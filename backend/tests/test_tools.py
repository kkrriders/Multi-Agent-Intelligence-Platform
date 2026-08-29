import os
import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_tool_requires_auth():
    response = client.post("/projects/some-id/tools", json={"name": "Echo", "type": "rest", "config": {}})
    assert response.status_code in (401, 422)


def test_invoke_tool_requires_auth():
    response = client.post("/tools/some-id/invoke", json={})
    assert response.status_code in (401, 422)


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost",
    reason="Real Supabase project required for this integration test",
)
def test_create_list_and_invoke_tool(auth_headers):
    project_response = client.post("/projects", json={"name": "Tool Test Project"}, headers=auth_headers)
    project_id = project_response.json()["id"]

    create_response = client.post(
        f"/projects/{project_id}/tools",
        # example.com is IANA-run and effectively never down; httpbin.org (the old
        # target) was a hobby host that 503'd/timed out and made this test flaky.
        # A real external GET returning 200 still proves the adapter works over the
        # network end to end, which is all this test asserts.
        json={"name": "Echo", "type": "rest", "config": {"url": "https://example.com", "method": "GET"}},
        headers=auth_headers,
    )
    assert create_response.status_code == 200
    tool = create_response.json()

    list_response = client.get(f"/projects/{project_id}/tools", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(t["id"] == tool["id"] for t in list_response.json())

    invoke_response = client.post(f"/tools/{tool['id']}/invoke", json={}, headers=auth_headers)
    assert invoke_response.status_code == 200
    assert invoke_response.json()["status"] == 200


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost",
    reason="Real Supabase project required for this integration test",
)
def test_invoke_nonexistent_tool_returns_404(auth_headers):
    response = client.post("/tools/00000000-0000-0000-0000-000000000000/invoke", json={}, headers=auth_headers)
    assert response.status_code == 404
