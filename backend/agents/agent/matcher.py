import numpy as np
from langgraph.graph import END
from langgraph.runtime import Runtime
from langgraph.types import Send

from agents.agent.job_discovery import search_queries
from agents.utils import emit_progress


def dedupe_jobs(jobs):
    """Drop jobs without a description and repeats of the same title + company."""
    unique = {}
    for job in jobs:
        if not job.get("description") or not job.get("title"):
            continue
        key = (job["title"].strip().lower(), (job.get("company") or "").strip().lower())
        unique.setdefault(key, job)
    return list(unique.values())


def profile_text(parsed_resume):
    """
    Short profile used for matching. The embedding model only reads
    ~256 tokens, so the structured profile is used instead of the full resume.
    """
    parts = [
        parsed_resume.get("suggested_role", ""),
        parsed_resume.get("summary", ""),
        "Skills: " + ", ".join(parsed_resume.get("skills", [])),
    ]
    return ". ".join(p for p in parts if p)


def match_jobs(state, runtime: Runtime):
    """
    LangGraph node:
    Rank all jobs found so far against the resume profile (local embeddings)
    """
    jobs = dedupe_jobs(state.get("job_results", []))
    if not jobs:
        emit_progress("No jobs found yet", stage="match")
        return {"ranked_jobs": []}

    vectors = np.asarray(runtime.context.services.embed(
        [profile_text(state["parsed_resume"])]
        + [f"{job['title']}. {job['description']}" for job in jobs]
    ))
    scores = vectors[1:] @ vectors[0]   # vectors are normalized -> cosine similarity

    order = np.argsort(-scores)[: runtime.context.top_n_jobs]
    ranked = []
    for rank, idx in enumerate(order):
        job = dict(jobs[idx])
        job["id"] = rank
        job["score"] = round(float(scores[idx]), 4)
        ranked.append(job)

    emit_progress(f"Ranked {len(jobs)} jobs, keeping the top {len(ranked)}", stage="match")
    return {"ranked_jobs": ranked}


def route_after_matching(state, runtime: Runtime):
    """
    Conditional edge:
    - too few matches and attempts left -> search again with a broader query
    - no matches at all -> stop
    - otherwise -> analyze every top job in parallel
    """
    ranked = state.get("ranked_jobs", [])

    max_attempts = min(
        runtime.context.max_search_attempts,
        len(search_queries(state.get("parsed_resume", {}))),
    )
    if len(ranked) < runtime.context.min_jobs and state.get("search_attempts", 0) < max_attempts:
        return "build_search_query"

    if not ranked:
        return END

    return [
        Send("analyze_job", {"job": job, "parsed_resume": state["parsed_resume"]})
        for job in ranked
    ]
