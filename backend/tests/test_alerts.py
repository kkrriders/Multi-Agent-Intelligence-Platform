import os
from datetime import date

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.alerts import daily_spend, error_rate, observed_for, p95_latency_ms
from app.main import app

_c = TestClient(app)


def test_alert_rule_routes_require_auth():
    assert _c.get("/projects/p/alert-rules").status_code in (401, 422)
    assert _c.post("/projects/p/alert-rules", json={"kind": "daily_spend", "threshold": 1}).status_code in (401, 422)
    assert _c.get("/projects/p/alert-events").status_code in (401, 422)
    assert _c.get("/config/limits").status_code in (401, 422)


def test_alert_rule_create_validates_kind_and_threshold():
    from app.models import AlertRuleCreate
    import pytest

    with pytest.raises(ValueError):
        AlertRuleCreate(kind="nonsense", threshold=1)
    with pytest.raises(ValueError):
        AlertRuleCreate(kind="error_rate", threshold=1.5)
    with pytest.raises(ValueError):
        AlertRuleCreate(kind="daily_spend", threshold=-1)
    AlertRuleCreate(kind="p95_latency", threshold=5000, window_n=10)  # ok

TODAY = date(2026, 8, 30)


def _run(status="completed", *, day=30, cost=0.01):
    return {
        "id": f"r{day}-{status}",
        "status": status,
        "created_at": f"2026-08-{day:02d}T12:00:00+00:00",
        "cost_usd": cost,
    }


def test_error_rate_counts_failed_and_blocked():
    runs = [_run("completed"), _run("failed"), _run("blocked"), _run("completed")]
    assert error_rate(runs) == 0.5


def test_error_rate_empty_is_zero():
    assert error_rate([]) == 0.0


def test_daily_spend_sums_only_todays_runs():
    runs = [_run(day=30, cost=0.02), _run(day=30, cost=0.03), _run(day=29, cost=1.0)]
    assert daily_spend(runs, TODAY) == 0.05


def test_daily_spend_handles_null_cost():
    runs = [_run(day=30, cost=None), _run(day=30, cost=0.04)]
    assert daily_spend(runs, TODAY) == 0.04


def test_p95_latency_nearest_rank_over_per_run_event_spans():
    # 3 runs: spans 1s, 2s, 10s -> p95 (nearest-rank) = the 10s run = 10000ms
    ev = {
        "a": [{"created_at": "2026-08-30T12:00:00+00:00"}, {"created_at": "2026-08-30T12:00:01+00:00"}],
        "b": [{"created_at": "2026-08-30T12:00:00+00:00"}, {"created_at": "2026-08-30T12:00:02+00:00"}],
        "c": [{"created_at": "2026-08-30T12:00:00+00:00"}, {"created_at": "2026-08-30T12:00:10+00:00"}],
    }
    assert p95_latency_ms(ev) == 10000.0


def test_p95_latency_ignores_runs_with_fewer_than_two_events():
    ev = {"a": [{"created_at": "2026-08-30T12:00:00+00:00"}]}
    assert p95_latency_ms(ev) == 0.0


def test_observed_for_dispatches_by_kind():
    runs = [_run("failed"), _run("completed")]
    assert observed_for("error_rate", runs, {}, TODAY) == 0.5
    assert observed_for("daily_spend", runs, {}, TODAY) == 0.02


# ---- evaluate_project_alerts with a fake Supabase client ----


class _FakeTable:
    def __init__(self, store, name):
        self.store, self.name, self._rows = store, name, list(store.get(name, []))

    def select(self, *a, **k):
        return self

    def eq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def in_(self, col, vals):
        self._rows = [r for r in self._rows if r.get(col) in vals]
        return self

    def execute(self):
        return type("R", (), {"data": self._rows, "count": len(self._rows)})()

    def insert(self, row):
        self.store.setdefault(self.name, []).append(row)
        return type("I", (), {"execute": lambda self=None: None})()


class _FakeClient:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _FakeTable(self.store, name)


def test_evaluate_writes_event_and_fires_webhook_on_breach(monkeypatch):
    from app import alerts

    posted = []
    monkeypatch.setattr(alerts.httpx, "post", lambda url, **k: posted.append((url, k)))

    store = {
        "alert_rules": [
            {"id": "rule1", "project_id": "p1", "kind": "error_rate", "threshold": 0.0,
             "window_n": 2, "webhook_url": "https://hook.example/x", "enabled": True}
        ],
        "runs": [
            {"id": "a", "project_id": "p1", "status": "failed", "created_at": "2026-08-30T12:00:00+00:00", "cost_usd": 0},
            {"id": "b", "project_id": "p1", "status": "completed", "created_at": "2026-08-30T11:00:00+00:00", "cost_usd": 0},
        ],
    }
    alerts.evaluate_project_alerts(_FakeClient(store), "p1", today=date(2026, 8, 30))

    events = store.get("alert_events", [])
    assert len(events) == 1
    assert events[0]["kind"] == "error_rate" and events[0]["observed"] == 0.5
    assert posted and posted[0][0] == "https://hook.example/x"


def test_evaluate_is_fail_open_when_webhook_raises(monkeypatch):
    from app import alerts

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(alerts.httpx, "post", boom)
    store = {
        "alert_rules": [
            {"id": "r", "project_id": "p1", "kind": "error_rate", "threshold": 0.0,
             "window_n": 1, "webhook_url": "https://hook.example/x", "enabled": True}
        ],
        "runs": [
            {"id": "a", "project_id": "p1", "status": "blocked", "created_at": "2026-08-30T12:00:00+00:00", "cost_usd": 0}
        ],
    }
    # must not raise
    alerts.evaluate_project_alerts(_FakeClient(store), "p1", today=date(2026, 8, 30))
    assert len(store.get("alert_events", [])) == 1


def test_evaluate_no_rules_is_a_noop():
    from app import alerts

    store = {"runs": [{"id": "a", "project_id": "p1", "status": "failed",
                       "created_at": "2026-08-30T12:00:00+00:00", "cost_usd": 0}]}
    alerts.evaluate_project_alerts(_FakeClient(store), "p1", today=date(2026, 8, 30))
    assert "alert_events" not in store
