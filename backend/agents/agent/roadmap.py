from langgraph.runtime import Runtime

from agents.errors import InvalidLLMOutput
from agents.utils import emit_progress, logger

SYSTEM_PROMPT = "You are a senior software mentor. You answer only with JSON."


def fallback_roadmap(missing_skills):
    roadmap = []
    week = 1

    for skill in missing_skills[:5]:
        roadmap.append({
            "phase": f"Week {week}-{week+1}",
            "focus": [skill],
            "tasks": [
                f"Learn fundamentals of {skill}",
                f"Build a small project using {skill}",
                f"Practice interview questions for {skill}"
            ]
        })
        week += 2

    return roadmap


def validate_roadmap(roadmap):
    """Keep only well-formed phases: {phase: str, focus: [str], tasks: [str]}."""
    if not isinstance(roadmap, list):
        raise InvalidLLMOutput("roadmap is not a list")

    phases = []
    for item in roadmap:
        if not isinstance(item, dict) or not item.get("phase"):
            continue
        focus = item.get("focus")
        tasks = item.get("tasks")
        phases.append({
            "phase": str(item["phase"]),
            "focus": [str(f) for f in focus] if isinstance(focus, list) else [str(focus or "")],
            "tasks": [str(t) for t in tasks] if isinstance(tasks, list) else [],
        })

    if not phases:
        raise InvalidLLMOutput("roadmap has no valid phases")
    return phases


def build_roadmap(state, runtime: Runtime):
    """
    LangGraph node (job analysis subgraph):
    Week-by-week learning plan for the missing skills (Groq)
    """
    job = state["job"]
    missing_skills = state["missing_skills"]

    prompt = f"""Candidate current skills:
{state["parsed_resume"].get("skills", [])}

Target role:
{job.get("title")} at {job.get("company")}

Missing skills:
{missing_skills}

Create an optimized learning roadmap.

Rules:
- Organize by phases (Week 1–2, Week 3–4, etc.)
- Focus on practical projects
- Prioritize skills logically
- Keep roadmap concise
- Answer with JSON exactly like:

{{
  "roadmap": [
    {{
      "phase": "Week 1–2",
      "focus": ["docker"],
      "tasks": ["..."]
    }}
  ]
}}"""

    try:
        parsed = runtime.context.services.llm_json(SYSTEM_PROMPT, prompt)
        roadmap, source = validate_roadmap(parsed.get("roadmap")), "groq"
    except InvalidLLMOutput as e:
        logger.warning("Roadmap output invalid for %s: %s", job.get("title"), e)
        roadmap, source = fallback_roadmap(missing_skills), "fallback"

    emit_progress(f"Built learning roadmap for {job.get('title')}", stage="analyze_job")
    return {
        "roadmaps": [{
            "job_id": job.get("id"),
            "job_title": job.get("title"),
            "company": job.get("company"),
            "roadmap": roadmap,
            "source": source,
        }]
    }
