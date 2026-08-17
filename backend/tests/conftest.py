import os

import pytest


@pytest.fixture
def auth_headers():
    """
    Real end-to-end auth requires a live Supabase user session token,
    ES256-signed by Supabase's own key and verified here via JWKS. Set
    SUPABASE_TEST_USER_TOKEN in the environment (obtained by signing in a
    real test user against the real Supabase project) before running
    integration tests that use this fixture.
    """
    token = os.environ["SUPABASE_TEST_USER_TOKEN"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def qdrant_available():
    from qdrant_client import QdrantClient

    from app.config import settings

    try:
        QdrantClient(url=settings.qdrant_url).get_collections()
    except Exception:
        pytest.skip("Real Qdrant instance required for this integration test (docker compose up -d qdrant)")
