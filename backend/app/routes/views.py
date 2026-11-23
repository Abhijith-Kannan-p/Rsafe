"""Role-specific views: the cluster grid (MIS, Admin), a teacher's classes, and a parent's view of
their child's record with a MOCK OTP confirmation step.

The parent confirmation is a mockup of a planned flow: no SMS is sent, the code is shown on
screen, and confirming never changes the record. It only writes an audit row that staff can see.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections import Counter, defaultdict
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import models as m
from ..auth import Identity, current_identity, require
from ..config import REFERENCE_DATE, SESSION_SECRET
from ..db import get_session
from ..roles import Role
from ..services import audit, scope
from ..services.actions import ID_LIKE
from ..services.validation import ACTIVE, school_summary

router = APIRouter(prefix="/api", tags=["views"])

SEV_ORDER = {"high": 0, "medium": 1, "low": 2}


def _issue_brief(i: m.Issue) -> dict[str, Any]:
    return {"id": i.id, "rule_id": i.rule_id, "severity": i.severity, "status": i.status, "title": i.title}


# ------------------------------------------------------------------ schools (role switcher)

@router.get("/schools")
def schools(_: Identity = Depends(current_identity), s: Session = Depends(get_session)) -> list[dict]:
    """Open synthetic schools, for the demo role switcher's school picker."""
    rows = s.exec(select(m.School).where(m.School.status == "open").order_by(m.School.code))
    return [{"code": x.code, "name": x.name, "cluster": x.cluster} for x in rows]


# ------------------------------------------------------------------ cluster

def school_status(active: list[m.Issue]) -> str:
    """blocked: a high-severity or held issue is waiting; fixing: only medium/low remain; ready: none."""
    if any(i.severity == "high" or i.status == "held" for i in active):
        return "blocked"
    return "fixing" if active else "ready"


@router.get("/cluster")
def cluster(who: Identity = Depends(require(Role.MIS_COORDINATOR, Role.ADMIN)),
            s: Session = Depends(get_session)) -> dict:
    visible = set(scope.visible_schools(s, who))
    q = select(m.School).order_by(m.School.code)
    if who.role == Role.MIS_COORDINATOR:
        q = q.where(m.School.cluster == who.cluster)
    tiles = []
    for school in s.exec(q):
        if school.status != "open":
            tiles.append({"school_code": school.code, "name": school.name, "cluster": school.cluster,
                          "status": school.status, "merged_into": school.merged_into})
            continue
        if school.code not in visible:
            continue
        issues = list(s.exec(select(m.Issue).where(m.Issue.school_code == school.code)))
        active = [i for i in issues if i.status in ACTIVE]
        by_rule: dict[str, list[m.Issue]] = defaultdict(list)
        for i in active:
            by_rule[i.rule_id].append(i)
        reasons = sorted(
            ({"rule_id": r, "title": xs[0].title, "severity": xs[0].severity, "count": len(xs),
              "held": sum(x.status == "held" for x in xs),
              "blocking": any(x.severity == "high" or x.status == "held" for x in xs)}
             for r, xs in by_rule.items()),
            key=lambda x: (not x["blocking"], SEV_ORDER[x["severity"]], -x["count"], x["rule_id"]))
        decided = Counter(i.status for i in issues)
        tiles.append(school_summary(s, school.code) | {
            "cluster": school.cluster, "status": school_status(active), "reasons": reasons,
            "decided": decided.get("approved", 0) + decided.get("edited", 0),
            "resolved": decided.get("resolved", 0),
        })
    open_tiles = [t for t in tiles if "readiness" in t]
    return {
        "cluster": who.cluster or "All clusters",
        "counts": dict(Counter(t["status"] for t in tiles)),
        "students": sum(t["students"] for t in open_tiles),
        "schools": tiles,
    }


# ------------------------------------------------------------------ teacher

@router.get("/my/classes")
def my_classes(who: Identity = Depends(require(Role.TEACHER)), s: Session = Depends(get_session)) -> dict:
    me = s.exec(select(m.Teacher).where(m.Teacher.teacher_ref == who.teacher_ref)).first()
    assignments = list(s.exec(select(m.TeacherAssignment).where(m.TeacherAssignment.teacher_ref == who.teacher_ref)))
    subjects: dict[tuple[int, str], list[str]] = defaultdict(list)
    for a in assignments:
        subjects[(a.class_grade, a.section)].append(a.subject)
    issues = [i for i in s.exec(select(m.Issue).where(m.Issue.school_code == who.school_code,
                                                      m.Issue.status != "resolved"))]
    by_student: dict[str, list[m.Issue]] = defaultdict(list)
    for i in issues:
        if i.entity == "student":
            by_student[i.entity_ref].append(i)
    students = list(s.exec(select(m.Student).where(m.Student.school_code == who.school_code)
                           .order_by(m.Student.name)))
    classes = []
    for (grade, section) in sorted(subjects):
        roster = []
        for st in students:
            if (st.class_grade, st.section) != (grade, section):
                continue
            mine = sorted(by_student.get(st.student_ref, []), key=lambda i: (i.status not in ACTIVE, SEV_ORDER[i.severity]))
            roster.append({"student_ref": st.student_ref, "name": st.name, "gender": st.gender, "dob": st.dob,
                           "issues": [_issue_brief(i) for i in mine],
                           "active": sum(i.status in ACTIVE for i in mine)})
        classes.append({"class_grade": grade, "section": section, "subjects": sorted(subjects[(grade, section)]),
                        "students": roster, "active": sum(r["active"] for r in roster)})
    own = [_issue_brief(i) for i in issues if i.entity == "teacher" and i.entity_ref == who.teacher_ref]
    return {
        "teacher": {"teacher_ref": who.teacher_ref, "name": me.name if me else who.teacher_ref,
                    "subjects": [x for x in (me.subjects if me else "").split(";") if x]},
        "school_code": who.school_code,
        "classes": classes,
        "own_issues": own,
    }


