import os

import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_routes_require_auth():
    assert client.get("/projects/x/prompt-templates").status_code in (401, 422)
    assert client.post("/projects/x/prompt-templates", json={"name": "n", "body": "b"}).status_code in (401, 422)
    assert client.get("/prompt-templates/x/versions").status_code in (401, 422)
    assert client.put("/prompt-templates/x", json={"body": "b"}).status_code in (401, 422)


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost",
    reason="Real Supabase project required",
)
def test_template_create_version_and_list(auth_headers):
    pid = client.post("/projects", json={"name": "PM"}, headers=auth_headers).json()["id"]

    created = client.post(
        f"/projects/{pid}/prompt-templates",
        json={"name": "greet", "body": "Say hi to {{name}} about {{topic}}."},
        headers=auth_headers,
    )
    assert created.status_code == 200
    t = created.json()
    assert t["version"] == 1 and t["version_count"] == 1
    assert t["variables"] == ["name", "topic"]

    dup = client.post(
        f"/projects/{pid}/prompt-templates", json={"name": "greet", "body": "x"}, headers=auth_headers
    )
    assert dup.status_code == 400

    bumped = client.put(f"/prompt-templates/{t['id']}", json={"body": "Hi {{name}}!"}, headers=auth_headers)
    assert bumped.status_code == 200 and bumped.json()["version"] == 2
    assert bumped.json()["variables"] == ["name"]

    versions = client.get(f"/prompt-templates/{t['id']}/versions", headers=auth_headers).json()
    assert [v["version"] for v in versions] == [2, 1]

    listed = client.get(f"/projects/{pid}/prompt-templates", headers=auth_headers).json()
    row = next(x for x in listed if x["id"] == t["id"])
    assert row["version"] == 2 and row["version_count"] == 2 and row["body"] == "Hi {{name}}!"
