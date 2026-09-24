import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response

from sqlalchemy import Connection, text

from app.config import settings
from app.db import get_db, maybe_one, one, rows
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
def list_deploy_targets(conn: Connection = Depends(get_db)):
    return rows(conn.execute(text("select * from deploy_targets order by created_at desc")))


@router.post("/deploy-targets", response_model=DeployTargetOut)
def create_deploy_target(body: DeployTargetCreate, conn: Connection = Depends(get_db)):
    try:
        validate_repo(body.registry)
        validate_repo(body.image_repo)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return one(
        conn.execute(
            text(
                "insert into deploy_targets (name, registry, image_repo, config) "
                "values (:n, :r, :i, cast(:c as jsonb)) returning *"
            ),
            {"n": body.name, "r": body.registry, "i": body.image_repo, "c": json.dumps(body.config)},
        )
    )


@router.delete("/deploy-targets/{target_id}", status_code=204)
def delete_deploy_target(target_id: str, conn: Connection = Depends(get_db)):
    conn.execute(text("delete from deploy_targets where id = :i"), {"i": target_id})
    return Response(status_code=204)


# ---- deployments ----


@router.get("/deployments", response_model=list[DeploymentOut])
def list_deployments(limit: int = 50, conn: Connection = Depends(get_db)):
    return rows(
        conn.execute(
            text("select * from deployments order by created_at desc limit :n"), {"n": min(limit, 200)}
        )
    )


@router.post("/deployments", response_model=DeploymentOut)
def create_deployment(body: DeploymentCreate, conn: Connection = Depends(get_db)):
    if not settings.enable_deploy_api:
        raise HTTPException(status_code=503, detail="deploy API disabled (ENABLE_DEPLOY_API)")

    target = maybe_one(
        conn.execute(text("select * from deploy_targets where id = :i"), {"i": body.target_id})
    )
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

    row = one(
        conn.execute(
            text(
                "insert into deployments (target_id, image_tag, components) "
                "values (:t, :tag, :c) returning *"
            ),
            {"t": body.target_id, "tag": tag, "c": components},
        )
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

    updated = one(
        conn.execute(
            text("update deployments set status = :s, log = :l, git_sha = :g where id = :i returning *"),
            {
                "s": "succeeded" if ok else "failed",
                "l": "\n".join(log_parts)[:_LOG_CAP],
                "g": git_sha,
                "i": row["id"],
            },
        )
    )
    return updated
