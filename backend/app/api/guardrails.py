import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection, text

from app.db import get_db, maybe_one, one, rows
from app.models import GuardrailEventOut, GuardrailPolicyOut, GuardrailPolicyUpdate

router = APIRouter(tags=["guardrails"])

POLICY_KINDS = ("input_constraint", "output_constraint")


@router.get("/projects/{project_id}/guardrail-policies", response_model=list[GuardrailPolicyOut])
def list_policies(project_id: str, conn: Connection = Depends(get_db)):
    policy_rows = rows(
        conn.execute(text("select * from guardrail_policies where project_id = :p"), {"p": project_id})
    )
    by_kind = {r["kind"]: r for r in policy_rows}
    return [
        by_kind.get(kind, {"id": None, "kind": kind, "enabled": False, "config": {}, "created_at": None})
        for kind in POLICY_KINDS
    ]


@router.put("/projects/{project_id}/guardrail-policies/{kind}", response_model=GuardrailPolicyOut)
def put_policy(project_id: str, kind: str, body: GuardrailPolicyUpdate, conn: Connection = Depends(get_db)):
    if kind not in POLICY_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown policy kind: {kind}")
    existing = maybe_one(
        conn.execute(
            text("select * from guardrail_policies where project_id = :p and kind = :k"),
            {"p": project_id, "k": kind},
        )
    )
    params = {
        "p": project_id,
        "k": kind,
        "e": body.enabled if body.enabled is not None else (existing["enabled"] if existing else True),
        "c": json.dumps(body.config if body.config is not None else (existing["config"] if existing else {})),
    }
    if existing:
        return one(
            conn.execute(
                text(
                    "update guardrail_policies set project_id = :p, kind = :k, enabled = :e, "
                    "config = cast(:c as jsonb) where id = :id returning *"
                ),
                {**params, "id": existing["id"]},
            )
        )
    return one(
        conn.execute(
            text(
                "insert into guardrail_policies (project_id, kind, enabled, config) "
                "values (:p, :k, :e, cast(:c as jsonb)) returning *"
            ),
            params,
        )
    )


@router.get("/projects/{project_id}/guardrail-events", response_model=list[GuardrailEventOut])
def list_events(project_id: str, limit: int = 50, conn: Connection = Depends(get_db)):
    return rows(
        conn.execute(
            text(
                "select * from guardrail_events where project_id = :p "
                "order by created_at desc limit :n"
            ),
            {"p": project_id, "n": min(limit, 200)},
        )
    )
