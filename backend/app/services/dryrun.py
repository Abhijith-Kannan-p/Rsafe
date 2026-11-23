"""Test submit: run every rule again, in memory, and show exactly what would be sent.

Nothing is stored and nothing is exported. The current findings are compared with the
decisions people have already made (by fingerprint, the same way a real validation run
does), so the verdict for each row is what would happen if the file were submitted now.
"""

from __future__ import annotations

import time
from collections import Counter
from typing import Any

from sqlmodel import Session, select

from .. import models as m
from .engine import run_rules
from .rules import RuleSpec
from .validation import dataset_from_db, fingerprint

# Row verdicts, from best to worst
SEND = "would_send"          # nothing undecided
WARN = "would_send_flagged"  # only medium or low problems left: likely accepted, but worth fixing
REJECT = "likely_rejected"   # an undecided high-severity problem
HELD = "held_back"           # a held flag: a person must decide before it can be sent

VERDICT_ORDER = {HELD: 0, REJECT: 1, WARN: 2, SEND: 3}

SENT_COLUMNS = ["student_ref", "name", "dob", "gender", "class_grade", "section", "guardian_name",
                "aadhaar_masked", "aadhaar_status", "enrolment_status", "transfer_status"]


def _decision(existing: m.Issue | None) -> str:
    """What the current finding means given the stored issue: open, held, decided or new."""
    if existing is None:
        return "new"  # found now, not yet in the issue list (data changed since the last run)
    if existing.status == "held":
        return "held"
    value_changed = existing.status == "edited" or (existing.status == "approved" and existing.suggested_field
                                                    and existing.suggested_value is not None)
    if existing.status == "resolved" or value_changed:
        return "back"  # a fixed problem is back: it would reopen
    if existing.status == "approved":
        return "decided"  # a person confirmed the record is right as it is
    return "open"


def dry_run(s: Session, rules: list[RuleSpec], code: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    data, ctx = dataset_from_db(s)
    results = [r for r in run_rules(rules, data, ctx) if r.school_code == code]
    ms = round((time.perf_counter() - t0) * 1000, 1)

    stored = {i.fingerprint: i for i in s.exec(select(m.Issue).where(m.Issue.school_code == code))}
    per_ref: dict[str, list[dict[str, Any]]] = {}
    other: list[dict[str, Any]] = []
    decisions: Counter[str] = Counter()
    for r in results:
        d = _decision(stored.get(fingerprint(r)))
        decisions[d] += 1
        item = {"rule_id": r.rule_id, "severity": r.severity, "title": r.title, "detail": r.detail, "decision": d}
        if r.entity == "student":
            per_ref.setdefault(r.entity_ref, []).append(item)
        else:
            other.append(item | {"entity": r.entity, "ref": r.entity_ref})

    rows = []
    verdicts: Counter[str] = Counter()
    for st in s.exec(select(m.Student).where(m.Student.school_code == code).order_by(m.Student.student_ref)):
        findings = per_ref.get(st.student_ref, [])
        pending = [f for f in findings if f["decision"] != "decided"]
        if any(f["decision"] == "held" for f in pending):
            verdict = HELD
        elif any(f["severity"] == "high" for f in pending):
            verdict = REJECT
        elif pending:
            verdict = WARN
        else:
            verdict = SEND
        verdicts[verdict] += 1
        values = {c: getattr(st, c, "") for c in SENT_COLUMNS if hasattr(st, c)}
        values["aadhaar_masked"] = f"XXXX XXXX {st.aadhaar_last4}" if st.aadhaar_last4 else ""
        rows.append({"values": values, "verdict": verdict, "findings": findings})
    rows.sort(key=lambda r: (VERDICT_ORDER[r["verdict"]], r["values"]["student_ref"]))

    total = len(rows)
    clean = verdicts[SEND] + verdicts[WARN]
    return {
        "school_code": code,
        "rules": {r.id: r.version for r in rules},
        "ran_ms": ms,
        "records": total,
        "verdicts": {k: verdicts.get(k, 0) for k in (SEND, WARN, REJECT, HELD)},
        "decisions": dict(decisions),
        "would_pass_pct": round(100 * clean / total) if total else 100,
        "ready": verdicts[REJECT] == 0 and verdicts[HELD] == 0,
        "other_findings": other,
        "columns": SENT_COLUMNS,
        "rows": rows,
        "exported": False,
    }
