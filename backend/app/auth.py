"""Demo authentication: a role switcher with a signed session cookie. No passwords.

The cookie holds a signed Identity. Every protected route resolves it with `current_identity`
and checks the role with `require(...)`, so access is enforced on the server, not just hidden
in the UI.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel, ValidationError

from .config import SESSION_MAX_AGE, SESSION_SECRET
from .roles import Role

COOKIE = "rsafe_session"
_serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="rsafe-session-v1")


class Identity(BaseModel):
    role: Role
    actor: str  # human-readable name written to the audit log
    school_code: Optional[str] = None  # principal, teacher, student_parent
    cluster: Optional[str] = None  # mis_coordinator
    teacher_ref: Optional[str] = None
    student_ref: Optional[str] = None


def encode(identity: Identity) -> str:
    return _serializer.dumps(identity.model_dump(mode="json"))


def decode(token: str) -> Identity | None:
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE)
        return Identity(**data)
    except (BadSignature, ValidationError, TypeError):
        return None


def current_identity(request: Request) -> Identity:
    token = request.cookies.get(COOKIE)
    identity = decode(token) if token else None
    if identity is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Choose a demo role first.")
    return identity


def require(*roles: Role):
    allowed = set(roles)

    def dep(identity: Identity = Depends(current_identity)) -> Identity:
        if identity.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"The {identity.role.value} role cannot do this.")
        return identity

    return dep
