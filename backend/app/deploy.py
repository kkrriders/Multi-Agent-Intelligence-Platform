"""Deployment (Phase 3, SP4) — pure helpers for building the `docker`
build/push argv and validating the interpolated pieces. The endpoint that
shells these out is owner-only and gated behind ENABLE_DEPLOY_API."""

import re
from datetime import date

COMPONENTS = ("backend", "frontend")
_REF_RE = re.compile(r"^[a-z0-9._/-]+$")


def validate_repo(value: str) -> None:
    """Registry host or image repo — lowercase, digits, dot/dash/slash only,
    no `..`, non-empty. Rejects shell metacharacters, spaces, path traversal."""
    if not value or not _REF_RE.match(value) or ".." in value:
        raise ValueError(f"invalid image repo/registry: {value!r}")


def validate_component(value: str) -> None:
    if value not in COMPONENTS:
        raise ValueError(f"unknown component: {value!r} (allowed: {COMPONENTS})")


def image_tag(git_sha: str, today: date) -> str:
    return f"{today.isoformat()}-{git_sha[:7]}"


def image_ref(registry: str, image_repo: str, component: str, tag: str) -> str:
    return f"{registry}/{image_repo}-{component}:{tag}"


def build_argv(ref: str, context: str) -> list[str]:
    return ["docker", "build", "-t", ref, context]


def push_argv(ref: str) -> list[str]:
    return ["docker", "push", ref]
