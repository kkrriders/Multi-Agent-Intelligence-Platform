from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.db import fetch_maybe_one, get_user_client
from app.models import GuardrailEventOut, GuardrailPolicyOut, GuardrailPolicyUpdate

router = APIRouter(tags=["guardrails"])

POLICY_KINDS = ("input_constraint", "output_constraint")


@router.get("/projects/{project_id}/guardrail-policies", response_model=list[GuardrailPolicyOut])
def list_policies(project_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    rows = client.table("guardrail_policies").select("*").eq("project_id", project_id).execute().data
    by_kind = {r["kind"]: r for r in rows}
    return [
        by_kind.get(kind, {"id": None, "kind": kind, "enabled": False, "config": {}, "created_at": None})
        for kind in POLICY_KINDS
    ]


@router.put("/projects/{project_id}/guardrail-policies/{kind}", response_model=GuardrailPolicyOut)
def put_policy(project_id: str, kind: str, body: GuardrailPolicyUpdate, user: dict = Depends(get_current_user)):
    if kind not in POLICY_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown policy kind: {kind}")
    client = get_user_client(user["token"])
    existing = fetch_maybe_one(
        client.table("guardrail_policies").select("*").eq("project_id", project_id).eq("kind", kind)
    )
    payload = {
        "project_id": project_id,
        "kind": kind,
        "enabled": body.enabled if body.enabled is not None else (existing["enabled"] if existing else True),
        "config": body.config if body.config is not None else (existing["config"] if existing else {}),
    }
    if existing:
        return client.table("guardrail_policies").update(payload).eq("id", existing["id"]).execute().data[0]
    return client.table("guardrail_policies").insert(payload).execute().data[0]


@router.get("/projects/{project_id}/guardrail-events", response_model=list[GuardrailEventOut])
def list_events(project_id: str, limit: int = 50, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    return (
        client.table("guardrail_events")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(min(limit, 200))
        .execute()
        .data
    )
