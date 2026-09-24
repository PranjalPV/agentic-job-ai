import time

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from agents.config import Settings
from agents.graph.state import AgentContext
from agents.graph.workflow import build_cover_letter_graph, build_graph
from conftest import FAST_RETRY, FakeServices, make_pdf
from main import AppDeps, create_app

TOKENS = {"token-alice": "alice", "token-bob": "bob"}
ALICE = {"Authorization": "Bearer token-alice"}
BOB = {"Authorization": "Bearer token-bob"}


class Backend:
    def __init__(self):
        self.fake = FakeServices()
        self.files = {"alice/cv.pdf": make_pdf("Data analyst skilled in Python and SQL")}
        self.saved = []
        self.download_error = None
        self.rows = {}   # analysis id -> saved result (one row per analysis)
        self.deps = AppDeps(
            graph=build_graph(checkpointer=InMemorySaver(), retry_policy=FAST_RETRY),
            letter_graph=build_cover_letter_graph(FAST_RETRY),
            context=AgentContext(services=self.fake.as_services()),
            verify_token=TOKENS.get,
            download_resume=self.download,
            persist_result=self.persist_result,
        )

    def persist_result(self, user_id, path, thread_id, result):
        if thread_id not in self.rows:
            self.saved.append((user_id, path, result))   # a new row
        self.rows[thread_id] = result

    def download(self, path):
        if self.download_error:
            raise self.download_error
        return self.files[path]


@pytest.fixture
def backend():
    return Backend()


@pytest.fixture
def client(backend):
    with TestClient(create_app(deps=backend.deps, settings=Settings())) as client:
        yield client


def wait_for(client, thread_id, statuses, headers=ALICE, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/analyze/{thread_id}", headers=headers).json()
        if body["status"] in statuses:
            return body
        time.sleep(0.05)
    raise AssertionError(f"Timed out, last status: {body['status']}")


def start(client, path="alice/cv.pdf"):
    res = client.post("/analyze", json={"file_path": path}, headers=ALICE)
    assert res.status_code == 200, res.text
    return res.json()["thread_id"]


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "missing_settings": []}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": "token-alice"}])
def test_requires_valid_login(client, headers):
    assert client.post("/analyze", json={"file_path": "alice/cv.pdf"}, headers=headers).status_code == 401
    assert client.get("/analyze/some-id", headers=headers).status_code == 401


@pytest.mark.parametrize("path", ["bob/cv.pdf", "alice/../bob/cv.pdf", "cv.pdf"])
def test_cannot_analyze_other_users_files(client, path):
    assert client.post("/analyze", json={"file_path": path}, headers=ALICE).status_code == 403


def test_full_flow_with_job_selection(client, backend):
    thread_id = start(client)

    paused = wait_for(client, thread_id, {"awaiting_selection", "error"})
    assert paused["status"] == "awaiting_selection", paused
    assert len(paused["selection"]["jobs"]) == 5
    assert len(paused["result"]["skill_gaps"]) == 5
    assert any("Reading your resume" in message for message in paused["progress"])
    assert backend.saved == []

    # Other users can't see or control this analysis
    assert client.get(f"/analyze/{thread_id}", headers=BOB).status_code == 404
    assert client.post(f"/analyze/{thread_id}/select", json={"job_ids": [0]}, headers=BOB).status_code == 404

    assert client.post(f"/analyze/{thread_id}/select", json={"job_ids": [42]}, headers=ALICE).status_code == 422

    res = client.post(f"/analyze/{thread_id}/select", json={"job_ids": [0, 3]}, headers=ALICE)
    assert res.status_code == 200

    done = wait_for(client, thread_id, {"done", "error"})
    assert done["status"] == "done", done
    assert [letter["job_id"] for letter in done["result"]["cover_letters"]] == [0, 3]

    assert len(backend.saved) == 1
    user_id, path, result = backend.saved[0]
    assert (user_id, path) == ("alice", "alice/cv.pdf")
    assert len(result["top_jobs"]) == 5 and len(result["cover_letters"]) == 2

    # Selection only works while the graph is paused
    assert client.post(f"/analyze/{thread_id}/select", json={"job_ids": [1]}, headers=ALICE).status_code == 409


def test_unreadable_pdf_shows_clear_error(client, backend):
    backend.files["alice/cv.pdf"] = b"not a pdf"
    thread_id = start(client)

    body = wait_for(client, thread_id, {"error"})
    assert "valid PDF" in body["message"]
    assert body["can_resume"] is False
    assert client.post(f"/analyze/{thread_id}/resume", headers=ALICE).status_code == 409


