from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


# Load model once (IMPORTANT)
model = SentenceTransformer("all-MiniLM-L6-v2")


def match_resume_jobs(state):
    """
    LangGraph node:
    Rank jobs using FREE local embeddings
    """

    if "resume_text" not in state:
        print("❌ resume_text missing in state")
        return state

    if "job_results" not in state:
        print("❌ job_results missing in state")
        return state

    resume_text = state["resume_text"]
    jobs = state["job_results"]

    resume_emb = model.encode(resume_text)

    ranked_jobs = []

    for job in jobs:
        description = job.get("description", "")
        if not description:
            continue

        job_emb = model.encode(description)

        score = cosine_similarity(
            [resume_emb],
            [job_emb]
        )[0][0]

        job_with_score = job.copy()
        job_with_score["score"] = float(score)

        ranked_jobs.append(job_with_score)

    state["ranked_jobs"] = sorted(
        ranked_jobs,
        key=lambda x: x["score"],
        reverse=True
    )

    return state


# if __name__ == "__main__":
    print("\n🧪 Testing rank_jobs...\n")

    mock_state = {
        "resume_text": "Python NLP Machine Learning Backend FastAPI",
        "job_results": [
            {
                "title": "AI Engineer",
                "description": "Looking for Python NLP engineer with machine learning experience",
                "company": "GoodMatch Inc",
                "location": "India",
                "apply_link": "test1",
                "source": "Adzuna"
            },
            {
                "title": "Backend Developer",
                "description": "Backend developer needed with Java and Spring Boot",
                "company": "MediumMatch Ltd",
                "location": "India",
                "apply_link": "test2",
                "source": "Jooble"
            },
            {
                "title": "Sales Executive",
                "description": "Looking for sales executive with communication skills",
                "company": "BadMatch Corp",
                "location": "India",
                "apply_link": "test3",
                "source": "JobSpy"
            }
        ]
    }

    result = rank_jobs(mock_state)

    print("🔢 Ranked Jobs (High → Low relevance):\n")

    for idx, job in enumerate(result["ranked_jobs"], start=1):
        print(
            f"{idx}. {job['title']} | "
            f"Score: {round(job['score'], 3)} | "
            f"Company: {job['company']}"
        )

    mock_state = {
        "resume_text": "Python NLP Machine Learning Backend",
        "job_results": [
            {
                "title": "AI Engineer",
                "description": "Looking for Python NLP engineer with ML experience",
                "company": "TestCorp",
                "location": "India",
                "apply_link": "test",
                "source": "Adzuna"
            }
        ]
    }

    out = rank_jobs(mock_state)
    print(out["ranked_jobs"])
