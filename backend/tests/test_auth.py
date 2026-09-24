import os
import time

import jwt
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://maip_app:x@localhost:5433/maip")
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.auth import hash_password, issue_token, verify_password
from app.config import settings
from app.main import app

client = TestClient(app)


def test_password_hash_roundtrip_and_salt():
    h1, h2 = hash_password("correct horse"), hash_password("correct horse")
    assert h1 != h2  # per-user salt
    assert verify_password("correct horse", h1)
    assert not verify_password("wrong", h1)
    assert not verify_password("x", "garbage-without-separator")


def test_protected_route_requires_bearer():
    assert client.get("/projects").status_code in (401, 422)


def test_rejects_expired_and_wrongly_signed_tokens():
    expired = jwt.encode(
        {"sub": "u", "aud": "authenticated", "exp": int(time.time()) - 60},
        settings.jwt_secret, algorithm="HS256",
    )
    forged = jwt.encode(
        {"sub": "u", "aud": "authenticated", "exp": int(time.time()) + 60},
        "another-secret-that-is-long-enough-xx", algorithm="HS256",
    )
    for t in (expired, forged):
        assert client.get("/projects", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_issue_token_claims():
    claims = jwt.decode(issue_token("abc"), settings.jwt_secret, algorithms=["HS256"], audience="authenticated")
    assert claims["sub"] == "abc"


def test_signup_login_flow(db_available):
    email = f"u{time.time_ns()}@t.dev"
    r = client.post("/auth/signup", json={"email": email, "password": "longenough1"})
    assert r.status_code == 200 and r.json()["user"]["email"] == email
    assert client.post("/auth/signup", json={"email": email, "password": "longenough1"}).status_code == 409
    ok = client.post("/auth/login", json={"email": email, "password": "longenough1"})
    assert ok.status_code == 200
    me = client.get("/projects", headers={"Authorization": f"Bearer {ok.json()['access_token']}"})
    assert me.status_code == 200 and me.json() == []
    bad = client.post("/auth/login", json={"email": email, "password": "nope-nope-1"})
    assert bad.status_code == 401 and bad.json()["detail"] == "Invalid email or password"
    unknown = client.post("/auth/login", json={"email": "no@one.dev", "password": "nope-nope-1"})
    assert unknown.json()["detail"] == bad.json()["detail"]


@pytest.mark.parametrize("body", [
    {"email": "not-an-email", "password": "longenough1"},
    {"email": "a@b.dev", "password": "short"},
])
def test_signup_validates_input(body):
    assert client.post("/auth/signup", json=body).status_code == 422
