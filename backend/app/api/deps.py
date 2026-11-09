"""Shared dependencies: authentication, role checks, case loading."""
from __future__ import annotations

import hashlib
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..enums import Role
from ..models import Case, User


class Principal:
    def __init__(self, username: str, role: str) -> None:
        self.username = username
        self.role = role

    @property
    def can_write(self) -> bool:
        return self.role in (Role.ADMIN.value, Role.REVIEWER.value)

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN.value


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def current_principal(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Principal:
    settings = get_settings()
    if not settings.auth_enabled:
        return Principal("local", Role.ADMIN.value)
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
    if settings.admin_api_key and x_api_key == settings.admin_api_key:
        return Principal("admin", Role.ADMIN.value)
    digest = _hash(x_api_key)
    user = db.scalars(select(User).where(User.api_key_hash == digest, User.active.is_(True))).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return Principal(user.username, user.role)


def require_write(principal: Principal = Depends(current_principal)) -> Principal:
    if not principal.can_write:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="This account has read-only access")
    return principal


def require_admin(principal: Principal = Depends(current_principal)) -> Principal:
    if not principal.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    return principal


def get_case(case_id: str, db: Session = Depends(get_db)) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case
