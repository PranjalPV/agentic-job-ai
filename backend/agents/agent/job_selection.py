from langgraph.graph import END
from langgraph.types import Send, interrupt


def normalize_selection(choice, valid_ids):
    """Keep valid, unique job ids in the order the user picked them."""
    if not isinstance(choice, list):
        return []
    selected = []
    for job_id in choice:
        if isinstance(job_id, bool) or not isinstance(job_id, int):
            continue
        if job_id in valid_ids and job_id not in selected:
            selected.append(job_id)
    return selected


def select_jobs(state):
    """
    LangGraph node (human in the loop):
    Pause the graph until the user picks which jobs get cover letters.
    The run is saved by the checkpointer while waiting, and continues
    when the API resumes it with Command(resume=[job ids]).
    """
    jobs = state.get("ranked_jobs", [])

    choice = interrupt({
        "type": "select_jobs",
        "jobs": [
            {"id": job["id"], "title": job.get("title"), "company": job.get("company")}
            for job in jobs
        ],
    })

    return {"selected_job_ids": normalize_selection(choice, {job["id"] for job in jobs})}


def route_after_selection(state):
    """Conditional edge: write cover letters and tailor resumes for each selected job, in parallel."""
    selected = state.get("selected_job_ids", [])
    if not selected:
        return END

    jobs = {job["id"]: job for job in state.get("ranked_jobs", [])}
    gaps = {gap.get("job_id"): gap for gap in state.get("skill_gaps", [])}

    branches = []
    for job_id in selected:
        if job_id in jobs:
            payload = {
                "job": jobs[job_id],
                "parsed_resume": state["parsed_resume"],
                "missing_skills": gaps.get(job_id, {}).get("missing_skills", []),
            }
            branches.append(Send("cover_letter", payload))
            branches.append(Send("tailor_resume", payload))
    return branches or END
