import time
import uuid

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from agents.errors import TransientError, UserFacingError
from agents.graph.state import AgentContext
from agents.graph.workflow import build_graph
from conftest import FAST_RETRY, FakeServices, make_jobs

INPUT = {"user_id": "user-1", "resume_path": "user-1/cv.pdf", "resume_text": "Python SQL Excel analyst"}


def new_thread():
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


def run(graph, graph_input, config, context):
    """Run until the graph finishes or pauses; return streamed progress messages."""
    messages = []
    for _ns, mode, chunk in graph.stream(
        graph_input, config, context=context, stream_mode=["custom", "updates"], subgraphs=True
    ):
        if mode == "custom":
            messages.append(chunk["message"])
    return messages


@pytest.fixture
def graph():
    return build_graph(checkpointer=InMemorySaver(), retry_policy=FAST_RETRY)


def test_full_run_pauses_for_selection_then_writes_letters(graph, fake, context):
    config = new_thread()
    messages = run(graph, INPUT, config, context)

    snapshot = graph.get_state(config)
    assert snapshot.next == ("select_jobs",)
    assert len(snapshot.interrupts) == 1
    jobs = snapshot.interrupts[0].value["jobs"]
    assert [job["id"] for job in jobs] == [0, 1, 2, 3, 4]

    values = snapshot.values
    # Top 5 only: 7 unique jobs found, 5 analyzed
    assert len(values["ranked_jobs"]) == 5
    assert fake.count("skill_gap") == 5
    assert len(values["skill_gaps"]) == 5
    assert values["ranked_jobs"][0]["score"] >= values["ranked_jobs"][-1]["score"]
    # Both sources queried in the same step
    assert fake.count("search_adzuna") == 1 and fake.count("search_jooble") == 1
    # Progress from inside subgraphs reaches the stream
    assert any(m.startswith("Analyzed skill gaps for") for m in messages)
    # No cover letters before the user chooses
    assert fake.count("write_letter") == 0

    run(graph, Command(resume=[0, 2]), config, context)

    final = graph.get_state(config)
    assert final.next == ()
    letters = final.values["cover_letters"]
    assert sorted(letter["job_id"] for letter in letters) == [0, 2]
    assert all(letter["approved"] and letter["drafts"] == 1 for letter in letters)
    assert fake.count("write_letter") == 2
    tailored = final.values.get("tailored_resumes", [])
    assert sorted(t["job_id"] for t in tailored) == [0, 2]
    assert all(t["ats_score"] == 88 for t in tailored)


def test_roadmap_only_built_when_skills_are_missing(graph, context, fake):
    config = new_thread()
    fake.missing_skills = lambda title: [] if title in ("Data Analyst", "Junior Data Analyst") else ["spark"]
    run(graph, INPUT, config, context)

    values = graph.get_state(config).values
    gaps = {gap["job_title"]: gap["missing_skills"] for gap in values["skill_gaps"]}
    roadmap_titles = {roadmap["job_title"] for roadmap in values["roadmaps"]}

    assert roadmap_titles == {title for title, missing in gaps.items() if missing}
    assert fake.count("roadmap") == len(roadmap_titles)


def test_skipping_selection_ends_without_cover_letters(graph, context, fake):
    config = new_thread()
    run(graph, INPUT, config, context)
    run(graph, Command(resume=[]), config, context)

    final = graph.get_state(config)
    assert final.next == ()
    assert final.values.get("cover_letters", []) == []
    assert fake.count("write_letter") == 0


def test_invalid_selection_ids_are_ignored(graph, context, fake):
    config = new_thread()
    run(graph, INPUT, config, context)
    run(graph, Command(resume=[99, 1, 1, "x"]), config, context)

    assert graph.get_state(config).values["selected_job_ids"] == [1]
    assert fake.count("write_letter") == 1


def test_search_broadens_query_when_too_few_jobs(graph, context, fake):
    # The most specific query finds 1 job; broader queries find more
    fake.jobs_for_query = lambda source, query: make_jobs(source, 1 if query == "Data Analyst Python" else 6)
    config = new_thread()
    run(graph, INPUT, config, context)

    values = graph.get_state(config).values
    queries = [key for kind, key in fake.calls if kind == "search_adzuna"]
    assert queries == ["Data Analyst Python", "Data Analyst"]
    assert values["search_attempts"] == 2
    assert len(values["ranked_jobs"]) == 5


def test_no_jobs_stops_after_all_queries(graph, context, fake):
    fake.jobs_for_query = lambda source, query: []
    config = new_thread()
    run(graph, INPUT, config, context)

    final = graph.get_state(config)
    assert final.next == ()
    assert final.values["ranked_jobs"] == []
    assert final.values["search_attempts"] == context.max_search_attempts
    assert fake.count("skill_gap") == 0


def test_failing_job_source_does_not_stop_analysis(graph, context, fake):
    def jobs_for_query(source, query):
        if source == "jooble":
            raise RuntimeError("Jooble is down")
        return make_jobs(source)

    fake.jobs_for_query = jobs_for_query
    config = new_thread()
    messages = run(graph, INPUT, config, context)

    assert "Jooble is unavailable right now" in messages
    assert len(graph.get_state(config).values["ranked_jobs"]) == 5