def test_no_jobs_found_is_reported(client, backend):
    backend.fake.jobs_for_query = lambda source, query: []
    thread_id = start(client)

    body = wait_for(client, thread_id, {"error", "done"})
    assert body["status"] == "error"
    assert "No matching jobs" in body["message"]
    assert backend.saved == []


def test_failed_run_can_be_resumed(client, backend):
    backend.fake.failures[("parse_resume", None)] = [RuntimeError("Gemini outage")]
    thread_id = start(client)

    failed = wait_for(client, thread_id, {"error"})
    assert failed["message"].startswith("Something went wrong")
    assert failed["can_resume"] is True

    assert client.post(f"/analyze/{thread_id}/resume", headers=ALICE).status_code == 200
    resumed = wait_for(client, thread_id, {"awaiting_selection", "error"})
    assert resumed["status"] == "awaiting_selection"
    assert backend.fake.count("parse_resume") == 2


def test_unknown_analysis_is_not_found(client):
    assert client.get("/analyze/does-not-exist", headers=ALICE).status_code == 404


def test_more_cover_letters_after_the_analysis_finished(client, backend):
    thread_id = start(client)
    wait_for(client, thread_id, {"awaiting_selection"})

    client.post(f"/analyze/{thread_id}/select", json={"job_ids": [0]}, headers=ALICE)
    done = wait_for(client, thread_id, {"done", "error"})
    assert [letter["job_id"] for letter in done["result"]["cover_letters"]] == [0]
    assert len(backend.saved) == 1

    # Ask for two more letters for jobs that don't have one yet
    res = client.post(f"/analyze/{thread_id}/letters", json={"job_ids": [2, 3]}, headers=ALICE)
    assert res.status_code == 200, res.text
    assert res.json()["job_ids"] == [2, 3]

    done = wait_for(client, thread_id, {"done", "error"})
    assert done["status"] == "done"
    assert [letter["job_id"] for letter in done["result"]["cover_letters"]] == [0, 2, 3]
    assert backend.fake.count("write_letter") == 3

    # Saved into the same row rather than creating a second one
    assert len(backend.saved) == 1
    assert len(backend.rows) == 1
    saved_row = backend.rows[thread_id]
    assert saved_row["thread_id"] == thread_id
    assert [letter["job_id"] for letter in saved_row["cover_letters"]] == [0, 2, 3]


def test_more_letters_rejects_repeats_and_unknown_jobs(client):
    thread_id = start(client)
    wait_for(client, thread_id, {"awaiting_selection"})
    client.post(f"/analyze/{thread_id}/select", json={"job_ids": [1]}, headers=ALICE)
    wait_for(client, thread_id, {"done"})

    assert client.post(f"/analyze/{thread_id}/letters", json={"job_ids": [1]}, headers=ALICE).status_code == 422
    assert client.post(f"/analyze/{thread_id}/letters", json={"job_ids": [99]}, headers=ALICE).status_code == 422
    assert client.post(f"/analyze/{thread_id}/letters", json={"job_ids": [0]}, headers=BOB).status_code == 404


def test_more_letters_rejected_before_the_analysis_is_done(client):
    thread_id = start(client)
    wait_for(client, thread_id, {"awaiting_selection"})
    assert client.post(f"/analyze/{thread_id}/letters", json={"job_ids": [0]}, headers=ALICE).status_code == 409


def test_letters_after_a_restart_still_update_the_same_row(backend):
    """The saved row is found by analysis id, so a restart doesn't duplicate it."""
    with TestClient(create_app(deps=backend.deps, settings=Settings())) as client:
        thread_id = start(client)
        wait_for(client, thread_id, {"awaiting_selection"})
        client.post(f"/analyze/{thread_id}/select", json={"job_ids": [0]}, headers=ALICE)
        wait_for(client, thread_id, {"done"})

    # A new app instance: the checkpointer keeps the run, in-memory tracking is gone
    with TestClient(create_app(deps=backend.deps, settings=Settings())) as client:
        assert client.post(f"/analyze/{thread_id}/letters", json={"job_ids": [4]},
                           headers=ALICE).status_code == 200
        done = wait_for(client, thread_id, {"done", "error"})

    assert [letter["job_id"] for letter in done["result"]["cover_letters"]] == [0, 4]
    assert len(backend.rows) == 1
    assert [letter["job_id"] for letter in backend.rows[thread_id]["cover_letters"]] == [0, 4]
