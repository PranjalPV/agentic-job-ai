from typing import TypedDict, List, Dict, Any


class JobAgentState(TypedDict, total=False):
    # ----------------------------
    # Resume parsing
    # ----------------------------
    resume_pdf_path: str
    resume_text: str
    parsed_resume: Dict[str, Any]   # {skills, experience_level, summary}

    # ----------------------------
    # Job discovery & ranking
    # ----------------------------
    job_results: List[Dict[str, Any]]
    ranked_jobs: List[Dict[str, Any]]

    # ----------------------------
    # Skill gap analysis (PER JOB)
    # ----------------------------
    skill_gaps: List[Dict[str, Any]]
    # each item:
    # {
    #   job_title: str
    #   company: str
    #   score: float
    #   missing_skills: List[str]
    #   source: "groq" | "fallback"
    # }

    # ----------------------------
    # User interaction
    # ----------------------------
    selected_job_id: int  # index of selected job

    # ----------------------------
    # Cover letter (job)
    # ----------------------------
    cover_letters: List[Dict[str, Any]]

    # ----------------------------
    # Learning roadmaps (PER JOB)
    # ----------------------------
    roadmaps: List[Dict[str, Any]]
    # each item:
    # {
    #   job_title: str
    #   company: str
    #   roadmap: List[Dict]
    # }
