import hashlib
import hmac
import os
import time

import jwt
from fastapi import Header, HTTPException

from app.config import settings

TOKEN_TTL_SECONDS = 12 * 3600
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$")
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)


def issue_token(user_id: str) -> str:
    now = int(time.time())
    claims = {"sub": user_id, "aud": "authenticated", "iat": now, "exp": now + TOKEN_TTL_SECONDS}
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def get_current_user(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=["HS256"], audience="authenticated", leeway=30
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"id": payload["sub"]}
