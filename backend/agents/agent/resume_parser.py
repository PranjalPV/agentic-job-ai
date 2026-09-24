from langgraph.runtime import Runtime

from agents.errors import UserFacingError
from agents.utils import emit_progress


def parse_resume(state, runtime: Runtime):
    """
    LangGraph node:
    Resume text -> structured profile (Gemini)
    """
    resume_text = (state.get("resume_text") or "").strip()
    if not resume_text:
        raise UserFacingError("The uploaded resume has no readable text.")

    emit_progress("Reading your resume...", stage="parse_resume")
    parsed = runtime.context.services.parse_resume(resume_text)

    if not parsed.get("skills") and not parsed.get("suggested_role"):
        raise UserFacingError(
            "We couldn't find any skills or job titles in your resume."
        )

    emit_progress(
        f"Found {len(parsed.get('skills', []))} skills"
        + (f", best fit: {parsed['suggested_role']}" if parsed.get("suggested_role") else ""),
        stage="parse_resume",
    )
    return {"parsed_resume": parsed}
