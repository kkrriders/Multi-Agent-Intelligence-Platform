from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import Connection, text

from app.auth import get_current_user
from app.config import settings
from app.db import get_db, maybe_one, one, rows
from app.models import AlertEventOut, AlertRuleCreate, AlertRuleOut, AlertRuleUpdate, LimitsOut

router = APIRouter(tags=["alerts"])

# Columns a PATCH may set — the SET clause is built only from this whitelist.
_PATCHABLE = ("threshold", "window_n", "webhook_url", "enabled")


@router.get("/config/limits", response_model=LimitsOut)
def get_limits(user: dict = Depends(get_current_user)):
    return {
        "run_rate_limit_per_min": settings.run_rate_limit_per_min,
        "deploy_api_enabled": settings.enable_deploy_api,
    }


def _project_or_404(conn: Connection, project_id: str):
    if not maybe_one(conn.execute(text("select id from projects where id = :i"), {"i": project_id})):
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/projects/{project_id}/alert-rules", response_model=list[AlertRuleOut])
def list_alert_rules(project_id: str, conn: Connection = Depends(get_db)):
    _project_or_404(conn, project_id)
    return rows(
        conn.execute(
            text("select * from alert_rules where project_id = :p order by kind"), {"p": project_id}
        )
    )


@router.post("/projects/{project_id}/alert-rules", response_model=AlertRuleOut)
def upsert_alert_rule(project_id: str, body: AlertRuleCreate, conn: Connection = Depends(get_db)):
    _project_or_404(conn, project_id)
    return one(
        conn.execute(
            text(
                "insert into alert_rules (project_id, kind, threshold, window_n, webhook_url, enabled) "
                "values (:p, :k, :t, :w, :u, true) "
                "on conflict (project_id, kind) do update set threshold = excluded.threshold, "
                "window_n = excluded.window_n, webhook_url = excluded.webhook_url, "
                "enabled = excluded.enabled returning *"
            ),
            {
                "p": project_id,
                "k": body.kind,
                "t": body.threshold,
                "w": body.window_n,
                "u": body.webhook_url,
            },
        )
    )


@router.patch("/projects/{project_id}/alert-rules/{rule_id}", response_model=AlertRuleOut)
def update_alert_rule(
    project_id: str, rule_id: str, body: AlertRuleUpdate, conn: Connection = Depends(get_db)
):
    _project_or_404(conn, project_id)
    patch = {k: v for k, v in body.model_dump().items() if v is not None and k in _PATCHABLE}
    if not patch:
        raise HTTPException(status_code=422, detail="no fields to update")
    assignments = ", ".join(f"{col} = :{col}" for col in patch)
    updated = maybe_one(
        conn.execute(
            text(f"update alert_rules set {assignments} where id = :rule_id and project_id = :pid returning *"),
            {**patch, "rule_id": rule_id, "pid": project_id},
        )
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return updated


@router.delete("/projects/{project_id}/alert-rules/{rule_id}", status_code=204)
def delete_alert_rule(project_id: str, rule_id: str, conn: Connection = Depends(get_db)):
    _project_or_404(conn, project_id)
    conn.execute(
        text("delete from alert_rules where id = :r and project_id = :p"), {"r": rule_id, "p": project_id}
    )
    return Response(status_code=204)


@router.get("/projects/{project_id}/alert-events", response_model=list[AlertEventOut])
def list_alert_events(project_id: str, limit: int = 100, conn: Connection = Depends(get_db)):
    _project_or_404(conn, project_id)
    return rows(
        conn.execute(
            text("select * from alert_events where project_id = :p order by created_at desc limit :n"),
            {"p": project_id, "n": min(limit, 500)},
        )
    )
