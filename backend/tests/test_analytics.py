import os
from datetime import date

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.analytics import aggregate_cost
from app.main import app

_client = TestClient(app)


def test_project_cost_requires_auth():
    assert _client.get("/projects/some-id/cost").status_code in (401, 422)


def _run(id, *, day, cost, cache_hit=False, status="completed", pt=100, ct=20):
    return {
        "id": id,
        "status": status,
        "created_at": f"2026-08-{day:02d}T12:00:00+00:00",
        "cache_hit": cache_hit,
        "prompt_tokens": None if cost is None else pt,
        "completion_tokens": None if cost is None else ct,
        "cost_usd": cost,
    }


def _call(run_id, model, *, cost, pt=80, ct=15):
    return {
        "run_id": run_id,
        "node": "executor",
        "model": model,
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "cost_usd": cost,
    }


TODAY = date(2026, 8, 30)


def test_totals_sum_tokens_and_cost_and_count_cache_hits():
    runs = [
        _run("a", day=28, cost=0.010),
        _run("b", day=29, cost=0.020),
        _run("c", day=30, cost=0.0, cache_hit=True),
    ]
    out = aggregate_cost(runs, [], TODAY)
    assert out["totals"]["run_count"] == 3
    assert out["totals"]["cached_run_count"] == 1
    assert out["totals"]["cost_usd"] == 0.03
    assert out["totals"]["prompt_tokens"] == 300
    assert out["totals"]["runs_missing_cost"] == 0


def test_runs_missing_cost_are_counted_but_contribute_zero():
    runs = [_run("a", day=28, cost=0.010), _run("old", day=10, cost=None)]
    out = aggregate_cost(runs, [], TODAY)
    assert out["totals"]["run_count"] == 2
    assert out["totals"]["runs_missing_cost"] == 1
    assert out["totals"]["cost_usd"] == 0.01


def test_estimated_cache_savings_is_mean_noncached_cost_times_hits():
    runs = [
        _run("a", day=28, cost=0.010),
        _run("b", day=29, cost=0.030),
        _run("c", day=30, cost=0.0, cache_hit=True),
        _run("d", day=30, cost=0.0, cache_hit=True),
    ]
    out = aggregate_cost(runs, [], TODAY)
    # mean non-cached cost = 0.020; two cache hits -> 0.040
    assert out["totals"]["estimated_cache_savings_usd"] == 0.04


def test_estimated_cache_savings_zero_without_noncached_runs():
    runs = [_run("c", day=30, cost=0.0, cache_hit=True)]
    out = aggregate_cost(runs, [], TODAY)
    assert out["totals"]["estimated_cache_savings_usd"] == 0.0


def test_by_model_groups_llm_calls():
    runs = [_run("a", day=30, cost=0.02)]
    calls = [
        _call("a", "big", cost=0.015),
        _call("a", "cheap", cost=0.001),
        _call("a", "cheap", cost=0.002),
    ]
    out = aggregate_cost(runs, calls, TODAY)
    by = {m["model"]: m for m in out["by_model"]}
    assert by["cheap"]["calls"] == 2
    assert by["cheap"]["cost_usd"] == 0.003
    assert by["big"]["calls"] == 1


def test_daily_series_is_thirty_days_zero_filled_and_ordered():
    runs = [_run("a", day=30, cost=0.02), _run("b", day=30, cost=0.01, cache_hit=True)]
    out = aggregate_cost(runs, [], TODAY)
    assert len(out["daily"]) == 30
    assert out["daily"][0]["date"] == "2026-08-01"
    assert out["daily"][-1]["date"] == "2026-08-30"
    last = out["daily"][-1]
    assert last["run_count"] == 2
    assert last["cost_usd"] == 0.03
    assert last["cached_run_count"] == 1
    assert out["daily"][-2]["run_count"] == 0


def test_recent_runs_newest_first_capped_with_model_list():
    runs = [_run(str(i), day=1 + i, cost=0.001) for i in range(60)]
    calls = [_call("59", "big", cost=0.001), _call("59", "cheap", cost=0.0)]
    out = aggregate_cost(runs, calls, TODAY)
    assert len(out["recent_runs"]) == 50
    assert out["recent_runs"][0]["id"] == "59"
    assert out["recent_runs"][0]["models"] == ["big", "cheap"]
