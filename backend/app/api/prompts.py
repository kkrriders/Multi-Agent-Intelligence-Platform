from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.db import fetch_maybe_one, get_user_client, one_row, rows
from app.models import (
    PromptTemplateCreate,
    PromptTemplateOut,
    PromptTemplateUpdate,
    PromptTemplateVersionOut,
)
from app.prompts import extract_variables

router = APIRouter(tags=["prompts"])


def _latest(client, template_id: str):
    return fetch_maybe_one(
        client.table("prompt_template_versions")
        .select("*")
        .eq("template_id", template_id)
        .order("version", desc=True)
        .limit(1)
    )


def _version_count(client, template_id: str) -> int:
    return len(
        rows(client.table("prompt_template_versions").select("id").eq("template_id", template_id).execute())
    )


@router.post("/projects/{project_id}/prompt-templates", response_model=PromptTemplateOut)
def create_template(project_id: str, body: PromptTemplateCreate, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    existing = fetch_maybe_one(
        client.table("prompt_templates").select("id").eq("project_id", project_id).eq("name", body.name)
    )
    if existing:
        raise HTTPException(status_code=400, detail="A template with that name already exists")
    template = one_row(
        client.table("prompt_templates").insert({"project_id": project_id, "name": body.name}).execute()
    )
    version = one_row(
        client.table("prompt_template_versions")
        .insert({"template_id": template["id"], "version": 1, "body": body.body})
        .execute()
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
def list_templates(project_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    templates = rows(
        client.table("prompt_templates")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )
    out = []
    for template in templates:
        latest = _latest(client, template["id"])
        if not latest:
            continue
        out.append(
            {
                "id": template["id"],
                "name": template["name"],
                "version": latest["version"],
                "body": latest["body"],
                "variables": extract_variables(latest["body"]),
                "version_count": _version_count(client, template["id"]),
                "created_at": template["created_at"],
            }
        )
    return out


@router.get("/prompt-templates/{template_id}/versions", response_model=list[PromptTemplateVersionOut])
def list_versions(template_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    versions = rows(
        client.table("prompt_template_versions")
        .select("*")
        .eq("template_id", template_id)
        .order("version", desc=True)
        .execute()
    )
    if not versions:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    return [{**r, "variables": extract_variables(r["body"])} for r in versions]


@router.put("/prompt-templates/{template_id}", response_model=PromptTemplateVersionOut)
def add_version(template_id: str, body: PromptTemplateUpdate, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    latest = _latest(client, template_id)
    if not latest:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    new = one_row(
        client.table("prompt_template_versions")
        .insert({"template_id": template_id, "version": latest["version"] + 1, "body": body.body})
        .execute()
    )
    return {**new, "variables": extract_variables(new["body"])}
