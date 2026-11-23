"""Human actions on issues. Nothing changes without one of these, and each writes an audit row.

    approve  apply the suggested value (or, with no suggestion, confirm the issue as reviewed)
    edit     set a whitelisted field to a value the person typed
    hold     park the issue for review; the record is not changed

Who may do what is decided in the routes (roles) and in `check_permission` (issue state).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from .. import models as m
from ..auth import Identity
from ..roles import Role
from . import audit
from .checks import normalise_gender
from .context import parse_date

ENTITY_MODEL = {"student": (m.Student, "student_ref"), "teacher": (m.Teacher, "teacher_ref"),
                "facility": (m.Facility, "facility_ref")}

# Fields a person may change, with a validator returning the cleaned value or raising ValueError.
def _text(v: str) -> str:
    v = " ".join(str(v).split())
    if not v:
        raise ValueError("Value cannot be empty.")
    return v


def _one_of(*allowed: str):
    def check(v: str) -> str:
        v = str(v).strip().lower().replace(" ", "_")
        if v not in allowed:
            raise ValueError(f"Must be one of: {', '.join(allowed)}.")
        return v
    return check


def _dob(v: str) -> str:
    v = str(v).strip()
    if not parse_date(v):
        raise ValueError("Use a real date in DD/MM/YYYY format.")
    return v


def _gender(v: str) -> str:
    g = normalise_gender(v)
    if not g:
        raise ValueError("Use M, F or T.")
    return g


def _grade(v: str) -> int:
    try:
        g = int(str(v).strip())
    except ValueError as exc:
        raise ValueError("Class must be a number from 1 to 12.") from exc
    if not 1 <= g <= 12:
        raise ValueError("Class must be a number from 1 to 12.")
    return g


EDITABLE: dict[str, dict[str, Any]] = {
    "student": {
        "name": _text, "guardian_name": _text, "dob": _dob, "gender": _gender, "class_grade": _grade,
        "section": _text,
        "aadhaar_status": _one_of("verified", "missing", "update_pending"),
        "enrolment_status": _one_of("active", "dropout", "transferred"),
        "transfer_status": _one_of("transferred_in", "transferred_out"),
    },
    "teacher": {"subjects": _text},
    "facility": {"status": _one_of("functional", "non_functional")},
}

ID_LIKE = re.compile(r"\d{4}\D?\d{4}\D?\d{4}")


def _clean(entity: str, field: str, value: Any) -> Any:
    validators = EDITABLE.get(entity, {})
    if field not in validators:
        raise HTTPException(422, f"'{field}' cannot be edited here.")
    if ID_LIKE.search(str(value)):
        raise HTTPException(422, "That looks like an ID number. Rsafe never stores full Aadhaar numbers.")
    try:
        return validators[field](value)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _record(s: Session, issue: m.Issue):
    model, ref_col = ENTITY_MODEL[issue.entity]
    rec = s.exec(select(model).where(getattr(model, ref_col) == issue.entity_ref)).first()
    if rec is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The record for this issue no longer exists.")
    return rec


def record_snapshot(s: Session, issue: m.Issue) -> dict[str, Any]:
    """Current values of the editable fields, for the issue panel."""
    rec = _record(s, issue)
    fields = list(EDITABLE[issue.entity])
    snap = {f: getattr(rec, f, None) for f in fields}
    if issue.entity == "student":
        snap["aadhaar"] = f"XXXX XXXX {rec.aadhaar_last4}" if rec.aadhaar_last4 else None
    return snap


def check_permission(who: Identity, issue: m.Issue, action: str) -> None:
    if issue.status in ("approved", "edited", "resolved"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"This issue is already {issue.status}.")
    if who.role == Role.PRINCIPAL:
        if action == "hold" and issue.status == "held":
            raise HTTPException(status.HTTP_409_CONFLICT, "This issue is already held.")
        return
    if who.role == Role.TEACHER:
        if action == "hold":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the principal can hold an issue.")
        if issue.status == "held":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Held issues can only be released by the principal.")
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, f"The {who.role.value} role cannot change records.")


def _finish(s: Session, issue: m.Issue, who: Identity, new_status: str, action: str,
            field: str | None, old: Any, new: Any, note: str) -> m.AuditEntry:
    issue.status = new_status
    issue.note = note
    issue.acted_by = who.actor
    issue.updated_at = datetime.now(timezone.utc)
    s.add(issue)
    return audit.append(s, who.actor, who.role.value, action, f"{issue.entity}:{issue.entity_ref}", {
        "issue_id": issue.id, "rule_id": issue.rule_id, "rule_version": issue.rule_version,
        "school_code": issue.school_code, "field": field, "old": old, "new": new,
        "status": new_status, "note": note,
    }, commit=False)


def _apply(s: Session, issue: m.Issue, field: str, value: Any) -> tuple[Any, Any]:
    rec = _record(s, issue)
    cleaned = _clean(issue.entity, field, value)
    old = getattr(rec, field)
    setattr(rec, field, cleaned)
    s.add(rec)
    return old, cleaned


def _check_note(note: str) -> None:
    # Notes go into the audit log, which is never edited, so an ID typed there could never be removed.
    if note and ID_LIKE.search(note):
        raise HTTPException(422, "The note looks like it contains an ID number. Please leave ID numbers out.")


def approve(s: Session, issue: m.Issue, who: Identity, note: str = "") -> m.AuditEntry:
    check_permission(who, issue, "approve")
    _check_note(note)
    if issue.suggested_field and issue.suggested_value is not None:
        old, new = _apply(s, issue, issue.suggested_field, issue.suggested_value)
        return _finish(s, issue, who, "approved", "issue.approve", issue.suggested_field, old, new, note)
    # No suggestion: the person confirms the issue was reviewed and the record is right as it is.
    return _finish(s, issue, who, "approved", "issue.confirm", None, None, None, note)


def edit(s: Session, issue: m.Issue, who: Identity, field: str, value: Any, note: str = "") -> m.AuditEntry:
    check_permission(who, issue, "edit")
    _check_note(note)
    old, new = _apply(s, issue, field, value)
    return _finish(s, issue, who, "edited", "issue.edit", field, old, new, note)


def hold(s: Session, issue: m.Issue, who: Identity, note: str = "") -> m.AuditEntry:
    check_permission(who, issue, "hold")
    _check_note(note)
    return _finish(s, issue, who, "held", "issue.hold", None, None, None, note)


def reject_suggestion(s: Session, issue: m.Issue, who: Identity, note: str = "") -> m.AuditEntry:
    """The person says the proposed value is wrong. The record is not touched and the issue stays
    open (or held): they still have to edit the value or confirm the record as it is."""
    check_permission(who, issue, "edit")
    _check_note(note)
    if issue.suggested_value is None or not issue.suggested_field:
        raise HTTPException(status.HTTP_409_CONFLICT, "This issue has no suggestion to reject.")
    field, rejected = issue.suggested_field, issue.suggested_value
    issue.suggested_value = None
    issue.suggested_field = None
    issue.note = note
    issue.updated_at = datetime.now(timezone.utc)
    s.add(issue)
    return audit.append(s, who.actor, who.role.value, "issue.reject_suggestion", f"{issue.entity}:{issue.entity_ref}", {
        "issue_id": issue.id, "rule_id": issue.rule_id, "rule_version": issue.rule_version,
        "school_code": issue.school_code, "field": field, "old": None, "new": None,
        "rejected_value": rejected, "status": issue.status, "note": note,
    }, commit=False)
