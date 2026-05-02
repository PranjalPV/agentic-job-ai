import os
from dotenv import load_dotenv
import json
from groq import Groq
import re
from pprint import pprint

load_dotenv()

def generate_roadmaps(state):
    """
    LangGraph node:
    Generate optimized learning roadmaps using Groq
    """

    if "parsed_resume" not in state:
        print("❌ parsed_resume missing")
        return state

    if "skill_gaps" not in state or not state["skill_gaps"]:
        print("❌ skill_gaps missing or empty")
        return state

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    resume_skills = state["parsed_resume"]["skills"]
    roadmaps = []

    for gap in state["skill_gaps"]:
        missing_skills = gap.get("missing_skills", [])
        job_title = gap.get("job_title")
        company = gap.get("company")

        if not missing_skills:
            continue

        prompt = f"""
You are a senior software mentor.

Candidate current skills:
{resume_skills}

Target role:
{job_title} at {company}

Missing skills:
{missing_skills}

Create an optimized learning roadmap.

Rules:
- Organize by phases (Week 1–2, Week 3–4, etc.)
- Focus on practical projects
- Prioritize skills logically
- Keep roadmap concise
- Output ONLY valid JSON like:

{{
  "roadmap": [
    {{
      "phase": "Week 1–2",
      "focus": ["docker"],
      "tasks": ["..."]
    }}
  ]
}}
"""

        # try:
        #     response = client.chat.completions.create(
        #         model="llama-3.1-8b-instant",
        #         messages=[{"role": "user", "content": prompt}],
        #         temperature=0
        #     )

        #     roadmap_json = json.loads(
        #         response.choices[0].message.content
        #     )

        #     roadmaps.append({
        #         "job_title": job_title,
        #         "company": company,
        #         "roadmap": roadmap_json["roadmap"]
        #     })

        # except Exception as e:
        #     print(f"⚠️ Roadmap generation failed for {job_title}: {e}")
        try:
            response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
            )

            content = response.choices[0].message.content
            roadmap_json = safe_json_parse(content)

            if not roadmap_json or "roadmap" not in roadmap_json:
                raise ValueError("Invalid JSON from Groq")

            roadmaps.append({
                "job_title": job_title,
                "company": company,
                "roadmap": roadmap_json["roadmap"],
                "source": "groq"
            })

        except Exception as e:
            print(f"⚠️ Roadmap generation failed for {job_title}: {e}")
            # 🔁 FALLBACK (ALWAYS WORKS)
            roadmaps.append({
                "job_title": job_title,
                "company": company,
                "roadmap": fallback_roadmap(missing_skills),
                "source": "fallback"
            })

    state["roadmaps"] = roadmaps
    return state

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


def safe_json_parse(text: str):
    """
    Extract and parse JSON from LLM output safely
    """
    try:
        return json.loads(text)
    except Exception:
        # Try to extract JSON block
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                return None
        return None

# if __name__ == "__main__":
#     mock_state = {
#         "parsed_resume": {
#             "skills": ["Python", "FastAPI", "Machine Learning"]
#         },
#         "skill_gaps": [
#             {
#                 "job_title": "Machine Learning Engineer",
#                 "company": "AI Labs",
#                 "missing_skills": ["docker", "kubernetes", "aws"]
#             }
#         ]
#     }

#     out = generate_roadmaps(mock_state)

    
#     pprint(out["roadmaps"])
