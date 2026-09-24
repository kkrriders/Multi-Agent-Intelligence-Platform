
import pytest


@pytest.fixture
def db_available():
    from sqlalchemy import text

    from app.db import engine

    try:
        with engine.connect() as c:
            c.execute(text("select 1"))
    except Exception:
        pytest.skip("Real Postgres required (docker compose up -d postgres; DATABASE_URL in .env)")


@pytest.fixture
def auth_headers(db_available):
    """Bearer header for a freshly inserted real user (signup itself is covered in test_auth.py;
    going through /auth/signup here would trip its per-IP throttle)."""
    import uuid

    from sqlalchemy import text

    from app.auth import issue_token
    from app.db import engine

    user_id = str(uuid.uuid4())
    with engine.connect() as c:
        c.execute(
            text("insert into auth.users (id, email, password_hash) values (:i, :e, 'x')"),
            {"i": user_id, "e": f"{user_id}@test.dev"},
        )
    return {"Authorization": f"Bearer {issue_token(user_id)}"}


@pytest.fixture
def qdrant_available():
    from qdrant_client import QdrantClient

    from app.config import settings

    try:
        QdrantClient(url=settings.qdrant_url).get_collections()
    except Exception:
        pytest.skip("Real Qdrant instance required for this integration test (docker compose up -d qdrant)")


@pytest.fixture
def user_db(db_available):
    """A freshly created user plus an RLS-scoped connection acting as them: (user_id, conn)."""
    import uuid

    from sqlalchemy import text

    from app.db import engine, user_conn

    user_id = str(uuid.uuid4())
    with engine.connect() as c:
        c.execute(
            text("insert into auth.users (id, email, password_hash) values (:i, :e, 'x')"),
            {"i": user_id, "e": f"{user_id}@test.dev"},
        )
    with user_conn(user_id) as conn:
        yield user_id, conn
