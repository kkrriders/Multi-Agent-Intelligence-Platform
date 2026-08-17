import os

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.auth import get_current_user

app = FastAPI()


@app.get("/whoami")
def whoami(user=Depends(get_current_user)):
    return {"id": user["id"]}


client = TestClient(app)


def test_missing_token_returns_401():
    response = client.get("/whoami")
    assert response.status_code in (401, 422)


def test_invalid_token_returns_401():
    response = client.get("/whoami", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


@pytest.mark.skipif(
    "SUPABASE_TEST_USER_TOKEN" not in os.environ,
    reason="Real Supabase user session token required for this integration test",
)
def test_valid_token_returns_user_id(auth_headers):
    response = client.get("/whoami", headers=auth_headers)
    assert response.status_code == 200
    assert "id" in response.json()
