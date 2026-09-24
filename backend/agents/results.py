def build_result(values, thread_id=None):
    """Shape saved to Supabase and shown on the website."""

    def by_job(items):
        return sorted(items or [], key=lambda item: (item.get("job_id") is None, item.get("job_id") or 0))

    return {
        "thread_id": thread_id,
        "profile": values.get("parsed_resume"),
        "top_jobs": [
            {**job, "description": (job.get("description") or "")[:400]}
            for job in values.get("ranked_jobs", [])
        ],
        "skill_gaps": by_job(values.get("skill_gaps")),
        "roadmap": by_job(values.get("roadmaps")),
        "cover_letters": by_job(values.get("cover_letters")),
        "tailored_resumes": by_job(values.get("tailored_resumes")),
    }
