import os
import json
import requests
from dotenv import load_dotenv
# from jobspy import scrape_jobs 

load_dotenv()

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY")


def discover_jobs(state):
    if "parsed_resume" not in state:
        print("❌ No parsed resume found.")
        return state

    if "resume_text" not in state:
        print("❌ resume_text missing.")
        return state

    parsed_resume = state["parsed_resume"]
    skills = parsed_resume.get("skills", [])
    summary = parsed_resume.get("summary", "")

    """
    LangGraph node:
    Takes parsed resume → searches jobs using
    Adzuna + Jooble + JobSpy
    """

    # ---- Build search query from resume ----
    # simple + effective
    search_query = " ".join(skills[:5]) or summary

    all_jobs = []

    # =========================
    # 1️⃣ ADZUNA
    # =========================
    try:
        url = "https://api.adzuna.com/v1/api/jobs/in/search/1"
        params = {
            "app_id": ADZUNA_APP_ID,
            "app_key": ADZUNA_APP_KEY,
            "what": search_query,
            "content-type": "application/json"
        }

        res = requests.get(url, params=params)
        res.raise_for_status()

        for job in res.json().get("results", []):
            all_jobs.append({
                "title": job["title"],
                "company": job["company"]["display_name"],
                "location": job["location"]["display_name"],
                "description": job["description"],
                "apply_link": job["redirect_url"],
                "source": "Adzuna"
            })

    except Exception as e:
        print(f"⚠️ Adzuna error: {e}")

    # =========================
    # 2️⃣ JOOBLE
    # =========================
    try:
        url = f"https://jooble.org/api/{JOOBLE_API_KEY}"
        payload = {
            "keywords": search_query,
            "location": "India"
        }

        res = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload)
        )
        res.raise_for_status()

        for job in res.json().get("jobs", []):
            all_jobs.append({
                "title": job["title"],
                "company": job.get("company", "Unknown"),
                "location": job.get("location"),
                "description": job.get("snippet", ""),
                "apply_link": job["link"],
                "source": "Jooble"
            })

    except Exception as e:
        print(f"⚠️ Jooble error: {e}")

    # =========================
    # 3️⃣ PYTHON-JOBSPY
    # =========================
    # try:
    #     df = scrape_jobs(
    #         site_name=["indeed", "glassdoor"],
    #         search_term=search_query,
    #         location="India",
    #         results_wanted=10
    #     )

    #     for _, row in df.iterrows():
    #         all_jobs.append({
    #             "title": row.get("job_title"),
    #             "company": row.get("company"),
    #             "location": row.get("location"),
    #             "description": row.get("description"),
    #             "apply_link": row.get("job_url"),
    #             "source": "JobSpy"
    #         })

    # except Exception as e:
    #     print(f"⚠️ JobSpy error: {e}")

    # state["job_results"] = all_jobs
    # ---- Deduplicate ----
    unique = {}
    for job in all_jobs:
        key = (job["title"], job["company"])
        unique[key] = job

    state["job_results"] = list(unique.values())
    return state

# if __name__ == "__main__":
#     print("\n🧪 Running discover_jobs local test\n")

#     mock_state = {
#         "resume_text": "Python NLP",
#         "parsed_resume": {
#             "skills": ["Python", "NLP"],
#             "summary": "AI Engineer"
#         }
#     }

#     result = discover_jobs(mock_state)

#     jobs = result.get("job_results", [])

#     print(f"\n✅ Total jobs fetched: {len(jobs)}")

#     # ---- Count jobs per source ----
#     source_count = {
#         "Adzuna": 0,
#         "Jooble": 0,
#         "JobSpy": 0
#     }

#     for job in jobs:
#         source = job.get("source")
#         if source in source_count:
#             source_count[source] += 1

#     print("\n📊 Jobs per source:")
#     for source, count in source_count.items():
#         status = "✅ WORKING" if count > 0 else "❌ NOT WORKING"
#         print(f"{source}: {count} → {status}")

#     # ---- Show sample jobs from each source ----
#     print("\n🔍 Sample jobs from each source:\n")

#     seen = set()
#     for job in jobs:
#         src = job["source"]
#         if src not in seen:
#             print(f"[{src}] {job['title']} | {job['company']}")
#             seen.add(src)

#     print("\n🧠 Test completed.")

#     print("🧪 Running local test for discover_jobs...\n")

#     mock_state = {
#         "resume_text": "Python NLP",
#         "parsed_resume": {
#             "skills": ["Python", "NLP"],
#             "summary": "AI Engineer"
#         }
#     }

#     result = discover_jobs(mock_state)

#     jobs = result.get("job_results", [])

#     print(f"✅ Total jobs found: {len(jobs)}\n")

#     for job in jobs[:5]:
#         print(f"1.) {job['title']} | {job['company']} | {job['source']} | {job['location']} | {job['apply_link']}")

