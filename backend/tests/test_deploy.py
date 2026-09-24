import os
from datetime import date

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://maip_app:x@localhost:5433/maip")
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ.setdefault("GROQ_API_KEY", "test")

from app.deploy import (
    COMPONENTS,
    build_argv,
    image_ref,
    image_tag,
    push_argv,
    validate_component,
    validate_repo,
)


def test_image_tag_is_date_plus_short_sha():
    assert image_tag("c6314b42b21a7bd17a7530fd4", date(2026, 8, 30)) == "2026-08-30-c6314b4"


def test_validate_repo_accepts_normal_refs():
    validate_repo("owner/ai-platform")
    validate_repo("ghcr.io")
    validate_repo("my-org/repo.name")


@pytest.mark.parametrize(
    "bad",
    ["; rm -rf /", "../evil", "Owner/Repo", "has space", "repo;", "a$b", ""],
)
def test_validate_repo_rejects_injection_and_bad_chars(bad):
    with pytest.raises(ValueError):
        validate_repo(bad)


def test_validate_component_allowlist():
    for c in COMPONENTS:
        validate_component(c)
    with pytest.raises(ValueError):
        validate_component("database")


def test_image_ref_format():
    assert image_ref("ghcr.io", "acme/app", "backend", "2026-08-30-abc1234") == (
        "ghcr.io/acme/app-backend:2026-08-30-abc1234"
    )


def test_build_and_push_argv_are_lists_never_shell_strings():
    ref = "ghcr.io/acme/app-backend:t1"
    b = build_argv(ref, "./backend")
    p = push_argv(ref)
    assert isinstance(b, list) and b[:3] == ["docker", "build", "-t"]
    assert ref in b and "./backend" in b
    assert p == ["docker", "push", ref]


# ---- create_deployment flow against real Postgres ----


def _call_create(monkeypatch, conn, *, runner, enabled=True):
    from sqlalchemy import text

    from app.api import deployments as dep
    from app.config import settings
    from app.db import one
    from app.models import DeploymentCreate

    monkeypatch.setattr(settings, "enable_deploy_api", enabled)
    target = one(
        conn.execute(
            text(
                "insert into deploy_targets (name, registry, image_repo) "
                "values (:n, 'ghcr.io', 'acme/app') returning *"
            ),
            {"n": f"prod-{os.urandom(3).hex()}"},
        )
    )
    monkeypatch.setattr(dep, "_run", runner)
    return dep.create_deployment(DeploymentCreate(target_id=target["id"], components=["backend"]), conn)


def test_create_deployment_marks_succeeded_and_captures_log(monkeypatch, user_db):
    calls = []

    def runner(argv, cwd=None):
        calls.append(argv)
        return 0, f"ok: {' '.join(argv)}\n"

    out = _call_create(monkeypatch, user_db[1], runner=runner)
    assert out["status"] == "succeeded"
    assert "docker" in out["log"] and out["image_tag"].count("-") >= 3
    assert ["docker", "build", "-t"] == calls[1][:3]  # calls[0] is git rev-parse


def test_create_deployment_marks_failed_on_nonzero_exit(monkeypatch, user_db):
    def runner(argv, cwd=None):
        if argv[:2] == ["git", "rev-parse"]:
            return 0, "abc1234\n"
        return 1, "build blew up\n"

    out = _call_create(monkeypatch, user_db[1], runner=runner)
    assert out["status"] == "failed"
    assert "build blew up" in out["log"]


def test_create_deployment_503_when_disabled(monkeypatch, user_db):
    with pytest.raises(Exception) as ei:
        _call_create(monkeypatch, user_db[1], runner=lambda *a, **k: (0, ""), enabled=False)
    assert "503" in str(ei.value) or "disabled" in str(ei.value)
