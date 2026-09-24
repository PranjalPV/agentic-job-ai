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
