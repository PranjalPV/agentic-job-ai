import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from pydantic import BaseModel

from agents.config import Settings
from agents.errors import UserFacingError
from agents.graph.state import AgentContext
from agents.results import build_result
from agents.services import extract_text_from_pdf_bytes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("api")

MAX_RESUME_BYTES = 5 * 1024 * 1024
GENERIC_ERROR = "Something went wrong while analyzing your resume. Please try again."
LETTER_WORKERS = 2   # keep parallel LLM calls low for free-tier rate limits


# ----------------------------
# Dependencies (real ones are created at startup; tests pass fakes)
# ----------------------------
@dataclass
class AppDeps:
    graph: object                                  # compiled LangGraph with a checkpointer
    letter_graph: object                           # cover letter subgraph, for extra letters later
    context: AgentContext
    verify_token: Callable[[str], Optional[str]]   # access token -> user id
    download_resume: Callable[[str], bytes]        # storage path -> PDF bytes
    # (user id, resume path, analysis id, result): saves, or updates the row for that analysis
    persist_result: Callable[[str, str, str, dict], None]
    missing_settings: List[str] = field(default_factory=list)


def build_real_deps(settings: Settings) -> AppDeps:
    from supabase import create_client

    from agents.graph.checkpointer import make_checkpointer
    from agents.graph.workflow import build_cover_letter_graph, build_graph, default_retry_policy
    from agents.services import build_services

    missing = settings.missing()
    if missing:
        logger.warning("Missing settings: %s", ", ".join(missing))
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set (see backend/.env.example)")

    supabase = create_client(settings.supabase_url, settings.supabase_key)

    def verify_token(token):
        try:
            res = supabase.auth.get_user(token)
            return res.user.id if res and res.user else None
        except Exception as e:
            logger.info("Token rejected: %s", e)
            return None

    def download_resume(path):
        res = supabase.storage.from_("resumes").download(path)
        return res.data if hasattr(res, "data") else res

    def persist_result(user_id, path, thread_id, result):
        """One row per analysis: later cover letters update it instead of adding a row."""
        existing = (
            supabase.table("results")
            .select("id")
            .eq("user_id", user_id)
            .eq("result_json->>thread_id", thread_id)
            .limit(1)
            .execute()
        )
        rows = existing.data or []
        if rows:
            supabase.table("results").update({"result_json": result}).eq("id", rows[0]["id"]).execute()
        else:
            supabase.table("results").insert({
                "user_id": user_id,
                "resume_path": path,
                "result_json": result,
            }).execute()

    return AppDeps(
        graph=build_graph(checkpointer=make_checkpointer(settings)),
        letter_graph=build_cover_letter_graph(default_retry_policy()),
        context=AgentContext(services=build_services(settings), location=settings.job_location),
        verify_token=verify_token,
        download_resume=download_resume,
        persist_result=persist_result,
        missing_settings=missing,
    )


# ----------------------------
# Live run tracking (progress messages and errors for runs in this process)
# The graph's own state lives in the checkpointer and survives restarts.
# ----------------------------
@dataclass
class RunInfo:
    user_id: str
    running: bool = False
    progress: List[str] = field(default_factory=list)
    error: Optional[str] = None
    user_facing: bool = False


class RunTracker:
    def __init__(self):
        self._runs = {}
        self._lock = threading.Lock()

    def start(self, thread_id, user_id):
        with self._lock:
            run = self._runs.get(thread_id)
            if run and run.running:
                return False
            if not run:
                run = self._runs[thread_id] = RunInfo(user_id=user_id)
            run.running, run.error, run.user_facing = True, None, False
            return True

    def progress(self, thread_id, message):
        with self._lock:
            run = self._runs[thread_id]
            run.progress = (run.progress + [message])[-30:]

    def finish(self, thread_id, error=None, user_facing=False):
        with self._lock:
            run = self._runs[thread_id]
            run.running, run.error, run.user_facing = False, error, user_facing

    def get(self, thread_id) -> Optional[RunInfo]:
        with self._lock:
            run = self._runs.get(thread_id)
            return RunInfo(**vars(run)) if run else None


class AnalyzeRequest(BaseModel):
    file_path: str


class SelectRequest(BaseModel):
    job_ids: List[int]


