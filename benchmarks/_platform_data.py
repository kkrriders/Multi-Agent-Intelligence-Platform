"""Shared data-fetch helper for the benchmarks/*_report.py scripts.

Reads straight from the local Postgres (docker compose up -d postgres;
DATABASE_URL in .env), acting as a dedicated benchmark user so RLS still applies.
The user (BENCH_USER_EMAIL, default bench@local.dev) is created on first use with
an unusable password hash: it can never log in, it only exists to own rows.
"""
import os
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import text  # noqa: E402

from app.db import engine, maybe_one, rows, user_conn  # noqa: E402

BENCH_EMAIL = os.environ.get("BENCH_USER_EMAIL", "bench@local.dev")

_RUN_COLS = "id, project_id, conversation_id, status, created_at, cache_hit, prompt_tokens, completion_tokens, cost_usd"
_CALL_COLS = "run_id, node, model, prompt_tokens, completion_tokens, cost_usd"


@contextmanager
def bench_conn():
    """RLS-scoped connection acting as the benchmark user (created if missing)."""
    try:
        with engine.connect() as c:
            c.execute(
                text(
                    "insert into auth.users (email, password_hash) values (:e, 'x') "
                    "on conflict (email) do nothing"
                ),
                {"e": BENCH_EMAIL},
            )
            user = maybe_one(c.execute(text("select id from auth.users where email = :e"), {"e": BENCH_EMAIL}))
    except Exception as exc:  # noqa: BLE001 - surface as a clean CLI exit, callers may catch SystemExit
        raise SystemExit(f"Postgres not reachable ({exc.__class__.__name__}); start it and set DATABASE_URL.")
    with user_conn(user["id"]) as conn:
        yield conn


def _ids(conn, sql: str, ids: list[str]) -> list[dict]:
    # `sql` is a constant from this module, never request data.
    return rows(conn.execute(text(sql), {"ids": ids}))


def fetch_all(conn) -> dict:
    """All runs/run_llm_calls/run_events/guardrail_events across every project
    the benchmark user can see (RLS-scoped) — not just one hardcoded project."""
    project_ids = [p["id"] for p in rows(conn.execute(text("select id from projects")))]
    conv_ids = [c["id"] for c in rows(conn.execute(text("select id from conversations")))]

    all_runs = (
        _ids(conn, f"select {_RUN_COLS} from runs where conversation_id = any(cast(:ids as uuid[]))", conv_ids)
        if conv_ids
        else []
    )
    run_ids = [r["id"] for r in all_runs]

    calls = (
        _ids(conn, f"select {_CALL_COLS} from run_llm_calls where run_id = any(cast(:ids as uuid[]))", run_ids)
        if run_ids
        else []
    )
    events = (
        _ids(conn, "select * from run_events where run_id = any(cast(:ids as uuid[])) order by created_at", run_ids)
        if run_ids
        else []
    )
    guardrails = (
        _ids(conn, "select * from guardrail_events where run_id = any(cast(:ids as uuid[])) order by created_at", run_ids)
        if run_ids
        else []
    )
    return {"projects": project_ids, "runs": all_runs, "calls": calls, "events": events, "guardrails": guardrails}


def load() -> dict:
    with bench_conn() as conn:
        return fetch_all(conn)


if __name__ == "__main__":
    data = load()
    print(
        f"projects={len(data['projects'])} runs={len(data['runs'])} "
        f"llm_calls={len(data['calls'])} run_events={len(data['events'])} "
        f"guardrail_events={len(data['guardrails'])}"
    )
