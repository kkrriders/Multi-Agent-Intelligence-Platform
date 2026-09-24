from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection, text

from app.db import get_db, maybe_one, one, rows
from app.models import (
    PromptTemplateCreate,
    PromptTemplateOut,
    PromptTemplateUpdate,
    PromptTemplateVersionOut,
)
from app.prompts import extract_variables

router = APIRouter(tags=["prompts"])


def _latest(conn: Connection, template_id: str):
    return maybe_one(
        conn.execute(
            text(
                "select * from prompt_template_versions where template_id = :t "
                "order by version desc limit 1"
            ),
            {"t": template_id},
        )
    )


def _version_count(conn: Connection, template_id: str) -> int:
    return conn.execute(
        text("select count(*) from prompt_template_versions where template_id = :t"), {"t": template_id}
    ).scalar_one()


@router.post("/projects/{project_id}/prompt-templates", response_model=PromptTemplateOut)
def create_template(project_id: str, body: PromptTemplateCreate, conn: Connection = Depends(get_db)):
    existing = maybe_one(
        conn.execute(
            text("select id from prompt_templates where project_id = :p and name = :n"),
            {"p": project_id, "n": body.name},
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail="A template with that name already exists")
    template = one(
        conn.execute(
            text("insert into prompt_templates (project_id, name) values (:p, :n) returning *"),
            {"p": project_id, "n": body.name},
        )
    )
    version = one(
        conn.execute(
            text(
                "insert into prompt_template_versions (template_id, version, body) "
                "values (:t, 1, :b) returning *"
            ),
            {"t": template["id"], "b": body.body},
        )
    )
    return {
        "id": template["id"],
        "name": template["name"],
        "version": 1,
        "body": version["body"],
        "variables": extract_variables(version["body"]),
        "version_count": 1,
        "created_at": template["created_at"],
    }


@router.get("/projects/{project_id}/prompt-templates", response_model=list[PromptTemplateOut])
def list_templates(project_id: str, conn: Connection = Depends(get_db)):
    templates = rows(
        conn.execute(
            text("select * from prompt_templates where project_id = :p order by created_at desc"),
            {"p": project_id},
        )
    )
    out = []
    for template in templates:
        latest = _latest(conn, template["id"])
        if not latest:
            continue
        out.append(
            {
                "id": template["id"],
                "name": template["name"],
                "version": latest["version"],
                "body": latest["body"],
                "variables": extract_variables(latest["body"]),
                "version_count": _version_count(conn, template["id"]),
                "created_at": template["created_at"],
            }
        )
    return out


@router.get("/prompt-templates/{template_id}/versions", response_model=list[PromptTemplateVersionOut])
def list_versions(template_id: str, conn: Connection = Depends(get_db)):
    versions = rows(
        conn.execute(
            text("select * from prompt_template_versions where template_id = :t order by version desc"),
            {"t": template_id},
        )
    )
    if not versions:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    return [{**r, "variables": extract_variables(r["body"])} for r in versions]


@router.put("/prompt-templates/{template_id}", response_model=PromptTemplateVersionOut)
def add_version(template_id: str, body: PromptTemplateUpdate, conn: Connection = Depends(get_db)):
    latest = _latest(conn, template_id)
    if not latest:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    new = one(
        conn.execute(
            text(
                "insert into prompt_template_versions (template_id, version, body) "
                "values (:t, :v, :b) returning *"
            ),
            {"t": template_id, "v": latest["version"] + 1, "b": body.body},
        )
    )
    return {**new, "variables": extract_variables(new["body"])}
