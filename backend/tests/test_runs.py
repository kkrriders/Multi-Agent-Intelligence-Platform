import os
import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_run_requires_auth():
    response = client.post("/conversations/some-id/runs", json={"input": "hello"})
    assert response.status_code in (401, 422)


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost"
    or os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real Supabase project and GROQ_API_KEY required for this integration test",
)
def test_create_run_executes_graph_and_records_events(auth_headers, qdrant_available):
    project_response = client.post("/projects", json={"name": "Run Test Project"}, headers=auth_headers)
    project_id = project_response.json()["id"]

    conversation_response = client.post(
        f"/projects/{project_id}/conversations", json={"title": "Run Test Conversation"}, headers=auth_headers
    )
    conversation_id = conversation_response.json()["id"]

    run_response = client.post(
        f"/conversations/{conversation_id}/runs",
        json={"input": "Say the word 'pong' and nothing else."},
        headers=auth_headers,
    )
    assert run_response.status_code == 200
    run = run_response.json()
    assert run["status"] == "completed"
    assert run["output"]
    step_names = [e["step_name"] for e in run["events"]]
    assert step_names == ["run_started", "agent_responded"]

    get_response = client.get(f"/runs/{run['id']}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == run["id"]


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost"
    or os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real Supabase project and GROQ_API_KEY required for this integration test",
)
def test_second_run_in_conversation_recalls_first(auth_headers, qdrant_available):
    project_response = client.post("/projects", json={"name": "Recall Test Project"}, headers=auth_headers)
    project_id = project_response.json()["id"]

    conversation_response = client.post(
        f"/projects/{project_id}/conversations", json={"title": "Recall Test Conversation"}, headers=auth_headers
    )
    conversation_id = conversation_response.json()["id"]

    first = client.post(
        f"/conversations/{conversation_id}/runs",
        json={"input": "My favorite color is teal. Reply with just 'ok'."},
        headers=auth_headers,
    )
    assert first.status_code == 200

    second = client.post(
        f"/conversations/{conversation_id}/runs",
        json={"input": "What is my favorite color? Reply with just the color."},
        headers=auth_headers,
    )
    assert second.status_code == 200
    assert "teal" in second.json()["output"].lower()

    history_response = client.get(f"/conversations/{conversation_id}/runs", headers=auth_headers)
    assert history_response.status_code == 200
    assert len(history_response.json()) == 2


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost"
    or os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real Supabase project and GROQ_API_KEY required for this integration test",
)
def test_run_cites_a_retrieved_document(auth_headers, qdrant_available):
    project_response = client.post("/projects", json={"name": "Citation Test Project"}, headers=auth_headers)
    project_id = project_response.json()["id"]

    upload_response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("launch-notes.txt", b"The launch codeword for our rocket is Bluebird.", "text/plain")},
        headers=auth_headers,
    )
    assert upload_response.json()["status"] == "indexed"

    conversation_response = client.post(
        f"/projects/{project_id}/conversations", json={"title": "Citation Test Conversation"}, headers=auth_headers
    )
    conversation_id = conversation_response.json()["id"]

    run_response = client.post(
        f"/conversations/{conversation_id}/runs",
        json={"input": "What is the launch codeword? Reply with just the word."},
        headers=auth_headers,
    )
    assert run_response.status_code == 200
    run = run_response.json()
    assert "bluebird" in run["output"].lower()
    assert any(c["filename"] == "launch-notes.txt" for c in run["citations"])
    step_names = [e["step_name"] for e in run["events"]]
    assert "retrieval_performed" in step_names


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost"
    or os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real Supabase project and GROQ_API_KEY required for this integration test",
)
def test_run_never_cites_a_document_from_a_different_project(auth_headers, qdrant_available):
    project_a = client.post("/projects", json={"name": "Isolation Project A"}, headers=auth_headers).json()
    client.post(
        f"/projects/{project_a['id']}/documents",
        files={"file": ("secret.txt", b"The launch codeword for our rocket is Bluebird.", "text/plain")},
        headers=auth_headers,
    )

    project_b = client.post("/projects", json={"name": "Isolation Project B"}, headers=auth_headers).json()
    conversation_b = client.post(
        f"/projects/{project_b['id']}/conversations", json={"title": "Isolation Conversation"}, headers=auth_headers
    ).json()

    run_response = client.post(
        f"/conversations/{conversation_b['id']}/runs",
        json={"input": "What is the launch codeword? Reply with just the word, or 'unknown' if you don't know."},
        headers=auth_headers,
    )
    assert run_response.status_code == 200
    assert not any(c["filename"] == "secret.txt" for c in run_response.json()["citations"])
