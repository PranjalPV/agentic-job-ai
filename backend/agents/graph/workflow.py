from langgraph.graph import StateGraph, END
from agents.graph.state import JobAgentState

from agents.agent.resume_parser import parse_resume
from agents.agent.job_discovery import discover_jobs
from agents.agent.matcher import match_resume_jobs
from agents.agent.skill_gap import find_skill_gaps
from agents.agent.cover_letter import generate_cover_letters
from agents.agent.roadmap import generate_roadmaps

def build_graph():
    graph = StateGraph(JobAgentState)

    # -----------------------
    # Nodes
    # -----------------------
    graph.add_node("parse_resume", parse_resume)
    graph.add_node("discover_jobs", discover_jobs)
    graph.add_node("match_jobs", match_resume_jobs)
    graph.add_node("skill_gap", find_skill_gaps)
    graph.add_node("cover_letter", generate_cover_letters)
    graph.add_node("roadmap", generate_roadmaps)

    # -----------------------
    # Linear autonomous flow
    # -----------------------
    graph.set_entry_point("parse_resume")
    graph.add_edge("parse_resume", "discover_jobs")
    graph.add_edge("discover_jobs", "match_jobs")
    graph.add_edge("match_jobs", "skill_gap")
    graph.add_edge("skill_gap", "cover_letter")
    graph.add_edge("cover_letter", "roadmap")
    graph.add_edge("roadmap", END)

    return graph.compile()
