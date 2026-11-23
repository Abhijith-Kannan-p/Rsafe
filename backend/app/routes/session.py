"""Demo role switcher. Picks a fixed synthetic identity for each role."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session, func, select

from .. import models as m
from fastapi import Request

from ..auth import COOKIE, Identity, current_identity, decode, encode
from ..config import SESSION_MAX_AGE
from ..db import get_session
from ..roles import ROLE_LABELS, Role

router = APIRouter(prefix="/api/session", tags=["session"])

DEFAULT_SCHOOL = "SYN-0002"
DEFAULT_CLUSTER = "CL-01"
# The demo parent's child: "Ananya Kumar", who has a spelling issue (good for the parent view).
# Found by ID, not name, so the identity survives the principal approving the name fix.
DEMO_STUDENT_REF = "SYN-0002-S0029"
DEMO_STUDENT_NAME = "Ananya Kumar"


class SessionRequest(BaseModel):
    role: Role
    school_code: Optional[str] = None


def _open_school(s: Session, code: str) -> m.School:
    school = s.get(m.School, code)
    if not school or school.status != "open":
        raise HTTPException(400, f"No open school with code {code}.")
    return school


def _busiest_teacher(s: Session, school: str) -> str:
    """The teacher whose classes hold the most active issues: makes the teacher view worth showing."""
    teachers = list(s.exec(select(m.Teacher).where(m.Teacher.school_code == school).order_by(m.Teacher.teacher_ref)))
    if not teachers:
        raise HTTPException(400, f"School {school} has no teachers.")
    students = list(s.exec(select(m.Student).where(m.Student.school_code == school)))
    active = {i.entity_ref for i in s.exec(select(m.Issue).where(
        m.Issue.school_code == school, m.Issue.status.in_(("open", "held"))))}
    best, best_n = teachers[0].teacher_ref, -1
    for t in teachers:
        classes = {(a.class_grade, a.section) for a in s.exec(
            select(m.TeacherAssignment).where(m.TeacherAssignment.teacher_ref == t.teacher_ref))}
        n = sum(1 for st in students if (st.class_grade, st.section) in classes and st.student_ref in active)
        if n > best_n:
            best, best_n = t.teacher_ref, n
    return best


def build_identity(s: Session, role: Role, school_code: str | None) -> Identity:
    label = ROLE_LABELS[role]
    if role == Role.PRINCIPAL:
        code = _open_school(s, school_code or DEFAULT_SCHOOL).code
        return Identity(role=role, actor=f"Demo {label} ({code})", school_code=code)
    if role == Role.TEACHER:
        code = _open_school(s, school_code or DEFAULT_SCHOOL).code
        ref = _busiest_teacher(s, code)
        return Identity(role=role, actor=f"Demo {label} ({ref})", school_code=code, teacher_ref=ref)
    if role == Role.MIS_COORDINATOR:
        return Identity(role=role, actor=f"Demo {label} ({DEFAULT_CLUSTER})", cluster=DEFAULT_CLUSTER)
    if role == Role.ADMIN:
        return Identity(role=role, actor=f"Demo {label}")
    # Student and parent
    st = s.exec(select(m.Student).where(m.Student.student_ref == DEMO_STUDENT_REF)).first() \
        or s.exec(select(m.Student).where(m.Student.name == DEMO_STUDENT_NAME)).first() \
        or s.exec(select(m.Student).order_by(m.Student.id)).first()
    if st is None:
        raise HTTPException(400, "No students loaded. Run the seed first.")
    return Identity(role=role, actor=f"Demo parent of {st.student_ref}", school_code=st.school_code,
                    student_ref=st.student_ref)


@router.post("")
def sign_in(body: SessionRequest, response: Response, s: Session = Depends(get_session)) -> dict:
    if s.exec(select(func.count()).select_from(m.School)).one() == 0:
        raise HTTPException(503, "No data loaded. Run `npm run seed` first.")
    identity = build_identity(s, body.role, body.school_code)
    response.set_cookie(COOKIE, encode(identity), max_age=SESSION_MAX_AGE, httponly=True, samesite="lax")
    return identity.model_dump(mode="json")


@router.get("/status")
def status(request: Request) -> dict:
    """Signed in or not, always 200: lets the app check without a 401 in the browser console."""
    raw = request.cookies.get(COOKIE)
    identity = decode(raw) if raw else None
    return {"identity": identity.model_dump(mode="json") if identity else None}


@router.get("")
def who_am_i(identity: Identity = Depends(current_identity)) -> dict:
    return identity.model_dump(mode="json")


@router.delete("")
def sign_out(response: Response) -> dict:
    response.delete_cookie(COOKIE)
    return {"ok": True}
