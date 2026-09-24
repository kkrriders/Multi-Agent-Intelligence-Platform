import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import hash_password, issue_token, verify_password
from app.db import engine, maybe_one, one
from app.models import AuthRequest, AuthResponse, AuthUser

router = APIRouter(prefix="/auth", tags=["auth"])

_ATTEMPTS: dict[str, deque] = defaultdict(deque)
_MAX_ATTEMPTS, _WINDOW = 10, 60  # ponytail: in-memory per-IP, per-process; use Redis if the backend scales out
# Verified against when the email is unknown so login time does not reveal which emails exist.
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def _throttle(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    q, now = _ATTEMPTS[ip], time.monotonic()
    while q and now - q[0] > _WINDOW:
        q.popleft()
    if len(q) >= _MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many attempts; try again shortly")
    q.append(now)


def _response(user: dict) -> AuthResponse:
    return AuthResponse(
        access_token=issue_token(user["id"]), user=AuthUser(id=user["id"], email=user["email"])
    )


@router.post("/signup", response_model=AuthResponse)
def signup(body: AuthRequest, request: Request):
    _throttle(request)
    try:
        with engine.connect() as conn:
            user = one(conn.execute(
                text("insert into auth.users (email, password_hash) values (:e, :h) returning id, email"),
                {"e": body.email, "h": hash_password(body.password)},
            ))
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Email already registered")
    return _response(user)


@router.post("/login", response_model=AuthResponse)
def login(body: AuthRequest, request: Request):
    _throttle(request)
    with engine.connect() as conn:
        user = maybe_one(conn.execute(
            text("select id, email, password_hash from auth.users where email = :e"), {"e": body.email}
        ))
    valid = verify_password(body.password, user["password_hash"] if user else _DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _response(user)
