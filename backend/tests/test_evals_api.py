import os

import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_routes_require_auth():
    assert client.get("/projects/x/eval-datasets").status_code in (401, 422)
    assert client.post("/projects/x/eval-datasets", json={"name": "n", "items": []}).status_code in (401, 422)
    assert client.get("/eval-datasets/x").status_code in (401, 422)
    assert client.post("/eval-datasets/x/run").status_code in (401, 422)
    assert client.get("/eval-datasets/x/runs").status_code in (401, 422)


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost"
    or os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real Supabase project and GROQ_API_KEY required",
)
def test_dataset_create_run_and_history(auth_headers):
    pid = client.post("/projects", json={"name": "Eval"}, headers=auth_headers).json()["id"]

    empty = client.post(f"/projects/{pid}/eval-datasets", json={"name": "d0", "items": []}, headers=auth_headers)
    assert empty.status_code == 400
    toobig = client.post(
        f"/projects/{pid}/eval-datasets",
        json={"name": "d1", "items": [{"input": "x", "expected": "y"}] * 21},
        headers=auth_headers,
    )
    assert toobig.status_code == 400

    ds = client.post(
        f"/projects/{pid}/eval-datasets",
        json={
            "name": "basics",
            "items": [
                {"input": "What is 2 + 2? Reply with just the number.", "expected": "4"},
                {"input": "Capital of France? One word.", "expected": "Paris"},
            ],
        },
        headers=auth_headers,
    ).json()
    assert ds["item_count"] == 2 and len(ds["items"]) == 2

    run = client.post(f"/eval-datasets/{ds['id']}/run", headers=auth_headers)
    assert run.status_code == 200
    body = run.json()
    for k in ("accuracy", "hallucination_rate", "mean_score"):
        assert 0.0 <= body[k] <= 1.0
    assert len(body["results"]) == 2
    assert all("output" in r and "score" in r for r in body["results"])

    runs = client.get(f"/eval-datasets/{ds['id']}/runs", headers=auth_headers).json()
    assert len(runs) >= 1 and runs[0]["item_count"] == 2

    listed = client.get(f"/projects/{pid}/eval-datasets", headers=auth_headers).json()
    row = next(x for x in listed if x["id"] == ds["id"])
    assert row["latest_run"] is not None and row["item_count"] == 2
