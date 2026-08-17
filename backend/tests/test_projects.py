import os
import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_project_requires_auth():
    response = client.post("/projects", json={"name": "Test Project"})
    assert response.status_code in (401, 422)


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost",
    reason="Real Supabase project required for this integration test",
)
def test_create_and_list_projects(auth_headers):
    create_response = client.post("/projects", json={"name": "Test Project"}, headers=auth_headers)
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["name"] == "Test Project"

    list_response = client.get("/projects", headers=auth_headers)
    assert list_response.status_code == 200
    names = [p["name"] for p in list_response.json()]
    assert "Test Project" in names
