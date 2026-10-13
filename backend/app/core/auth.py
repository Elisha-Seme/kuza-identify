"""Staff authentication and role checks.

Deliberately dependency-free (stdlib scrypt + HMAC), so nothing new has to be
installed on the serverless host:

* Passwords: salted scrypt hash, compared in constant time.
* Tokens: a short signed bearer token, `base64(payload).base64(hmac_sha256)`,
  carrying user id, role and expiry. Signed with AUTH_SECRET.

Fail-closed: outside local development, if AUTH_SECRET is not configured the
API refuses to issue or accept tokens rather than falling back to a guessable
default.

Learners never sign in. Referrals (nomination / portfolio) stay open to
parents and teachers without an account, but are rate-limited and can never
reach a decision on their own.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.enums import StaffRole

TOKEN_TTL_SECONDS = 12 * 60 * 60  # one working day
_LOCAL_SECRET = secrets.token_hex(32)  # per-process, local dev only


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


_DUMMY_HASH: str | None = None


def burn_password_check(password: str) -> None:
    """Spend the same time as a real check when the email doesn't exist, so
    response timing doesn't reveal which emails have accounts."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_hex(8))
    verify_password(password, _DUMMY_HASH)


def client_ip(request) -> str:
    """Behind Vercel the socket peer is the proxy; Vercel sets
    x-real-ip / x-forwarded-for to the real client (and overwrites any
    client-supplied value)."""
    h = request.headers
    ip = h.get("x-real-ip") or (h.get("x-forwarded-for") or "").split(",")[0].strip()
    return ip or (request.client.host if request.client else "unknown")


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
    except ValueError:
        return False
    actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=len(expected))
    return hmac.compare_digest(actual, expected)


# ---------------------------------------------------------------- tokens
def is_local_dev() -> bool:
    """Only a genuine local run may fall back to a throwaway secret. Vercel
    sets VERCEL=1 and the app sets SERVERLESS there, so a hosted deploy with
    no AUTH_SECRET fails closed even if APP_ENV was never set."""
    s = get_settings()
    return s.app_env == "local" and not s.serverless and not os.environ.get("VERCEL")


def _secret() -> bytes:
    s = get_settings()
    if s.auth_secret:
        return s.auth_secret.encode()
    if is_local_dev():
        return _LOCAL_SECRET.encode()
    raise HTTPException(503, "Sign-in is not configured on this server (AUTH_SECRET is not set).")


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue_token(user_id: uuid.UUID, role: StaffRole, school_id: uuid.UUID | None) -> str:
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "school": str(school_id) if school_id else None,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


@dataclass(frozen=True)
class Staff:
    id: uuid.UUID
    role: StaffRole
    school_id: uuid.UUID | None

    @property
    def reviewer_id(self) -> str:
        """What is written to PanelReview.reviewer_id: the signed-in account,
        never a free-text name typed into the browser."""
        return f"staff:{self.id}"


def _decode(token: str) -> dict:
    try:
        body, sig = token.split(".")
    except ValueError:
        raise HTTPException(401, "Malformed token.")
    expected = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(401, "Invalid token.")
    payload = json.loads(_unb64(body))
    if payload.get("exp", 0) < time.time():
        raise HTTPException(401, "Session expired, please sign in again.")
    return payload


def current_staff(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> Staff:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Sign in required.")
    payload = _decode(authorization.split(" ", 1)[1].strip())

    # Re-check the account on every request so deactivating someone takes
    # effect immediately, not when their token expires.
    from app.models import StaffUser

    user = db.get(StaffUser, uuid.UUID(payload["sub"]))
    if user is None or not user.active:
        raise HTTPException(401, "This account is no longer active.")
    return Staff(id=user.id, role=user.role, school_id=user.school_id)


def require_roles(*roles: StaffRole):
    allowed = set(roles)

    def dep(staff: Staff = Depends(current_staff)) -> Staff:
        if staff.role not in allowed:
            raise HTTPException(403, "Your role does not have access to this.")
        return staff

    return dep


# Convenience groupings used by the routers.
PANEL_READ = (StaffRole.reviewer, StaffRole.panel_lead, StaffRole.programme_admin)
PANEL_DECIDE = (StaffRole.reviewer, StaffRole.panel_lead)
INSIGHTS_READ = (StaffRole.reviewer, StaffRole.panel_lead, StaffRole.programme_admin, StaffRole.auditor)
AUDIT_READ = (StaffRole.panel_lead, StaffRole.programme_admin, StaffRole.auditor)
SCREENING_OPERATE = (StaffRole.school_staff, StaffRole.programme_admin, StaffRole.panel_lead)
ADMIN = (StaffRole.programme_admin,)


# ---------------------------------------------------------------- rate limiting
_hits: dict[str, list[float]] = {}


def rate_limit(key: str, limit: int, window_s: int, record: bool = True) -> None:
    """Best-effort, per-instance sliding window. On serverless each instance
    keeps its own window, so this caps bursts rather than guaranteeing a
    global limit; put a real limiter (Vercel firewall / Upstash) in front for
    hard guarantees."""
    now = time.time()
    bucket = [t for t in _hits.get(key, []) if now - t < window_s]
    if len(bucket) >= limit:
        raise HTTPException(429, "Too many requests, please wait a moment and try again.")
    if record:
        bucket.append(now)
    _hits[key] = bucket
    if len(_hits) > 10_000:  # keep memory bounded
        _hits.clear()
