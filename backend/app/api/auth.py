"""Staff sign-in. See app/core/auth.py for the token and role model."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import (
    Staff, burn_password_check, client_ip, current_staff, issue_token, rate_limit, verify_password,
)
from app.core.db import get_db
from app.models import StaffUser

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    ip = client_ip(request)
    key = f"login-fail:{ip}"
    rate_limit(key, limit=10, window_s=300, record=False)  # only FAILED attempts count
    user = db.scalar(select(StaffUser).where(func.lower(StaffUser.email) == body.email.strip().lower()))
    # Same message whether the email or the password is wrong.
    if user is None:
        burn_password_check(body.password)
    if user is None or not user.active or not verify_password(body.password, user.password_hash):
        rate_limit(key, limit=10, window_s=300)
        raise HTTPException(401, "Email or password is incorrect.")
    return {
        "token": issue_token(user.id, user.role, user.school_id),
        "user": _public(user),
    }


@router.get("/me")
def me(staff: Staff = Depends(current_staff), db: Session = Depends(get_db)) -> dict:
    return _public(db.get(StaffUser, staff.id))


def _public(u: StaffUser) -> dict:
    return {
        "id": str(u.id),
        "email": u.email,
        "display_name": u.display_name,
        "role": u.role.value,
        "school_id": str(u.school_id) if u.school_id else None,
    }
