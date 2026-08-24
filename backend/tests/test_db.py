import os

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from app.db import get_user_client


def test_get_user_client_sets_bearer_token_for_storage_requests():
    client = get_user_client("fake-jwt-token")
    assert client.options.headers["Authorization"] == "Bearer fake-jwt-token"
