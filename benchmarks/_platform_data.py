"""Shared data-fetch helper for the benchmarks/*_report.py scripts.

Auth follows the repo's own documented convention (CLAUDE.md "Commands",
backend/tests/conftest.py): a signed-in test user's access token in
SUPABASE_TEST_USER_TOKEN. No credentials live in this file — mint the token
externally (e.g. AIRRA's labs/integration/run-traffic.ps1 already does the
password-grant sign-in against this same shared Supabase project and prints
one) and export it before running any report script.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.db import get_user_client, rows  # noqa: E402

_RUN_COLS = "id, project_id, conversation_id, status, created_at, cache_hit, prompt_tokens, completion_tokens, cost_usd"
_CALL_COLS = "run_id, node, model, prompt_tokens, completion_tokens, cost_usd"


def get_token() -> str:
    token = os.environ.get("SUPABASE_TEST_USER_TOKEN")
    if not token:
        raise SystemExit(
            "SUPABASE_TEST_USER_TOKEN not set. Sign in a real Supabase user and export the "
            "access_token — see CLAUDE.md 'Commands' and backend/tests/conftest.py for the "
            "convention this repo already uses for gated integration tests."
        )
    return token


def fetch_all(client) -> dict:
    """All runs/run_llm_calls/run_events/guardrail_events across every project
    this user can see (RLS-scoped) — not just one hardcoded project."""
    project_ids = [p["id"] for p in rows(client.table("projects").select("id").execute())]
    conv_ids: list[str] = []
    for pid in project_ids:
        conv_ids += [
            c["id"]
            for c in rows(client.table("conversations").select("id").eq("project_id", pid).execute())
        ]

    all_runs = (
        rows(client.table("runs").select(_RUN_COLS).in_("conversation_id", conv_ids).execute())
        if conv_ids
        else []
    )
    run_ids = [r["id"] for r in all_runs]

    calls = (
        rows(client.table("run_llm_calls").select(_CALL_COLS).in_("run_id", run_ids).execute())
        if run_ids
        else []
    )
    events = (
        rows(client.table("run_events").select("*").in_("run_id", run_ids).order("created_at").execute())
        if run_ids
        else []
    )
    guardrails = (
        rows(client.table("guardrail_events").select("*").in_("run_id", run_ids).order("created_at").execute())
        if run_ids
        else []
    )
    return {"projects": project_ids, "runs": all_runs, "calls": calls, "events": events, "guardrails": guardrails}


def load() -> dict:
    client = get_user_client(get_token())
    return fetch_all(client)


if __name__ == "__main__":
    data = load()
    print(
        f"projects={len(data['projects'])} runs={len(data['runs'])} "
        f"llm_calls={len(data['calls'])} run_events={len(data['events'])} "
        f"guardrail_events={len(data['guardrails'])}"
    )
