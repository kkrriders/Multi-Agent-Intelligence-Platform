from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterator
from uuid import UUID

from fastapi import Depends
from sqlalchemy import Connection, create_engine, text

from app.auth import get_current_user
from app.config import settings

# AUTOCOMMIT: each statement commits on its own, matching the PostgREST behaviour the
# callers were written against (e.g. a `failed` status written in an except block survives).
engine = create_engine(settings.database_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)


@contextmanager
def user_conn(user_id: str) -> Iterator[Connection]:
    with engine.connect() as conn:
        # session-level (is_local=false) because AUTOCOMMIT has no enclosing transaction
        conn.execute(text("select set_config('app.user_id', :u, false)"), {"u": user_id})
        try:
            yield conn
        finally:
            conn.execute(text("reset app.user_id"))  # pool only rolls back; it does not clear GUCs


def get_db(user: dict = Depends(get_current_user)) -> Iterator[Connection]:
    with user_conn(user["id"]) as conn:
        yield conn


def _plain(v: Any) -> Any:
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def rows(result) -> list[dict[str, Any]]:
    return [{k: _plain(v) for k, v in r._mapping.items()} for r in result]


def one(result) -> dict[str, Any]:
    return rows(result)[0]


def maybe_one(result) -> dict[str, Any] | None:
    found = rows(result)
    return found[0] if found else None
