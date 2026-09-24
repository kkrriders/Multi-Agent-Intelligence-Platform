import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://maip_app:x@localhost:5433/maip")
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_project_requires_auth():
    response = client.post("/projects", json={"name": "Test Project"})
    assert response.status_code in (401, 422)


def test_create_and_list_projects(auth_headers):
    create_response = client.post("/projects", json={"name": "Test Project"}, headers=auth_headers)
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["name"] == "Test Project"

    list_response = client.get("/projects", headers=auth_headers)
    assert list_response.status_code == 200
    names = [p["name"] for p in list_response.json()]
    assert "Test Project" in names
