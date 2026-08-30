import os
import shutil
import subprocess

import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_NEEDS_SUPABASE = pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost",
    reason="Real Supabase project required for this integration test",
)


def test_deploy_routes_require_auth():
    assert client.get("/deployments").status_code in (401, 422)
    assert client.get("/deploy-targets").status_code in (401, 422)
    assert client.post("/deploy-targets", json={"name": "x", "image_repo": "a/b"}).status_code in (401, 422)
    assert client.post("/deployments", json={"target_id": "t"}).status_code in (401, 422)


@_NEEDS_SUPABASE
def test_deploy_target_crud_and_owner_isolation(auth_headers):
    created = client.post(
        "/deploy-targets",
        json={"name": f"tgt-{os.urandom(3).hex()}", "image_repo": "acme/ai-platform", "config": {"FOO": "bar"}},
        headers=auth_headers,
    )
    assert created.status_code == 200
    tid = created.json()["id"]

    assert any(t["id"] == tid for t in client.get("/deploy-targets", headers=auth_headers).json())

    # a bad repo string is rejected
    bad = client.post(
        "/deploy-targets", json={"name": "bad", "image_repo": "../evil; rm -rf"}, headers=auth_headers
    )
    assert bad.status_code == 422

    assert client.delete(f"/deploy-targets/{tid}", headers=auth_headers).status_code == 204
    assert not any(t["id"] == tid for t in client.get("/deploy-targets", headers=auth_headers).json())


@_NEEDS_SUPABASE
def test_post_deployments_503_when_api_disabled(auth_headers):
    # ENABLE_DEPLOY_API defaults to False
    tid = client.post(
        "/deploy-targets",
        json={"name": f"d503-{os.urandom(3).hex()}", "image_repo": "acme/ai-platform"},
        headers=auth_headers,
    ).json()["id"]
    r = client.post("/deployments", json={"target_id": tid}, headers=auth_headers)
    assert r.status_code == 503
    assert client.get("/deployments", headers=auth_headers).status_code == 200
    client.delete(f"/deploy-targets/{tid}", headers=auth_headers)


@pytest.mark.skipif(
    shutil.which("docker") is None or os.environ.get("RUN_IMAGE_BUILD_TEST") != "1",
    reason="slow: set RUN_IMAGE_BUILD_TEST=1 (and have docker) to run the hardened-image acceptance build",
)
def test_hardened_images_build_and_run_as_nonroot():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    for name in ("backend", "frontend"):
        tag = f"maip-harden-test-{name}:t"
        build = subprocess.run(
            ["docker", "build", "-t", tag, os.path.join(root, name)],
            capture_output=True, text=True, timeout=1200,
        )
        assert build.returncode == 0, build.stdout + build.stderr
        who = subprocess.run(["docker", "run", "--rm", tag, "id", "-u"], capture_output=True, text=True)
        assert who.stdout.strip() not in ("0", ""), f"{name} image runs as root"
        subprocess.run(["docker", "rmi", "-f", tag], capture_output=True)
