from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.analytics import aggregate_cost
from app.auth import get_current_user
from app.db import fetch_maybe_one, get_user_client

router = APIRouter(tags=["analytics"])

_RUN_COLS = "id, status, created_at, cache_hit, prompt_tokens, completion_tokens, cost_usd"
_CALL_COLS = "run_id, node, model, prompt_tokens, completion_tokens, cost_usd"


@router.get("/projects/{project_id}/cost")
def project_cost(project_id: str, user: dict = Depends(get_current_user)):
    """Cost/token rollup for a project: totals, per-model, a 30-day daily
    series, and recent-run rows. Pure aggregation over runs + run_llm_calls
    (no response_model — the shape is covered by test_analytics.py)."""
    client = get_user_client(user["token"])
    project = fetch_maybe_one(client.table("projects").select("id").eq("id", project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    today = datetime.now(timezone.utc).date()
    conv_ids = [
        c["id"]
        for c in client.table("conversations").select("id").eq("project_id", project_id).execute().data
    ]
    if not conv_ids:
        return aggregate_cost([], [], today)

    runs = client.table("runs").select(_RUN_COLS).in_("conversation_id", conv_ids).execute().data
    run_ids = [r["id"] for r in runs]
    calls = (
        client.table("run_llm_calls").select(_CALL_COLS).in_("run_id", run_ids).execute().data
        if run_ids
        else []
    )
    return aggregate_cost(runs, calls, today)
