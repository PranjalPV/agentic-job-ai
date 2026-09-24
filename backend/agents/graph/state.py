import operator
from dataclasses import dataclass
from typing import Annotated, Any, Dict, List, TypedDict

from agents.services import Services


# ----------------------------
# Runtime context (same for every node in a run, not saved in checkpoints)
# ----------------------------
@dataclass
class AgentContext:
    services: Services
    location: str = "India"
    top_n_jobs: int = 5
    min_jobs: int = 3            # fewer matches than this -> widen the search
    max_search_attempts: int = 3
    max_letter_revisions: int = 1  # extra drafts after the first one


# ----------------------------
# Main graph
# ----------------------------
class JobAgentState(TypedDict, total=False):
    # Input
    user_id: str
    resume_path: str
    resume_text: str

    # Resume parsing: {name, suggested_role, skills, experience_level, summary}
    parsed_resume: Dict[str, Any]

    # Job discovery (both sources run in parallel and append here)
    search_query: str
    search_attempts: int
    job_results: Annotated[List[Dict[str, Any]], operator.add]
    ranked_jobs: List[Dict[str, Any]]

    # Per-job analysis (one parallel branch per job appends here)
    skill_gaps: Annotated[List[Dict[str, Any]], operator.add]
    roadmaps: Annotated[List[Dict[str, Any]], operator.add]

    # Human in the loop: ids of jobs the user wants cover letters for
    selected_job_ids: List[int]

    # Cover letters (one parallel branch per selected job appends here)
    cover_letters: Annotated[List[Dict[str, Any]], operator.add]

    # Tailored resumes & ATS scoring (one parallel branch per selected job appends here)
    tailored_resumes: Annotated[List[Dict[str, Any]], operator.add]


# ----------------------------
# Subgraph: analyze one job (skill gap -> roadmap)
# ----------------------------
class JobAnalysisInput(TypedDict):
    job: Dict[str, Any]
    parsed_resume: Dict[str, Any]


class JobAnalysisState(TypedDict, total=False):
    job: Dict[str, Any]
    parsed_resume: Dict[str, Any]
    missing_skills: List[str]
    skill_gaps: Annotated[List[Dict[str, Any]], operator.add]
    roadmaps: Annotated[List[Dict[str, Any]], operator.add]


class JobAnalysisOutput(TypedDict, total=False):
    skill_gaps: Annotated[List[Dict[str, Any]], operator.add]
    roadmaps: Annotated[List[Dict[str, Any]], operator.add]


# ----------------------------
# Subgraph: write one cover letter (write <-> review loop)
# ----------------------------
class CoverLetterInput(TypedDict):
    job: Dict[str, Any]
    parsed_resume: Dict[str, Any]
    missing_skills: List[str]


class CoverLetterState(TypedDict, total=False):
    job: Dict[str, Any]
    parsed_resume: Dict[str, Any]
    missing_skills: List[str]
    draft: str
    drafts: int
    feedback: str
    review_score: Any
    approved: bool
    cover_letters: Annotated[List[Dict[str, Any]], operator.add]


class CoverLetterOutput(TypedDict, total=False):
    cover_letters: Annotated[List[Dict[str, Any]], operator.add]
