import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()


def find_skill_gaps(state):
    """
    LangGraph node:
    Identify skill gaps for ALL ranked jobs using GROQ (LLaMA 3)
    """

    if "parsed_resume" not in state:
        print("❌ parsed_resume missing")
        return state

    if "ranked_jobs" not in state or not state["ranked_jobs"]:
        print("❌ ranked_jobs missing or empty")
        return state

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("❌ GROQ_API_KEY missing")
        return state

    client = Groq(api_key=api_key)

    resume_skills = state["parsed_resume"]["skills"]
    skill_gaps_all = []

    for job in state["ranked_jobs"]:
        job_description = job.get("description", "")
        if not job_description:
            continue

        prompt = f"""
You are an expert technical recruiter.

Resume skills:
{resume_skills}

Job description:
{job_description}

Task:
List the technical skills required by the job that are NOT present
in the resume skills.

Rules:
- Only technical skills
- No explanations
- No duplicates
- Lowercase
- Output ONLY valid JSON like:
{{"missing_skills": ["skill1", "skill2"]}}
"""

        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You extract skill gaps."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )

            content = response.choices[0].message.content.strip()

            # Parse JSON safely
            import json
            parsed = json.loads(content)

            skill_gaps_all.append({
                "job_title": job.get("title"),
                "company": job.get("company"),
                "score": job.get("score"),
                "missing_skills": parsed.get("missing_skills", []),
                "source": "groq"
            })

        except Exception as e:
            print(f"⚠️ Groq error for {job.get('title')}: {e}")

    state["skill_gaps"] = skill_gaps_all
    return state


# if __name__ == "__main__":
    print("\n🧪 Running local test for find_skill_gaps (Gemini-based)\n")

    mock_state = {
        "parsed_resume": {
            "skills": ["Python", "FastAPI", "Machine Learning"]
        },
        "ranked_jobs": [
            {
                "title": "Machine Learning Engineer",
                "company": "AI Labs",
                "description": (
                    "We are looking for a Machine Learning Engineer with strong Python skills, "
                    "experience in Docker, Kubernetes, AWS, and CI/CD pipelines."
                ),
                "score": 0.82
            },
            {
                "title": "Backend Developer",
                "company": "Web Solutions",
                "description": (
                    "Backend developer required with Python, Django, SQL, and REST APIs."
                ),
                "score": 0.51
            },
            {
                "title": "Sales Executive",
                "company": "Sales Corp",
                "description": (
                    "Looking for a sales executive with communication and negotiation skills."
                ),
                "score": 0.08
            }
        ]
    }

    result = find_skill_gaps(mock_state)
    print("DEBUG skill_gaps:", result["skill_gaps"])
    if "skill_gaps" in result:
        print("✅ Skill gap detection successful\n")
        for i, gap in enumerate(result["skill_gaps"], start=1):
            print(f"Job {i}:")
            print("  Job Title :", gap["job_title"])
            print("  Company   :", gap["company"])
            print("  Missing   :", gap["missing_skills"])
            print("-" * 40)
            print("hihhduiwehd")
    else:
        print("❌ Skill gap detection failed")



