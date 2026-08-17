import os
import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_conversation_requires_auth():
    response = client.post("/projects/some-id/conversations", json={})
    assert response.status_code in (401, 422)


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost",
    reason="Real Supabase project required for this integration test",
)
def test_create_and_list_conversations(auth_headers):
    project_response = client.post("/projects", json={"name": "Conversation Test Project"}, headers=auth_headers)
    project_id = project_response.json()["id"]

    create_response = client.post(
        f"/projects/{project_id}/conversations", json={"title": "First thread"}, headers=auth_headers
    )
    assert create_response.status_code == 200
    conversation = create_response.json()
    assert conversation["title"] == "First thread"

    list_response = client.get(f"/projects/{project_id}/conversations", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(c["id"] == conversation["id"] for c in list_response.json())
