"""Runs loaded rules over records and produces issues. Never modifies the records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .checks import REGISTRY, Finding
from .context import Context
from .rules import SEVERITY_RANK, RuleSpec

ENTITY_REF = {"student": "student_ref", "teacher": "teacher_ref", "facility": "facility_ref"}


@dataclass
class IssueResult:
    rule_id: str
    rule_version: str
    severity: str
    entity: str
    entity_ref: str
    school_code: str
    title: str
    message: str  # the rule's plain-language reason
    detail: str  # what exactly is wrong with this record
    fix: str
    evidence: dict[str, Any] = field(default_factory=dict)
    confidence: str | None = None
    suggested_value: str | None = None
    suggested_field: str | None = None
    held: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_list(result: Finding | list[Finding] | None) -> list[Finding]:
    if result is None:
        return []
    return result if isinstance(result, list) else [result]


def _issue(rule: RuleSpec, rec: dict, f: Finding) -> IssueResult:
    return IssueResult(
        rule_id=rule.id,
        rule_version=rule.version,
        severity=rule.severity,
        entity=rule.entity,
        entity_ref=str(rec.get(ENTITY_REF[rule.entity], "")),
        school_code=str(rec.get("school_code", "")),
        title=rule.title,
        message=rule.message,
        detail=f.detail,
        fix=rule.fix,
        evidence=f.evidence,
        confidence=f.confidence,
        suggested_value=f.suggested_value,
        suggested_field=f.field,
        held=rule.hold,
    )


def run_rules(rules: list[RuleSpec], data: dict[str, list[dict]], ctx: Context) -> list[IssueResult]:
    """data maps entity name ('student', 'teacher', 'facility') to its records."""
    issues: list[IssueResult] = []
    for rule in rules:
        check = REGISTRY[rule.check]
        records = data.get(rule.entity, [])
        if check.scope == "record":
            for rec in records:
                for f in _as_list(check.fn(rec, ctx, rule.params)):
                    issues.append(_issue(rule, rec, f))
        else:
            for rec, f in check.fn(records, ctx, rule.params):
                issues.append(_issue(rule, rec, f))
    issues.sort(key=lambda i: (SEVERITY_RANK[i.severity], i.rule_id, i.school_code, i.entity_ref))
    return issues


def readiness_score(total_records: int, issues: list[IssueResult]) -> int:
    """Share of records with no high-severity issue, minus a smaller weight for medium/low.

    Simple and explainable on purpose; refined when the dashboard lands (Phase 5).
    """
    if total_records == 0:
        return 100
    worst: dict[str, int] = {}
    for i in issues:
        key = f"{i.entity}:{i.entity_ref}"
        worst[key] = min(worst.get(key, 9), SEVERITY_RANK[i.severity])
    weight = {0: 1.0, 1: 0.5, 2: 0.2}
    penalty = sum(weight[w] for w in worst.values())
    return max(0, round(100 * (1 - penalty / total_records)))