# ------------------------------------------------------------------ student and parent

def _student(s: Session, who: Identity) -> m.Student:
    st = s.exec(select(m.Student).where(m.Student.student_ref == who.student_ref)).first()
    if st is None:
        raise HTTPException(404, "Record not found.")
    return st


def mock_code(student_ref: str) -> str:
    """Demo OTP: derived, not sent. Stable for a student for the (pinned) day."""
    digest = hmac.new(SESSION_SECRET.encode(), f"otp|{student_ref}|{REFERENCE_DATE}".encode(), hashlib.sha256).digest()
    return f"{int.from_bytes(digest[:4], 'big') % 1_000_000:06d}"


def _latest_confirmation(s: Session, ref: str) -> dict | None:
    rows = s.exec(select(m.AuditEntry).where(m.AuditEntry.record_ref == f"student:{ref}",
                                             m.AuditEntry.action.startswith("parent."))  # type: ignore[attr-defined]
                  .order_by(m.AuditEntry.id.desc()))
    e = rows.first()
    if e is None:
        return None
    p = json.loads(e.payload or "{}")
    return {"ts": e.ts, "outcome": p.get("outcome"), "comment": p.get("comment", ""), "audit_id": e.id}


@router.get("/my/record")
def my_record(who: Identity = Depends(require(Role.STUDENT_PARENT)), s: Session = Depends(get_session)) -> dict:
    st = _student(s, who)
    school = s.get(m.School, st.school_code)
    issues = s.exec(select(m.Issue).where(m.Issue.entity == "student", m.Issue.entity_ref == st.student_ref)
                    .order_by(m.Issue.id))
    return {
        "student": {
            "student_ref": st.student_ref, "name": st.name, "dob": st.dob, "gender": st.gender,
            "class_grade": st.class_grade, "section": st.section, "guardian_name": st.guardian_name,
            "aadhaar": f"XXXX XXXX {st.aadhaar_last4}" if st.aadhaar_last4 else None,
            "aadhaar_status": st.aadhaar_status, "enrolment_status": st.enrolment_status,
        },
        "school": {"code": st.school_code, "name": school.name if school else st.school_code},
        "issues": [{"id": i.id, "rule_id": i.rule_id, "severity": i.severity, "status": i.status,
                    "title": i.title, "message": i.message, "fix": i.fix} for i in issues],
        "confirmation": _latest_confirmation(s, st.student_ref),
    }


@router.post("/my/confirm/start")
def confirm_start(who: Identity = Depends(require(Role.STUDENT_PARENT)), s: Session = Depends(get_session)) -> dict:
    st = _student(s, who)
    ending = f"{int(hashlib.sha256(st.student_ref.encode()).hexdigest(), 16) % 100:02d}"
    return {"mock": True, "sent_to": f"guardian's mobile ending {ending}", "demo_code": mock_code(st.student_ref),
            "note": "Mockup: no SMS is sent. The code is shown here so the flow can be demonstrated."}


class ConfirmBody(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    outcome: Literal["correct", "needs_change"]
    comment: str = Field(default="", max_length=300)


@router.post("/my/confirm")
def confirm(body: ConfirmBody, who: Identity = Depends(require(Role.STUDENT_PARENT)),
            s: Session = Depends(get_session)) -> dict:
    st = _student(s, who)
    if ID_LIKE.search(body.comment):
        raise HTTPException(422, "Please don't type ID numbers here. Rsafe never stores full Aadhaar numbers.")
    if not hmac.compare_digest(body.code, mock_code(st.student_ref)):
        raise HTTPException(422, "That code is not right. Check it and try again.")
    action = "parent.confirm" if body.outcome == "correct" else "parent.report"
    entry = audit.append(s, who.actor, who.role.value, action, f"student:{st.student_ref}", {
        "school_code": st.school_code, "outcome": body.outcome, "comment": body.comment, "mock_otp": True,
    })
    return {"audit_id": entry.id, "confirmation": _latest_confirmation(s, st.student_ref)}
