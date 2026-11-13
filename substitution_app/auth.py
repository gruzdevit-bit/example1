"""Упрощённый вход: подписанная кука с идентификатором пользователя и CSRF."""

from __future__ import annotations

import hashlib
import hmac
import os

COOKIE_NAME = "substitution_session"
SECRET = os.getenv("COOKIE_SECRET", "dev-substitution-secret-key")


def _sign(payload: str) -> str:
    return hmac.new(SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def make_session(user_id: int) -> str:
    payload = str(user_id)
    return f"{payload}.{_sign(payload)}"


def read_session(raw: str | None) -> int | None:
    if not raw or "." not in raw:
        return None
    payload, signature = raw.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    try:
        return int(payload)
    except ValueError:
        return None


def csrf_token(user_id: int | None) -> str:
    key = str(user_id) if user_id is not None else "anon"
    return _sign(f"csrf:{key}")


def csrf_valid(token: str | None, user_id: int | None) -> bool:
    if not token:
        return False
    return hmac.compare_digest(token, csrf_token(user_id))
