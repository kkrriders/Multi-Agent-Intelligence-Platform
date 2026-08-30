import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import get_current_user
from app.config import settings
from app.db import fetch_maybe_one, get_user_client
from app.deploy import (
    build_argv,
    image_ref,
    image_tag,
    push_argv,
    validate_component,
    validate_repo,
)
from app.models import DeploymentCreate, DeploymentOut, DeployTargetCreate, DeployTargetOut

router = APIRouter(tags=["deployments"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LOG_CAP = 64_000
_STEP_TIMEOUT_S = 900


def _run(argv: list[str], cwd: Path | None = None) -> tuple[int, str]:
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=_STEP_TIMEOUT_S)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


# ---- deploy targets ----


@router.get("/deploy-targets", response_model=list[DeployTargetOut])
def list_deploy_targets(user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    return client.table("deploy_targets").select("*").order("created_at", desc=True).execute().data


@router.post("/deploy-targets", response_model=DeployTargetOut)
def create_deploy_target(body: DeployTargetCreate, user: dict = Depends(get_current_user)):
    try:
        validate_repo(body.registry)
        validate_repo(body.image_repo)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    client = get_user_client(user["token"])
    return (
        client.table("deploy_targets")
        .insert(
            {
                "name": body.name,
                "registry": body.registry,
                "image_repo": body.image_repo,
                "config": body.config,
            }
        )
        .execute()
        .data[0]
    )


@router.delete("/deploy-targets/{target_id}", status_code=204)
def delete_deploy_target(target_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    client.table("deploy_targets").delete().eq("id", target_id).execute()
    return Response(status_code=204)


# ---- deployments ----


@router.get("/deployments", response_model=list[DeploymentOut])
def list_deployments(limit: int = 50, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    return (
        client.table("deployments")
        .select("*")
        .order("created_at", desc=True)
        .limit(min(limit, 200))
        .execute()
        .data
    )


@router.post("/deployments", response_model=DeploymentOut)
def create_deployment(body: DeploymentCreate, user: dict = Depends(get_current_user)):
    if not settings.enable_deploy_api:
        raise HTTPException(status_code=503, detail="deploy API disabled (ENABLE_DEPLOY_API)")

    client = get_user_client(user["token"])
    target = fetch_maybe_one(client.table("deploy_targets").select("*").eq("id", body.target_id))
    if not target:
        raise HTTPException(status_code=404, detail="Deploy target not found")

    components = body.components or list(("backend", "frontend"))
    try:
        for c in components:
            validate_component(c)
        validate_repo(target["registry"])
        validate_repo(target["image_repo"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    rc, out = _run(["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT)
    git_sha = out.strip() if rc == 0 else "unknown"
    tag = image_tag(git_sha, datetime.now(timezone.utc).date())

    row = (
        client.table("deployments")
        .insert({"target_id": body.target_id, "image_tag": tag, "components": components})
        .execute()
        .data[0]
    )

    log_parts: list[str] = []
    ok = True
    for component in components:
        ref = image_ref(target["registry"], target["image_repo"], component, tag)
        ctx = _REPO_ROOT / component
        for argv in (build_argv(ref, str(ctx)), push_argv(ref)):
            log_parts.append(f"$ {' '.join(argv)}")
            step_rc, step_out = _run(argv, cwd=_REPO_ROOT)
            log_parts.append(step_out)
            if step_rc != 0:
                ok = False
                break
        if not ok:
            break

    updated = (
        client.table("deployments")
        .update(
            {
                "status": "succeeded" if ok else "failed",
                "log": "\n".join(log_parts)[:_LOG_CAP],
                "git_sha": git_sha,
            }
        )
        .eq("id", row["id"])
        .execute()
        .data[0]
    )
    return updated
