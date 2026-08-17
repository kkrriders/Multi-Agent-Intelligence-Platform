import os
import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_search_memory_requires_auth():
    response = client.get("/projects/some-id/memories/search", params={"q": "hello"})
    assert response.status_code in (401, 422)


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost"
    or os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real Supabase project and GROQ_API_KEY required for this integration test",
)
def test_search_finds_earlier_turn_across_conversations(auth_headers, qdrant_available):
    project_response = client.post("/projects", json={"name": "Search Test Project"}, headers=auth_headers)
    project_id = project_response.json()["id"]

    conversation_a = client.post(
        f"/projects/{project_id}/conversations", json={"title": "Thread A"}, headers=auth_headers
    ).json()
    client.post(
        f"/conversations/{conversation_a['id']}/runs",
        json={"input": "The launch codeword for our rocket is Bluebird. Reply 'ok'."},
        headers=auth_headers,
    )

    client.post(f"/projects/{project_id}/conversations", json={"title": "Thread B"}, headers=auth_headers)

    search_response = client.get(
        f"/projects/{project_id}/memories/search",
        params={"q": "rocket launch codeword"},
        headers=auth_headers,
    )
    assert search_response.status_code == 200
    results = search_response.json()
    assert any("Bluebird" in r["input"] for r in results)
    assert all(r["project_id"] == project_id for r in results)


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost",
    reason="Real Supabase project required for this integration test",
)
def test_search_memory_requires_project_ownership(auth_headers):
    response = client.get(
        "/projects/00000000-0000-0000-0000-000000000000/memories/search",
        params={"q": "hello"},
        headers=auth_headers,
    )
    assert response.status_code == 404
