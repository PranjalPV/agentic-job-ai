import hashlib
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest
from langgraph.types import RetryPolicy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.errors import is_transient  # noqa: E402
from agents.graph.state import AgentContext  # noqa: E402
from agents.services import Services  # noqa: E402

PROFILE = {
    "name": "Test Candidate",
    "suggested_role": "Data Analyst",
    "skills": ["Python", "SQL", "Excel"],
    "experience_level": "Junior",
    "summary": "Junior data analyst who builds dashboards with Python and SQL.",
}

JOB_DESCRIPTIONS = [
    ("Data Analyst", "Acme", "Data analyst with Python, SQL and Tableau dashboards."),
    ("Junior Data Analyst", "Globex", "Analyze data using SQL, Excel and Power BI."),
    ("Business Analyst", "Initech", "Business analyst using Excel and SQL reports."),
    ("Data Engineer", "Umbrella", "Build pipelines with Python, Airflow and Spark."),
    ("BI Developer", "Hooli", "Create Power BI dashboards with SQL and DAX."),
    ("Analytics Intern", "Stark", "Python and pandas analytics internship."),
    ("Sales Executive", "Wayne", "Sales role with strong communication skills."),
]


def make_jobs(source, count=len(JOB_DESCRIPTIONS)):
    return [
        {
            "title": title,
            "company": company,
            "location": "India",
            "description": description,
            "apply_link": f"https://example.com/{source}/{i}",
            "source": source,
        }
        for i, (title, company, description) in enumerate(JOB_DESCRIPTIONS[:count])
    ]


def fake_embed(texts):
    """Deterministic bag-of-words vectors, normalized like the real embedder."""
    vectors = np.zeros((len(texts), 256))
    for row, text in enumerate(texts):
        for word in text.lower().replace(",", " ").replace(".", " ").split():
            bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % 256
            vectors[row, bucket] += 1
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


class FakeServices:
    """
    Records every call so tests can assert exactly what ran.
    Behaviour can be changed per test through the attributes below.
    """

    def __init__(self, latency=0.0):
        self.latency = latency
        self.calls = []
        self.lock = threading.Lock()

        self.profile = dict(PROFILE)
        self.jobs_for_query = lambda source, query: make_jobs(source)
        self.missing_skills = lambda title: [] if "Sales" in title else ["tableau", "power bi"]
        self.review = lambda title, draft_number: {"approved": True, "score": 5, "feedback": ""}
        self.failures = {}   # (kind, job title) -> list of exceptions to raise, in order
        self.letter_drafts = {}

    def record(self, kind, key=None):
        with self.lock:
            self.calls.append((kind, key))
            queue = self.failures.get((kind, key))
            error = queue.pop(0) if queue else None
        if self.latency:
            time.sleep(self.latency)
        if error:
            raise error

    def count(self, kind, key=None):
        return sum(1 for k, v in self.calls if k == kind and (key is None or v == key))

    # --- Services interface ---
    def parse_resume(self, text):
        self.record("parse_resume")
        return dict(self.profile)

    def llm_json(self, system, prompt):
        title = next(
            (line.split(":", 1)[1].strip() for line in prompt.splitlines() if line.startswith("Title:")),
            None,
        )
        if "recruiter" in system:
            self.record("skill_gap", title)
            return {"missing_skills": self.missing_skills(title)}
        if "mentor" in system:
            target = prompt.split("Target role:\n", 1)[1].split(" at ", 1)[0].strip()
            self.record("roadmap", target)
            return {"roadmap": [{"phase": "Week 1–2", "focus": ["tableau"], "tasks": ["Build a dashboard"]}]}
        if "review" in system:
            self.record("review", title)
            with self.lock:
                draft_number = self.letter_drafts.get(title, 0)
            return self.review(title, draft_number)
        if "ats" in system.lower() or "optimizer" in system.lower():
            self.record("tailor_resume", title)
            return {
                "ats_score": 88,
                "matched_keywords": ["Python", "SQL"],
                "missing_critical_keywords": ["Tableau"],
                "tailored_summary": f"Targeted candidate summary for {title}.",
                "tailored_bullet_points": [
                    f"Implemented scalable data workflows aligned with {title} requirements.",
                    "Optimized query execution and built dashboards using SQL and Python."
                ],
                "ats_recommendations": ["Highlight data modeling skills prominently."]
            }
        raise AssertionError(f"Unexpected llm_json call: {system}")

    def llm_text(self, system, prompt):
        title = next(line.split(":", 1)[1].strip() for line in prompt.splitlines() if line.startswith("Title:"))
        self.record("write_letter", title)
        with self.lock:
            self.letter_drafts[title] = self.letter_drafts.get(title, 0) + 1
            number = self.letter_drafts[title]
        return f"Dear Hiring Manager,\n\nDraft {number} for {title}.\n\nKind regards,\n{PROFILE['name']}"

    def search(self, source):
        def run(query, location):
            self.record(f"search_{source}", query)
            return self.jobs_for_query(source, query)
        return run

    def as_services(self, sources=("adzuna", "jooble")):
        return Services(
            parse_resume=self.parse_resume,
            llm_json=self.llm_json,
            llm_text=self.llm_text,
            embed=fake_embed,
            job_sources={source: self.search(source) for source in sources},
            vector_search=getattr(self, "vector_search", None),
            cache_jobs=getattr(self, "cache_jobs", None),
        )


FAST_RETRY = RetryPolicy(max_attempts=3, initial_interval=0.01, backoff_factor=1.0, jitter=False, retry_on=is_transient)


@pytest.fixture
def fake():
    return FakeServices()


@pytest.fixture
def context(fake):
    return AgentContext(services=fake.as_services())


def make_pdf(text):
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data
