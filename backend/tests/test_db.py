import os
import uuid

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://maip_app:x@localhost:5433/maip")
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ.setdefault("GROQ_API_KEY", "test")

from sqlalchemy import text

from app.db import engine, maybe_one, one, rows, user_conn


@pytest.fixture
def two_users(db_available):
    ids = []
    with engine.connect() as c:
        for _ in range(2):
            uid = str(uuid.uuid4())
            c.execute(
                text("insert into auth.users (id, email, password_hash) values (:i, :e, 'x')"),
                {"i": uid, "e": f"{uid}@t.dev"},
            )
            ids.append(uid)
    return ids


def test_rows_are_json_shaped(two_users):
    a, _ = two_users
    with user_conn(a) as c:
        p = one(c.execute(text("insert into projects (name) values ('p') returning *")))
    assert isinstance(p["id"], str) and isinstance(p["created_at"], str)
    assert p["owner_id"] == a  # auth.uid() default picked up app.user_id


def test_rls_hides_other_users_rows(two_users):
    a, b = two_users
    with user_conn(a) as c:
        c.execute(text("insert into projects (name) values ('mine')"))
    with user_conn(b) as c:
        assert rows(c.execute(text("select * from projects"))) == []
        assert maybe_one(c.execute(text("select * from projects"))) is None


def test_user_id_is_reset_when_connection_returns_to_pool(two_users):
    a, _ = two_users
    with user_conn(a) as c:
        c.execute(text("select 1"))
    with engine.connect() as c:
        assert c.execute(text("select auth.uid()")).scalar() is None
