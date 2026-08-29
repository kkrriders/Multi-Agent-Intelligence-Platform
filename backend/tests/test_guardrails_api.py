import os

import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_policies_requires_auth():
    assert client.get("/projects/x/guardrail-policies").status_code in (401, 422)


def test_put_policy_requires_auth():
    assert client.put("/projects/x/guardrail-policies/input_constraint", json={"enabled": True}).status_code in (401, 422)


def test_list_events_requires_auth():
    assert client.get("/projects/x/guardrail-events").status_code in (401, 422)


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost",
    reason="Real Supabase project required",
)
def test_policy_roundtrip_and_synthetic_defaults(auth_headers):
    project = client.post("/projects", json={"name": "GR API"}, headers=auth_headers).json()
    pid = project["id"]

    listed = client.get(f"/projects/{pid}/guardrail-policies", headers=auth_headers).json()
    assert {p["kind"] for p in listed} == {"input_constraint", "output_constraint"}
    assert all(p["enabled"] is False and p["id"] is None for p in listed)

    put = client.put(
        f"/projects/{pid}/guardrail-policies/input_constraint",
        json={"enabled": True, "config": {"max_length": 100}},
        headers=auth_headers,
    )
    assert put.status_code == 200
    assert put.json()["enabled"] is True

    listed2 = client.get(f"/projects/{pid}/guardrail-policies", headers=auth_headers).json()
    ic = next(p for p in listed2 if p["kind"] == "input_constraint")
    assert ic["id"] is not None and ic["config"] == {"max_length": 100}

    bad = client.put(f"/projects/{pid}/guardrail-policies/nope", json={"enabled": True}, headers=auth_headers)
    assert bad.status_code == 400
