def generate_cover_letters(state):
    """
    LangGraph node:
    Generate cover letters for ALL jobs
    """

    if "skill_gaps" not in state or not state["skill_gaps"]:
        print("❌ skill_gaps missing or empty")
        return state

    cover_letters = []

    for gap in state["skill_gaps"]:
        job_title = gap.get("job_title", "the position")
        company = gap.get("company", "your company")
        missing_skills = gap.get("missing_skills", [])

        gaps_text = (
            ", ".join(missing_skills)
            if missing_skills
            else "all the required skills"
        )

        letter = f"""
Dear Hiring Manager at {company},

I am writing to express my interest in the {job_title} role.

I bring strong experience in Python, FastAPI, and Machine Learning,
and have worked on AI-driven and backend systems aligned with real-world applications.

I am actively strengthening my expertise in {gaps_text} to better align
my profile with the requirements of this role.

I would welcome the opportunity to contribute my skills and grow with your team.

Kind regards,
Pranjal Verma
""".strip()

        cover_letters.append({
            "job_title": job_title,
            "company": company,
            "cover_letter": letter
        })

    state["cover_letters"] = cover_letters
    return state



# if __name__ == "__main__":
#     mock_state = {
#         "skill_gaps": [
#             {
#                 "job_title": "Machine Learning Engineer",
#                 "company": "AI Labs",
#                 "missing_skills": ["docker", "kubernetes", "aws"]
#             },
#             {
#                 "job_title": "Backend Developer",
#                 "company": "Web Solutions",
#                 "missing_skills": ["django", "sql"]
#             }
#         ],
#         "selected_job_id": 1  # 👈 User selects Backend Developer
#     }

#     out = generate_cover_letter(mock_state)
#     print(out["cover_letter"])
