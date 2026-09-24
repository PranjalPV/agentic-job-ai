import pytest
import requests

from agents.agent.cover_letter import template_cover_letter
from agents.agent.job_discovery import search_queries
from agents.agent.job_selection import normalize_selection
from agents.agent.matcher import dedupe_jobs, profile_text
from agents.agent.resume_tailor import fallback_tailoring
from agents.agent.roadmap import fallback_roadmap, validate_roadmap
from agents.agent.skill_gap import normalize_skills
from agents.errors import InvalidLLMOutput, TransientError, UserFacingError, is_transient
from agents.results import build_result
from agents.services import extract_text_from_pdf_bytes
from agents.utils import clean_text, safe_json_parse
from conftest import PROFILE, make_pdf


def http_error(status):
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(response=response)


def test_safe_json_parse_handles_wrapped_json():
    assert safe_json_parse('Sure! {"a": [1, 2]} hope that helps') == {"a": [1, 2]}
    assert safe_json_parse("no json here") is None
    assert safe_json_parse("") is None


def test_clean_text_removes_html():
    assert clean_text("<strong>Data</strong> &amp; <em>AI</em>\n Engineer") == "Data & AI Engineer"
    assert clean_text(None) == ""


@pytest.mark.parametrize("exc, expected", [
    (TransientError("x"), True),
    (requests.ConnectionError(), True),
    (requests.Timeout(), True),
    (http_error(429), True),
    (http_error(503), True),
    (http_error(401), False),
    (UserFacingError("bad resume"), False),
    (InvalidLLMOutput("bad json"), False),
    (RuntimeError("bug"), False),
])
def test_is_transient(exc, expected):
    assert is_transient(exc) is expected


def test_search_queries_go_from_specific_to_broad():
    assert search_queries(PROFILE) == ["Data Analyst Python", "Data Analyst", "Python SQL", "Python"]
    assert search_queries({"skills": ["Go"]}) == ["Go"]
    assert search_queries({}) == []


def test_dedupe_jobs():
    jobs = [
        {"title": "Data Analyst", "company": "Acme", "description": "a"},
        {"title": "data analyst ", "company": "ACME", "description": "b"},
        {"title": "No Description", "company": "Acme", "description": ""},
        {"title": "Engineer", "company": "Acme", "description": "c"},
    ]
    assert [job["description"] for job in dedupe_jobs(jobs)] == ["a", "c"]


def test_profile_text_is_short_structured_profile():
    text = profile_text(PROFILE)
    assert text.startswith("Data Analyst")
    assert "Skills: Python, SQL, Excel" in text


def test_normalize_skills_drops_known_and_duplicate_skills():
    assert normalize_skills(["Docker", "python", "docker ", 5, ""], ["Python"]) == ["docker"]
    assert normalize_skills("not a list") == []


def test_normalize_selection():
    assert normalize_selection([2, 2, 9, True, "1", 0], {0, 1, 2}) == [2, 0]
    assert normalize_selection(None, {0}) == []


def test_validate_roadmap():
    phases = validate_roadmap([{"phase": "Week 1", "focus": "docker", "tasks": ["x"]}, "junk", {"tasks": []}])
    assert phases == [{"phase": "Week 1", "focus": ["docker"], "tasks": ["x"]}]
    with pytest.raises(InvalidLLMOutput):
        validate_roadmap([])
    assert len(fallback_roadmap(["a", "b", "c", "d", "e", "f"])) == 5


def test_template_cover_letter_uses_resume_details():
    job = {"title": "Data Analyst", "company": "Acme", "description": "Needs SQL and Tableau"}
    letter = template_cover_letter(job, PROFILE, ["tableau"])
    assert "Acme" in letter and "SQL" in letter and "tableau" in letter
    assert letter.endswith("Kind regards,\nTest Candidate")

    anonymous = template_cover_letter(job, {**PROFILE, "name": ""}, [])
    assert anonymous.endswith("Kind regards,")


def test_build_result_sorts_by_job_and_trims_descriptions():
    values = {
        "parsed_resume": PROFILE,
        "ranked_jobs": [{"id": 0, "title": "A", "description": "x" * 1000}],
        "skill_gaps": [{"job_id": 1}, {"job_id": 0}],
        "roadmaps": [],
    }
    result = build_result(values)
    assert len(result["top_jobs"][0]["description"]) == 400
    assert [gap["job_id"] for gap in result["skill_gaps"]] == [0, 1]
    assert result["cover_letters"] == []


def test_extract_text_from_pdf_bytes():
    assert "Python developer" in extract_text_from_pdf_bytes(make_pdf("Python developer"))
    with pytest.raises(UserFacingError):
        extract_text_from_pdf_bytes(b"not a pdf")
    with pytest.raises(UserFacingError):
        extract_text_from_pdf_bytes(b"")
    with pytest.raises(UserFacingError, match="no readable text"):
        extract_text_from_pdf_bytes(make_pdf(""))


def test_fallback_tailoring_generates_ats_and_bullets():
    job = {"title": "Data Analyst", "company": "Acme", "description": "Needs Python and SQL"}
    res = fallback_tailoring(job, PROFILE, ["tableau"])
    assert 40 <= res["ats_score"] <= 100
    assert "Python" in res["matched_keywords"] or "SQL" in res["matched_keywords"]
    assert len(res["tailored_bullet_points"]) >= 1
    assert "Data Analyst" in res["tailored_summary"]
