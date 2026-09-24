from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from agents.agent.cover_letter import (
    finalize_cover_letter,
    review_cover_letter,
    route_after_review,
    write_cover_letter,
)
from agents.agent.job_discovery import (
    build_search_query,
    make_search_node,
    route_after_cache,
    search_cache,
)
from agents.agent.job_selection import route_after_selection, select_jobs
from agents.agent.matcher import match_jobs, route_after_matching
from agents.agent.resume_parser import parse_resume
from agents.agent.resume_tailor import tailor_resume
from agents.agent.roadmap import build_roadmap
from agents.agent.skill_gap import find_skill_gap, route_after_skill_gap
from agents.errors import is_transient
from agents.graph.state import (
    AgentContext,
    CoverLetterInput,
    CoverLetterOutput,
    CoverLetterState,
    JobAgentState,
    JobAnalysisInput,
    JobAnalysisOutput,
    JobAnalysisState,
)

JOB_SOURCES = ("adzuna", "jooble")


def default_retry_policy():
    # Only rate limits, timeouts and 5xx errors are retried (see is_transient)
    return RetryPolicy(
        max_attempts=4,
        initial_interval=5.0,
        backoff_factor=2.0,
        max_interval=30.0,
        retry_on=is_transient,
    )


def build_job_analysis_graph(retry_policy):
    """Subgraph run once per top job: skill gap -> (roadmap if anything is missing)."""
    graph = StateGraph(
        JobAnalysisState,
        AgentContext,
        input_schema=JobAnalysisInput,
        output_schema=JobAnalysisOutput,
    )
    graph.add_node("find_skill_gap", find_skill_gap, retry_policy=retry_policy)
    graph.add_node("build_roadmap", build_roadmap, retry_policy=retry_policy)

    graph.add_edge(START, "find_skill_gap")
    graph.add_conditional_edges("find_skill_gap", route_after_skill_gap, ["build_roadmap", END])
    graph.add_edge("build_roadmap", END)
    return graph.compile()


def build_cover_letter_graph(retry_policy):
    """Subgraph run once per selected job: write <-> review until approved."""
    graph = StateGraph(
        CoverLetterState,
        AgentContext,
        input_schema=CoverLetterInput,
        output_schema=CoverLetterOutput,
    )
    graph.add_node("write_cover_letter", write_cover_letter, retry_policy=retry_policy)
    graph.add_node("review_cover_letter", review_cover_letter, retry_policy=retry_policy)
    graph.add_node("finalize_cover_letter", finalize_cover_letter)

    graph.add_edge(START, "write_cover_letter")
    graph.add_edge("write_cover_letter", "review_cover_letter")
    graph.add_conditional_edges(
        "review_cover_letter",
        route_after_review,
        ["write_cover_letter", "finalize_cover_letter"],
    )
    graph.add_edge("finalize_cover_letter", END)
    return graph.compile()


def build_graph(checkpointer=None, retry_policy=None):
    """
    parse_resume -> build_search_query -> (adzuna | jooble in parallel) -> match_jobs
        -> [too few jobs: loop back with a broader query]
        -> analyze_job x N in parallel (subgraph)
        -> select_jobs (pauses for the user)
        -> cover_letter x selected in parallel (subgraph with review loop)
    """
    retry_policy = retry_policy or default_retry_policy()

    graph = StateGraph(JobAgentState, AgentContext)

    graph.add_node("parse_resume", parse_resume, retry_policy=retry_policy)
    graph.add_node("search_cache", search_cache)
    graph.add_node("build_search_query", build_search_query)
    for source in JOB_SOURCES:
        graph.add_node(f"search_{source}", make_search_node(source))
    graph.add_node("match_jobs", match_jobs)
    graph.add_node("analyze_job", build_job_analysis_graph(retry_policy))
    graph.add_node("select_jobs", select_jobs)
    graph.add_node("cover_letter", build_cover_letter_graph(retry_policy))
    graph.add_node("tailor_resume", tailor_resume, retry_policy=retry_policy)

    graph.add_edge(START, "parse_resume")
    graph.add_edge("parse_resume", "search_cache")
    graph.add_conditional_edges(
        "search_cache",
        route_after_cache,
        ["match_jobs", "build_search_query"],
    )
    for source in JOB_SOURCES:
        graph.add_edge("build_search_query", f"search_{source}")
    # Wait for every source before ranking
    graph.add_edge([f"search_{source}" for source in JOB_SOURCES], "match_jobs")

    graph.add_conditional_edges(
        "match_jobs",
        route_after_matching,
        ["build_search_query", "analyze_job", END],
    )
    graph.add_edge("analyze_job", "select_jobs")
    graph.add_conditional_edges("select_jobs", route_after_selection, ["cover_letter", "tailor_resume", END])
    graph.add_edge("cover_letter", END)
    graph.add_edge("tailor_resume", END)

    return graph.compile(checkpointer=checkpointer)
