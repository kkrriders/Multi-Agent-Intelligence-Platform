import os
from datetime import date

import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
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


# ---- create_deployment flow with a fake Supabase client ----


class _FakeTable:
    def __init__(self, store, name):
        self.store, self.name, self._rows = store, name, list(store.get(name, []))
        self._patch = None

    def select(self, *a, **k):
        return self

    def insert(self, row):
        row = {"id": f"{self.name}-{len(self.store.setdefault(self.name, []))}", **row,
               "status": row.get("status", "running"), "git_sha": None, "log": ""}
        self.store.setdefault(self.name, []).append(row)
        self._rows = [row]
        return self

    def update(self, patch):
        self._patch = patch
        return self

    def eq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def maybe_single(self):
        self._single = True
        return self

    def execute(self):
        if self._patch is not None:
            for r in self._rows:
                r.update(self._patch)
            self._patch = None
        if getattr(self, "_single", False):
            return type("R", (), {"data": self._rows[0] if self._rows else None})()
        return type("R", (), {"data": list(self._rows)})()


class _FakeClient:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _FakeTable(self.store, name)


def _call_create(monkeypatch, *, runner, enabled=True):
    from app.api import deployments as dep
    from app.config import settings
    from app.models import DeploymentCreate

    monkeypatch.setattr(settings, "enable_deploy_api", enabled)
    store = {"deploy_targets": [
        {"id": "t1", "name": "prod", "registry": "ghcr.io", "image_repo": "acme/app", "config": {}}
    ]}
    monkeypatch.setattr(dep, "get_user_client", lambda token: _FakeClient(store))
    monkeypatch.setattr(dep, "_run", runner)
    out = dep.create_deployment(DeploymentCreate(target_id="t1", components=["backend"]), {"token": "x"})
    return out, store


def test_create_deployment_marks_succeeded_and_captures_log(monkeypatch):
    calls = []

    def runner(argv, cwd=None):
        calls.append(argv)
        return 0, f"ok: {' '.join(argv)}\n"

    out, _ = _call_create(monkeypatch, runner=runner)
    assert out["status"] == "succeeded"
    assert "docker" in out["log"] and out["image_tag"].count("-") >= 3
    assert ["docker", "build", "-t"] == calls[1][:3]  # calls[0] is git rev-parse


def test_create_deployment_marks_failed_on_nonzero_exit(monkeypatch):
    def runner(argv, cwd=None):
        if argv[:2] == ["git", "rev-parse"]:
            return 0, "abc1234\n"
        return 1, "build blew up\n"

    out, _ = _call_create(monkeypatch, runner=runner)
    assert out["status"] == "failed"
    assert "build blew up" in out["log"]


def test_create_deployment_503_when_disabled(monkeypatch):
    with pytest.raises(Exception) as ei:
        _call_create(monkeypatch, runner=lambda *a, **k: (0, ""), enabled=False)
    assert "503" in str(ei.value) or "disabled" in str(ei.value)