def create_app(deps: Optional[AppDeps] = None, settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.deps = deps or build_real_deps(settings)
        yield

    app = FastAPI(title="Agentic Job AI", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    tracker = RunTracker()

    def get_deps(request: Request) -> AppDeps:
        return request.app.state.deps

    def current_user(authorization: str = Header(None), deps: AppDeps = Depends(get_deps)) -> str:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Please log in again")
        user_id = deps.verify_token(authorization.split(" ", 1)[1].strip())
        if not user_id:
            raise HTTPException(status_code=401, detail="Please log in again")
        return user_id

    def graph_config(thread_id):
        return {"configurable": {"thread_id": thread_id}}

    # ----------------------------
    # Saving results
    # ----------------------------
    def store_result(deps, thread_id, user_id, values):
        """Save the first time, then update the same row as letters are added."""
        try:
            deps.persist_result(
                user_id,
                values.get("resume_path"),
                thread_id,
                build_result(values, thread_id),
            )
        except Exception:
            logger.exception("Saving result failed for %s", thread_id)

    # ----------------------------
    # Background work
    # ----------------------------
    def run_graph(deps: AppDeps, thread_id: str, user_id: str, make_input: Callable[[], object]):
        config = graph_config(thread_id)
        graph_input = make_input()
        for _namespace, mode, chunk in deps.graph.stream(
            graph_input,
            config,
            context=deps.context,
            stream_mode=["custom", "updates"],
            subgraphs=True,
        ):
            if mode == "custom" and isinstance(chunk, dict) and chunk.get("message"):
                tracker.progress(thread_id, chunk["message"])

        snapshot = deps.graph.get_state(config)
        if not snapshot.next and snapshot.values.get("ranked_jobs"):
            store_result(deps, thread_id, user_id, snapshot.values)

    def run_extra_letters(deps: AppDeps, thread_id: str, user_id: str, job_ids: List[int]):
        """Write cover letters for more jobs of an analysis that already finished."""
        config = graph_config(thread_id)
        values = deps.graph.get_state(config).values
        jobs = {job["id"]: job for job in values.get("ranked_jobs", [])}
        gaps = {gap.get("job_id"): gap for gap in values.get("skill_gaps", [])}

        def write_one(job_id):
            payload = {
                "job": jobs[job_id],
                "parsed_resume": values.get("parsed_resume", {}),
                "missing_skills": gaps.get(job_id, {}).get("missing_skills", []),
            }
            final = {}
            for mode, chunk in deps.letter_graph.stream(
                payload, context=deps.context, stream_mode=["custom", "values"]
            ):
                if mode == "custom" and isinstance(chunk, dict) and chunk.get("message"):
                    tracker.progress(thread_id, chunk["message"])
                elif mode == "values":
                    final = chunk
            return final.get("cover_letters", [])

        letters = []
        with ThreadPoolExecutor(max_workers=LETTER_WORKERS) as pool:
            for written in pool.map(write_one, job_ids):
                letters.extend(written)

        if letters:
            # The reducer appends these to the letters already in the run
            deps.graph.update_state(config, {"cover_letters": letters}, as_node="cover_letter")
            store_result(deps, thread_id, user_id, deps.graph.get_state(config).values)

    def start_run(thread_id, user_id, work: Callable[[], None]):
        if not tracker.start(thread_id, user_id):
            raise HTTPException(status_code=409, detail="This analysis is already running")

        def guarded():
            try:
                work()
                tracker.finish(thread_id)
            except UserFacingError as e:
                logger.info("Run %s stopped: %s", thread_id, e)
                tracker.finish(thread_id, error=str(e), user_facing=True)
            except Exception:
                logger.exception("Run %s failed", thread_id)
                tracker.finish(thread_id, error=GENERIC_ERROR)

        threading.Thread(target=guarded, daemon=True).start()

    # ----------------------------
    # Status
    # ----------------------------
    def describe(deps: AppDeps, thread_id: str, user_id: str):
        run = tracker.get(thread_id)
        snapshot = deps.graph.get_state(graph_config(thread_id))
        values = snapshot.values or {}

        owner = values.get("user_id") or (run.user_id if run else None)
        if owner != user_id:
            raise HTTPException(status_code=404, detail="Analysis not found")

        response = {
            "thread_id": thread_id,
            "status": "error",
            "message": None,
            "progress": run.progress if run else [],
            "can_resume": False,
            "selection": None,
            "result": build_result(values, thread_id),
        }

        if run and run.running:
            response["status"] = "processing"
        elif snapshot.interrupts:
            response["status"] = "awaiting_selection"
            response["selection"] = snapshot.interrupts[0].value
        elif values and not snapshot.next:
            if values.get("ranked_jobs"):
                response["status"] = "done"
            else:
                response["message"] = "No matching jobs were found for your resume right now."
        elif run and run.error:
            response["message"] = run.error
            response["can_resume"] = not run.user_facing and bool(snapshot.next)
        elif snapshot.next:
            response["status"] = "stalled"
            response["message"] = "This analysis was interrupted (for example by a server restart)."
            response["can_resume"] = True
        else:
            response["message"] = GENERIC_ERROR

        return response

    # ----------------------------
    # Routes
    # ----------------------------
    @app.get("/health")
    def health(deps: AppDeps = Depends(get_deps)):
        return {"status": "ok", "missing_settings": deps.missing_settings}

    @app.post("/analyze")
    def analyze(req: AnalyzeRequest, user_id: str = Depends(current_user), deps: AppDeps = Depends(get_deps)):
        # Users may only analyze resumes in their own folder
        if not req.file_path.startswith(f"{user_id}/") or ".." in req.file_path:
            raise HTTPException(status_code=403, detail="Not allowed to use this file")

        thread_id = str(uuid.uuid4())

        def make_input():
            file_bytes = deps.download_resume(req.file_path)
            if file_bytes and len(file_bytes) > MAX_RESUME_BYTES:
                raise UserFacingError("Your resume is larger than 5 MB. Please upload a smaller PDF.")
            return {
                "user_id": user_id,
                "resume_path": req.file_path,
                "resume_text": extract_text_from_pdf_bytes(file_bytes),
            }

        start_run(thread_id, user_id, lambda: run_graph(deps, thread_id, user_id, make_input))
        return {"thread_id": thread_id, "status": "processing"}

    @app.get("/analyze/{thread_id}")
    def get_analysis(thread_id: str, user_id: str = Depends(current_user), deps: AppDeps = Depends(get_deps)):
        return describe(deps, thread_id, user_id)

    @app.post("/analyze/{thread_id}/select")
    def select(thread_id: str, req: SelectRequest, user_id: str = Depends(current_user),
               deps: AppDeps = Depends(get_deps)):
        state = describe(deps, thread_id, user_id)
        if state["status"] != "awaiting_selection":
            raise HTTPException(status_code=409, detail="This analysis is not waiting for a job selection")

        valid_ids = {job["id"] for job in state["selection"]["jobs"]}
        if any(job_id not in valid_ids for job_id in req.job_ids):
            raise HTTPException(status_code=422, detail="Unknown job selected")

        start_run(thread_id, user_id,
                  lambda: run_graph(deps, thread_id, user_id, lambda: Command(resume=req.job_ids)))
        return {"thread_id": thread_id, "status": "processing"}

    @app.post("/analyze/{thread_id}/letters")
    def more_letters(thread_id: str, req: SelectRequest, user_id: str = Depends(current_user),
                     deps: AppDeps = Depends(get_deps)):
        """Write cover letters for more jobs, after the analysis has finished."""
        state = describe(deps, thread_id, user_id)
        if state["status"] != "done":
            raise HTTPException(status_code=409, detail="This analysis is not finished yet")

        result = state["result"]
        known_ids = {job["id"] for job in result["top_jobs"]}
        already_written = {letter.get("job_id") for letter in result["cover_letters"]}

        if any(job_id not in known_ids for job_id in req.job_ids):
            raise HTTPException(status_code=422, detail="Unknown job selected")

        wanted = [job_id for job_id in dict.fromkeys(req.job_ids) if job_id not in already_written]
        if not wanted:
            raise HTTPException(status_code=422, detail="Those jobs already have a cover letter")

        start_run(thread_id, user_id, lambda: run_extra_letters(deps, thread_id, user_id, wanted))
        return {"thread_id": thread_id, "status": "processing", "job_ids": wanted}

    @app.post("/analyze/{thread_id}/resume")
    def resume(thread_id: str, user_id: str = Depends(current_user), deps: AppDeps = Depends(get_deps)):
        state = describe(deps, thread_id, user_id)
        if not state["can_resume"]:
            raise HTTPException(status_code=409, detail="This analysis can't be resumed")

        # Input None = continue from the last checkpoint; finished steps are not repeated
        start_run(thread_id, user_id, lambda: run_graph(deps, thread_id, user_id, lambda: None))
        return {"thread_id": thread_id, "status": "processing"}

    return app


app = create_app()
