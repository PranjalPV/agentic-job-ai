import time

from langgraph.runtime import Runtime

from agents.errors import UserFacingError, is_transient
from agents.utils import emit_progress, logger


def search_queries(parsed_resume):
    """
    Search queries from most specific to broadest.
    Each loop back from the matcher uses the next one.
    """
    role = (parsed_resume.get("suggested_role") or "").strip()
    skills = [s.strip() for s in parsed_resume.get("skills", []) if s and s.strip()]

    candidates = []
    if role and skills:
        candidates.append(f"{role} {skills[0]}")
    if role:
        candidates.append(role)
    if skills:
        candidates.append(" ".join(skills[:2]))
        candidates.append(skills[0])

    unique = []
    for query in candidates:
        if query.lower() not in [q.lower() for q in unique]:
            unique.append(query)
    return unique


def build_search_query(state):
    """
    LangGraph node:
    Pick the next search query (broader on every retry)
    """
    queries = search_queries(state.get("parsed_resume", {}))
    if not queries:
        raise UserFacingError("We couldn't find any skills or job titles in your resume.")

    attempt = state.get("search_attempts", 0)
    query = queries[min(attempt, len(queries) - 1)]

    emit_progress(f'Searching jobs for "{query}"...', stage="search")
    return {"search_query": query, "search_attempts": attempt + 1}


def make_search_node(source_name, attempts=2, retry_delay=1.0):
    """
    LangGraph node factory:
    Query one job source. Sources are optional, so a failing source
    returns no jobs instead of failing the whole analysis.
    """

    def search(state, runtime: Runtime):
        source = runtime.context.services.job_sources.get(source_name)
        if source is None:
            logger.warning("%s is not configured, skipping", source_name)
            return {"job_results": []}

        query = state["search_query"]
        for attempt in range(1, attempts + 1):
            try:
                jobs = source(query, runtime.context.location)
                emit_progress(f"{source_name.title()}: {len(jobs)} jobs", stage="search")
                return {"job_results": jobs}
            except Exception as e:
                if attempt < attempts and is_transient(e):
                    time.sleep(retry_delay)
                    continue
                logger.warning("%s search failed: %s", source_name, e)
                emit_progress(f"{source_name.title()} is unavailable right now", stage="search")
                return {"job_results": []}

    search.__name__ = f"search_{source_name}"
    return search


def search_cache(state, runtime: Runtime):
    """
    LangGraph node:
    Queries shared vector database (Supabase pgvector) for fresh matching jobs (< 7 days old).
    """
    services = runtime.context.services
    if not services.vector_search:
        return {"job_results": []}

    parsed = state.get("parsed_resume", {})
    parts = [
        parsed.get("suggested_role", ""),
        parsed.get("summary", ""),
        "Skills: " + ", ".join(parsed.get("skills", [])),
    ]
    text = ". ".join(p for p in parts if p)
    if not text:
        return {"job_results": []}

    emit_progress("Checking shared vector cache for recent matches...", stage="search")
    try:
        vectors = services.embed([text])
        query_vector = vectors[0]
        cached_jobs = services.vector_search(query_vector, limit=runtime.context.top_n_jobs)
        if cached_jobs:
            emit_progress(f"Vector Cache: Found {len(cached_jobs)} fresh cached jobs (15ms)", stage="search")
            return {"job_results": cached_jobs}
    except Exception as e:
        logger.info("Vector cache lookup skipped: %s", e)

    return {"job_results": []}


def route_after_cache(state, runtime: Runtime):
    """
    Conditional edge:
    If cache provides enough fresh matches (>= min_jobs), jump straight to ranking (15ms path).
    Otherwise, query live external APIs (Adzuna + Jooble) to discover new jobs.
    """
    cached = state.get("job_results", [])
    if len(cached) >= runtime.context.min_jobs:
        return "match_jobs"
    return "build_search_query"
