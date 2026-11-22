"""Validation runs, issue listing and the approve / edit / hold actions."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import models as m
from ..auth import Identity, current_identity, require
from ..db import get_session
from ..roles import Role
from ..services import actions, scope
from ..services.validation import run_validation, school_summary

router = APIRouter(prefix="/api", tags=["issues"])

ACTORS = (Role.PRINCIPAL, Role.TEACHER)


def issue_out(i: m.Issue) -> dict[str, Any]:
    return i.model_dump(mode="json", exclude={"fingerprint"})


class ValidateRequest(BaseModel):
    school_code: Optional[str] = None


@router.post("/validate")
def validate(body: ValidateRequest, request: Request,
             who: Identity = Depends(require(Role.PRINCIPAL, Role.MIS_COORDINATOR, Role.ADMIN)),
             s: Session = Depends(get_session)) -> dict:
    allowed = scope.visible_schools(s, who)
    if body.school_code:
        if body.school_code not in allowed:
            raise HTTPException(404, "School not found.")
        targets = [body.school_code]
    else:
        targets = allowed
    return run_validation(s, request.app.state.rules, targets, who.actor, who.role.value)


@router.get("/summary")
def summary(who: Identity = Depends(current_identity), s: Session = Depends(get_session)) -> dict:
    only = scope.visible_student_refs(s, who)
    return {"schools": [school_summary(s, code, only) for code in scope.visible_schools(s, who)]}


@router.get("/issues")
def list_issues(
    status: Optional[str] = None, severity: Optional[str] = None, rule_id: Optional[str] = None,
    entity: Optional[str] = None, school_code: Optional[str] = None,
    who: Identity = Depends(current_identity), s: Session = Depends(get_session),
) -> list[dict]:
    q = select(m.Issue)
    for col, val in ((m.Issue.status, status), (m.Issue.severity, severity), (m.Issue.rule_id, rule_id),
                     (m.Issue.entity, entity), (m.Issue.school_code, school_code)):
        if val:
            q = q.where(col == val)
    issues = scope.filter_issues(s, who, list(s.exec(q.order_by(m.Issue.id))))
    return [issue_out(i) for i in issues]


def _get_visible(s: Session, who: Identity, issue_id: int) -> m.Issue:
    issue = s.get(m.Issue, issue_id)
    if issue is None or not scope.can_see_issue(s, who, issue):
        raise HTTPException(404, "Issue not found.")  # same answer for "missing" and "not yours"
    return issue


@router.get("/issues/{issue_id}")
def get_issue(issue_id: int, request: Request, who: Identity = Depends(current_identity),
              s: Session = Depends(get_session)) -> dict:
    issue = _get_visible(s, who, issue_id)
    rule = next((r for r in request.app.state.rules if r.id == issue.rule_id), None)
    editable = list(actions.EDITABLE.get(issue.entity, {})) if who.role in ACTORS else []
    return issue_out(issue) | {
        "record": actions.record_snapshot(s, issue),
        "editable_fields": editable,
        "rule": {"id": rule.id, "version": rule.version, "title": rule.title, "addresses": rule.addresses} if rule else None,
    }


class NoteBody(BaseModel):
    note: str = Field(default="", max_length=500)


class EditBody(NoteBody):
    field: str
    value: str = Field(max_length=200)


def _act_and_revalidate(s: Session, request: Request, who: Identity, issue: m.Issue, entry: m.AuditEntry) -> dict:
    s.commit()
    result = run_validation(s, request.app.state.rules, [issue.school_code], who.actor, who.role.value)
    s.refresh(issue)
    return {"issue": issue_out(issue), "audit_id": entry.id, "summary": result["schools"][0]}


@router.post("/issues/{issue_id}/approve")
def approve(issue_id: int, body: NoteBody, request: Request,
            who: Identity = Depends(require(*ACTORS)), s: Session = Depends(get_session)) -> dict:
    issue = _get_visible(s, who, issue_id)
    return _act_and_revalidate(s, request, who, issue, actions.approve(s, issue, who, body.note))


@router.post("/issues/{issue_id}/edit")
def edit(issue_id: int, body: EditBody, request: Request,
         who: Identity = Depends(require(*ACTORS)), s: Session = Depends(get_session)) -> dict:
    issue = _get_visible(s, who, issue_id)
    return _act_and_revalidate(s, request, who, issue, actions.edit(s, issue, who, body.field, body.value, body.note))


@router.post("/issues/{issue_id}/hold")
def hold(issue_id: int, body: NoteBody, request: Request,
         who: Identity = Depends(require(Role.PRINCIPAL)), s: Session = Depends(get_session)) -> dict:
    issue = _get_visible(s, who, issue_id)
    return _act_and_revalidate(s, request, who, issue, actions.hold(s, issue, who, body.note))