def test_review_loop_rewrites_rejected_letter(graph, context, fake):
    fake.review = lambda title, drafts: (
        {"approved": False, "score": 2, "feedback": "Mention the company"} if drafts == 1
        else {"approved": True, "score": 5, "feedback": ""}
    )
    config = new_thread()
    run(graph, INPUT, config, context)
    run(graph, Command(resume=[0]), config, context)

    letter = graph.get_state(config).values["cover_letters"][0]
    assert letter["drafts"] == 2
    assert letter["approved"] is True
    assert letter["review_score"] == 5
    assert "Draft 2" in letter["cover_letter"]


def test_review_loop_stops_after_max_revisions(graph, context, fake):
    fake.review = lambda title, drafts: {"approved": False, "score": 2, "feedback": "Still weak"}
    config = new_thread()
    run(graph, INPUT, config, context)
    run(graph, Command(resume=[0]), config, context)

    letter = graph.get_state(config).values["cover_letters"][0]
    assert letter["drafts"] == 1 + context.max_letter_revisions
    assert letter["approved"] is False


def test_transient_errors_are_retried(graph, context, fake):
    fake.failures[("skill_gap", "Data Analyst")] = [TransientError("429 rate limit")]
    config = new_thread()
    run(graph, INPUT, config, context)

    assert fake.count("skill_gap", "Data Analyst") == 2
    assert len(graph.get_state(config).values["skill_gaps"]) == 5


def test_permanent_errors_are_not_retried(graph, context, fake):
    fake.failures[("parse_resume", None)] = [RuntimeError("invalid API key")]
    with pytest.raises(RuntimeError):
        run(graph, INPUT, new_thread(), context)
    assert fake.count("parse_resume") == 1


def test_resume_without_skills_is_user_facing_error(graph, context, fake):
    fake.profile = {**fake.profile, "skills": [], "suggested_role": ""}
    with pytest.raises(UserFacingError):
        run(graph, INPUT, new_thread(), context)


def test_invalid_llm_json_uses_fallback(graph, context, fake):
    fake.missing_skills = lambda title: "not a list"
    config = new_thread()
    run(graph, INPUT, config, context)

    gaps = graph.get_state(config).values["skill_gaps"]
    assert all(gap["source"] == "fallback" and gap["missing_skills"] == [] for gap in gaps)


def test_crashed_run_resumes_from_checkpoint_without_redoing_work(tmp_path):
    """
    Durable execution: one job's analysis crashes, the "server restarts"
    (new graph + new saver on the same database), and resuming reruns only
    the failed branch. Resume parsing, job search and the other 4 job
    analyses come from the checkpoint.
    """
    db = tmp_path / "checkpoints.sqlite"
    fake = FakeServices()
    context = AgentContext(services=fake.as_services())
    config = new_thread()

    # Let the other branches finish before the failing one raises
    def slow_failure(title):
        if title == "Data Analyst":
            time.sleep(0.3)
            raise RuntimeError("process crashed")
        return ["tableau"]

    fake.missing_skills = slow_failure
    with SqliteSaver.from_conn_string(str(db)) as saver:
        graph = build_graph(checkpointer=saver, retry_policy=FAST_RETRY)
        with pytest.raises(RuntimeError):
            run(graph, INPUT, config, context)
        assert graph.get_state(config).next == ("analyze_job",)

    calls_before_restart = list(fake.calls)
    fake.missing_skills = lambda title: ["tableau"]

    with SqliteSaver.from_conn_string(str(db)) as saver:
        restarted = build_graph(checkpointer=saver, retry_policy=FAST_RETRY)
        run(restarted, None, config, context)
        snapshot = restarted.get_state(config)

    new_calls = fake.calls[len(calls_before_restart):]
    assert [kind for kind, _ in new_calls if kind in ("parse_resume", "search_adzuna", "search_jooble")] == []
    assert [key for kind, key in new_calls if kind == "skill_gap"] == ["Data Analyst"]
    assert snapshot.next == ("select_jobs",)
    assert len(snapshot.values["skill_gaps"]) == 5


def test_parallel_job_analysis_is_faster_than_sequential():
    """
    Every service call takes 0.1s. Run one after another, the calls would take
    (number of calls x 0.1s); the Send fan-out runs the 5 job analyses concurrently.
    """
    latency = 0.1
    fake = FakeServices(latency=latency)
    context = AgentContext(services=fake.as_services())
    graph = build_graph(checkpointer=InMemorySaver(), retry_policy=FAST_RETRY)

    started = time.perf_counter()
    run(graph, INPUT, new_thread(), context)
    elapsed = time.perf_counter() - started

    sequential_estimate = len(fake.calls) * latency
    assert len(fake.calls) == 13   # parse + 2 searches + 5 skill gaps + 5 roadmaps
    assert elapsed < sequential_estimate * 0.5
