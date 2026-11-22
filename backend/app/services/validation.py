"""Run the rules against the database and store the results as Issues.

Re-runs keep human decisions: an issue is identified by its fingerprint, so an approved,
edited or held issue keeps its status. Open or held issues that no longer appear become
"resolved". Results are always computed over ALL schools (cross-school duplicates need
that), but only the requested schools' issues are written.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from .. import models as m
from . import audit
from .context import Context
from .engine import IssueResult, readiness_score, run_rules
from .rules import RuleSpec

ACTIVE = ("open", "held")


def _rows(s: Session, model) -> list[dict[str, Any]]:
    return [r.model_dump() for r in s.exec(select(model))]


def dataset_from_db(s: Session) -> tuple[dict[str, list[dict]], Context]:
    ctx = Context.build(
        prior_year=_rows(s, m.PriorYearRecord),
        admission_register=_rows(s, m.AdmissionRegisterEntry),
        attendance=_rows(s, m.AttendanceRecord),
        fees=_rows(s, m.FeeRecord),
        assignments=_rows(s, m.TeacherAssignment),
        maintenance=_rows(s, m.MaintenanceLog),
        schools=_rows(s, m.School),
    )
    data = {"student": _rows(s, m.Student), "teacher": _rows(s, m.Teacher), "facility": _rows(s, m.Facility)}
    return data, ctx


def fingerprint(r: IssueResult) -> str:
    return hashlib.sha256(f"{r.rule_id}|{r.entity}|{r.entity_ref}|{r.detail}".encode()).hexdigest()[:32]


def _sync_school(s: Session, code: str, results: list[IssueResult]) -> dict[str, int]:
    existing = {i.fingerprint: i for i in s.exec(select(m.Issue).where(m.Issue.school_code == code))}
    now = datetime.now(timezone.utc)
    seen: set[str] = set()
    added = reopened = resolved = 0
    for r in results:
        fp = fingerprint(r)
        if fp in seen:
            continue
        seen.add(fp)
        start = "held" if r.held else "open"
        if fp in existing:
            e = existing[fp]
            e.rule_version, e.evidence, e.confidence = r.rule_version, r.evidence, r.confidence
            if e.status == "resolved":
                e.status, e.updated_at = start, now
                reopened += 1
            continue
        s.add(m.Issue(
            fingerprint=fp, rule_id=r.rule_id, rule_version=r.rule_version, severity=r.severity,
            entity=r.entity, entity_ref=r.entity_ref, school_code=r.school_code, title=r.title,
            message=r.message, detail=r.detail, fix=r.fix, confidence=r.confidence,
            suggested_value=r.suggested_value, suggested_field=r.suggested_field,
            evidence=r.evidence, status=start,
        ))
        added += 1
    for fp, e in existing.items():
        if fp not in seen and e.status in ACTIVE:
            e.status, e.updated_at = "resolved", now
            resolved += 1
    return {"added": added, "reopened": reopened, "resolved": resolved}


def school_summary(s: Session, code: str) -> dict[str, Any]:
    issues = list(s.exec(select(m.Issue).where(m.Issue.school_code == code)))
    students = len(list(s.exec(select(m.Student.id).where(m.Student.school_code == code))))
    active = [i for i in issues if i.status in ACTIVE]
    student_active = [i for i in active if i.entity == "student"]
    return {
        "school_code": code,
        "students": students,
        "readiness": readiness_score(students, student_active),  # type: ignore[arg-type]
        "by_severity": dict(Counter(i.severity for i in active)),
        "by_status": dict(Counter(i.status for i in issues)),
        "active": len(active),
        "held": sum(i.status == "held" for i in issues),
    }


def run_validation(s: Session, rules: list[RuleSpec], schools: list[str],
                   actor: str, role: str) -> dict[str, Any]:
    data, ctx = dataset_from_db(s)
    results = run_rules(rules, data, ctx)
    by_school: dict[str, list[IssueResult]] = {}
    for r in results:
        by_school.setdefault(r.school_code, []).append(r)
    changes = {code: _sync_school(s, code, by_school.get(code, [])) for code in schools}
    s.flush()
    summaries = [school_summary(s, code) for code in schools]
    audit.append(s, actor, role, "validation.run", ",".join(schools), {
        "schools": schools,
        "rules": {r.id: r.version for r in rules},
        "changes": changes,
        "readiness": {x["school_code"]: x["readiness"] for x in summaries},
    }, commit=False)
    s.commit()
    return {"schools": summaries, "changes": changes}
