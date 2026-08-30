from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import get_current_user
from app.config import settings
from app.db import fetch_maybe_one, get_user_client
from app.models import AlertEventOut, AlertRuleCreate, AlertRuleOut, AlertRuleUpdate, LimitsOut

router = APIRouter(tags=["alerts"])


@router.get("/config/limits", response_model=LimitsOut)
def get_limits(user: dict = Depends(get_current_user)):
    return {
        "run_rate_limit_per_min": settings.run_rate_limit_per_min,
        "deploy_api_enabled": settings.enable_deploy_api,
    }


def _project_or_404(client, project_id: str):
    if not fetch_maybe_one(client.table("projects").select("id").eq("id", project_id)):
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/projects/{project_id}/alert-rules", response_model=list[AlertRuleOut])
def list_alert_rules(project_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    _project_or_404(client, project_id)
    return (
        client.table("alert_rules")
        .select("*")
        .eq("project_id", project_id)
        .order("kind")
        .execute()
        .data
    )


@router.post("/projects/{project_id}/alert-rules", response_model=AlertRuleOut)
def upsert_alert_rule(project_id: str, body: AlertRuleCreate, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    _project_or_404(client, project_id)
    row = (
        client.table("alert_rules")
        .upsert(
            {
                "project_id": project_id,
                "kind": body.kind,
                "threshold": body.threshold,
                "window_n": body.window_n,
                "webhook_url": body.webhook_url,
                "enabled": True,
            },
            on_conflict="project_id,kind",
        )
        .execute()
        .data[0]
    )
    return row


@router.patch("/projects/{project_id}/alert-rules/{rule_id}", response_model=AlertRuleOut)
def update_alert_rule(
    project_id: str, rule_id: str, body: AlertRuleUpdate, user: dict = Depends(get_current_user)
):
    client = get_user_client(user["token"])
    _project_or_404(client, project_id)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=422, detail="no fields to update")
    updated = (
        client.table("alert_rules")
        .update(patch)
        .eq("id", rule_id)
        .eq("project_id", project_id)
        .execute()
        .data
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return updated[0]


@router.delete("/projects/{project_id}/alert-rules/{rule_id}", status_code=204)
def delete_alert_rule(project_id: str, rule_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    _project_or_404(client, project_id)
    client.table("alert_rules").delete().eq("id", rule_id).eq("project_id", project_id).execute()
    return Response(status_code=204)


@router.get("/projects/{project_id}/alert-events", response_model=list[AlertEventOut])
def list_alert_events(project_id: str, limit: int = 100, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    _project_or_404(client, project_id)
    return (
        client.table("alert_events")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(min(limit, 500))
        .execute()
        .data
    )
