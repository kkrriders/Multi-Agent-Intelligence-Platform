from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection, text

from app.analytics import aggregate_cost
from app.db import get_db, maybe_one, rows

router = APIRouter(tags=["analytics"])

_RUN_COLS = "id, status, created_at, cache_hit, prompt_tokens, completion_tokens, cost_usd"
_CALL_COLS = "run_id, node, model, prompt_tokens, completion_tokens, cost_usd"


@router.get("/projects/{project_id}/cost")
def project_cost(project_id: str, conn: Connection = Depends(get_db)):
    """Cost/token rollup for a project: totals, per-model, a 30-day daily
    series, and recent-run rows. Pure aggregation over runs + run_llm_calls
    (no response_model — the shape is covered by test_analytics.py)."""
    project = maybe_one(conn.execute(text("select id from projects where id = :i"), {"i": project_id}))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    today = datetime.now(timezone.utc).date()
    conv_ids = [
        c["id"]
        for c in rows(conn.execute(text("select id from conversations where project_id = :p"), {"p": project_id}))
    ]
    if not conv_ids:
        return aggregate_cost([], [], today)

    # _RUN_COLS / _CALL_COLS are module constants, never request data.
    runs = rows(
        conn.execute(
            text(f"select {_RUN_COLS} from runs where conversation_id = any(cast(:ids as uuid[]))"),
            {"ids": conv_ids},
        )
    )
    run_ids = [r["id"] for r in runs]
    calls = (
        rows(
            conn.execute(
                text(f"select {_CALL_COLS} from run_llm_calls where run_id = any(cast(:ids as uuid[]))"),
                {"ids": run_ids},
            )
        )
        if run_ids
        else []
    )
    return aggregate_cost(runs, calls, today)
