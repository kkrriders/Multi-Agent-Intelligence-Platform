import os
from datetime import date

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://maip_app:x@localhost:5433/maip")
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.alerts import daily_spend, error_rate, observed_for, p95_latency_ms
from app.db import one, rows
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


def _run(status="completed", *, day=30, cost: float | None = 0.01):
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


# ---- evaluate_project_alerts against real Postgres ----


def _seed_project(conn, *, kind, threshold, window_n, webhook_url, run_statuses):
    project = one(conn.execute(text("insert into projects (name) values ('alerts') returning *")))
    conv = one(
        conn.execute(
            text("insert into conversations (project_id) values (:p) returning id"), {"p": project["id"]}
        )
    )
    conn.execute(
        text(
            "insert into alert_rules (project_id, kind, threshold, window_n, webhook_url) "
            "values (:p, :k, :t, :w, :u)"
        ),
        {"p": project["id"], "k": kind, "t": threshold, "w": window_n, "u": webhook_url},
    )
    for i, status in enumerate(run_statuses):
        conn.execute(
            text(
                "insert into runs (project_id, conversation_id, status, input, cost_usd, created_at) "
                "values (:p, :c, :s, 'q', 0, now() - make_interval(secs => :age))"
            ),
            {"p": project["id"], "c": conv["id"], "s": status, "age": i * 60},
        )
    return project["id"]


def _alert_events(conn, project_id):
    return rows(conn.execute(text("select * from alert_events where project_id = :p"), {"p": project_id}))


def test_evaluate_writes_event_and_fires_webhook_on_breach(monkeypatch, user_db):
    from app import alerts

    _, conn = user_db
    posted = []
    monkeypatch.setattr(alerts.httpx, "post", lambda url, **k: posted.append((url, k)))
    pid = _seed_project(
        conn, kind="error_rate", threshold=0.0, window_n=2,
        webhook_url="https://hook.example/x", run_statuses=["failed", "completed"],
    )

    alerts.evaluate_project_alerts(conn, pid)

    events = _alert_events(conn, pid)
    assert len(events) == 1
    assert events[0]["kind"] == "error_rate" and events[0]["observed"] == 0.5
    assert posted and posted[0][0] == "https://hook.example/x"


def test_evaluate_is_fail_open_when_webhook_raises(monkeypatch, user_db):
    from app import alerts

    _, conn = user_db

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(alerts.httpx, "post", boom)
    pid = _seed_project(
        conn, kind="error_rate", threshold=0.0, window_n=1,
        webhook_url="https://hook.example/x", run_statuses=["blocked"],
    )

    alerts.evaluate_project_alerts(conn, pid)  # must not raise

    assert len(_alert_events(conn, pid)) == 1


def test_evaluate_no_rules_is_a_noop(user_db):
    from app import alerts

    _, conn = user_db
    project = one(conn.execute(text("insert into projects (name) values ('no rules') returning *")))
    conv = one(
        conn.execute(
            text("insert into conversations (project_id) values (:p) returning id"), {"p": project["id"]}
        )
    )
    conn.execute(
        text(
            "insert into runs (project_id, conversation_id, status, input, cost_usd) "
            "values (:p, :c, 'failed', 'q', 0)"
        ),
        {"p": project["id"], "c": conv["id"]},
    )

    alerts.evaluate_project_alerts(conn, project["id"])

    assert _alert_events(conn, project["id"]) == []


def test_record_rate_limit_event_writes_row(user_db):
    from app import alerts

    _, conn = user_db
    project = one(conn.execute(text("insert into projects (name) values ('rl') returning *")))

    alerts.record_rate_limit_event(conn, project["id"], 20)

    events = _alert_events(conn, project["id"])
    assert len(events) == 1 and events[0]["kind"] == "rate_limit" and events[0]["detail"]["limit"] == 20
