"""Read-only views that help people decide: test submit, readiness trend, rule coverage, search.

None of these change data. Test submit writes one audit row so the log shows who checked.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlmodel import Session, col, or_, select

from .. import models as m
from ..auth import Identity, require
from ..db import get_session
from ..roles import Role
from ..services import audit, scope
from ..services.dryrun import dry_run
from ..services.validation import ACTIVE

router = APIRouter(prefix="/api", tags=["insights"])

STAFF = (Role.PRINCIPAL, Role.TEACHER, Role.MIS_COORDINATOR, Role.ADMIN)
OVERSEERS = (Role.PRINCIPAL, Role.MIS_COORDINATOR, Role.ADMIN)


def _one_school(s: Session, who: Identity, school_code: Optional[str]) -> str:
    allowed = scope.visible_schools(s, who)
    code = school_code or (who.school_code if who.school_code in allowed else None) or (allowed[0] if len(allowed) == 1 else None)
    if not code:
        raise HTTPException(400, "Choose a school.")
    if code not in allowed:
        raise HTTPException(404, "School not found.")
    return code


# ------------------------------------------------------------------ test submit

class DryRunBody(BaseModel):
    school_code: Optional[str] = None


@router.post("/submit/dry-run")
def submit_dry_run(body: DryRunBody, request: Request,
                   who: Identity = Depends(require(Role.PRINCIPAL, Role.MIS_COORDINATOR)),
                   s: Session = Depends(get_session)) -> dict:
    code = _one_school(s, who, body.school_code)
    result = dry_run(s, request.app.state.rules, code)
    audit.append(s, who.actor, who.role.value, "submit.dry_run", f"school:{code}",
                 {"school_code": code, "verdicts": result["verdicts"], "exported": False})
    return result


# ------------------------------------------------------------------ readiness trend

@router.get("/trend")
def trend(school_code: Optional[str] = None, who: Identity = Depends(require(*OVERSEERS)),
          s: Session = Depends(get_session)) -> dict:
    """Readiness after every validation run for one school, with the action that caused each run.
    Read from the audit log, so it survives restarts and cannot be edited quietly."""
    code = _one_school(s, who, school_code)
    rows = list(s.exec(select(m.AuditEntry).order_by(m.AuditEntry.id)))
    points: list[dict[str, Any]] = []
    prev: m.AuditEntry | None = None
    for e in rows:
        if e.action == "validation.run":
            p = json.loads(e.payload or "{}")
            if code in (p.get("readiness") or {}):
                cause = None
                if prev is not None and prev.action != "validation.run":
                    pp = json.loads(prev.payload or "{}")
                    cause = {"action": prev.action, "actor": prev.actor, "record": prev.record_ref,
                             "rule_id": pp.get("rule_id")}
                points.append({"audit_id": e.id, "ts": e.ts, "readiness": p["readiness"][code], "cause": cause})
        prev = e
    return {"school_code": code, "points": points}


# ------------------------------------------------------------------ rule coverage

@router.get("/coverage")
def coverage(request: Request, who: Identity = Depends(require(*OVERSEERS)),
             s: Session = Depends(get_session)) -> dict:
    """Which government-reported failure reason each rule addresses, and what it has caught here."""
    schools = scope.visible_schools(s, who)
    issues = list(s.exec(select(m.Issue).where(col(m.Issue.school_code).in_(schools))))
    by_rule: dict[str, dict[str, int]] = defaultdict(lambda: {"found": 0, "active": 0, "fixed": 0, "resolved": 0})
    for i in issues:
        c = by_rule[i.rule_id]
        c["found"] += 1
        c["active"] += i.status in ACTIVE
        c["fixed"] += i.status in ("approved", "edited")
        c["resolved"] += i.status == "resolved"
    reasons: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in request.app.state.rules:
        reasons[r.addresses or "Other"].append({
            "id": r.id, "version": r.version, "title": r.title, "severity": r.severity, "entity": r.entity,
            "hold": r.hold, **by_rule[r.id],
        })
    out = []
    for reason, rules in sorted(reasons.items()):
        out.append({
            "reason": reason, "rules": rules,
            "found": sum(x["found"] for x in rules), "active": sum(x["active"] for x in rules),
            "fixed": sum(x["fixed"] for x in rules), "resolved": sum(x["resolved"] for x in rules),
        })
    return {"schools": schools, "reasons": out}


# ------------------------------------------------------------------ search (command palette)

@router.get("/search")
def search(q: str = Query(min_length=2, max_length=60), who: Identity = Depends(require(*STAFF)),
           s: Session = Depends(get_session)) -> list[dict]:
    """Students the caller may see whose ID or name contains the text. Never searches Aadhaar."""
    schools = scope.visible_schools(s, who)
    refs = scope.visible_student_refs(s, who)
    like = f"%{q.strip()}%"
    stmt = (select(m.Student).where(col(m.Student.school_code).in_(schools))
            .where(or_(col(m.Student.student_ref).ilike(like), col(m.Student.name).ilike(like)))
            .order_by(m.Student.student_ref).limit(40))
    found = [st for st in s.exec(stmt) if refs is None or st.student_ref in refs][:8]
    out = []
    for st in found:
        issues = list(s.exec(select(m.Issue).where(m.Issue.entity == "student", m.Issue.entity_ref == st.student_ref)
                             .order_by(m.Issue.id)))
        active = [i for i in issues if i.status in ACTIVE]
        first = (active or issues or [None])[0]
        out.append({"student_ref": st.student_ref, "name": st.name, "school_code": st.school_code,
                    "class": f"{st.class_grade or '?'}{st.section or ''}", "active": len(active),
                    "issue_id": first.id if first else None})
    return out
