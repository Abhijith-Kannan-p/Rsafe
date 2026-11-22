"""Exports: the cleaned student CSV and a one-page HTML "Submission readiness report".

"Cleaned" means the current values after the human decisions in the audit log. The file
never holds a full Aadhaar number (Rsafe doesn't have one): it carries the masked last four
digits, and the school re-attaches the real number from its own system when submitting.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from typing import Any

from sqlmodel import Session, select

from .. import models as m
from ..config import SYNTHETIC_NOTICE
from .audit import verify_chain
from .validation import ACTIVE, school_summary

CSV_COLUMNS = [
    "student_ref", "school_code", "admission_no", "name", "dob", "gender", "class_grade", "section",
    "guardian_name", "aadhaar_masked", "aadhaar_status", "enrolment_status", "previous_school_code",
    "transfer_status", "rsafe_status", "rsafe_open_rules",
]


def _active_by_student(s: Session, code: str) -> dict[str, list[m.Issue]]:
    out: dict[str, list[m.Issue]] = defaultdict(list)
    for i in s.exec(select(m.Issue).where(m.Issue.school_code == code, m.Issue.entity == "student",
                                          m.Issue.status.in_(ACTIVE))):  # type: ignore[attr-defined]
        out[i.entity_ref].append(i)
    return out


def cleaned_csv(s: Session, code: str) -> tuple[str, dict[str, int]]:
    active = _active_by_student(s, code)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
    w.writeheader()
    counts: Counter[str] = Counter()
    for st in s.exec(select(m.Student).where(m.Student.school_code == code).order_by(m.Student.student_ref)):
        issues = active.get(st.student_ref, [])
        status = "held" if any(i.status == "held" for i in issues) else "needs_review" if issues else "ready"
        counts[status] += 1
        row = {c: getattr(st, c, "") for c in CSV_COLUMNS if hasattr(st, c)}
        row["aadhaar_masked"] = f"XXXX XXXX {st.aadhaar_last4}" if st.aadhaar_last4 else ""
        row["rsafe_status"] = status
        row["rsafe_open_rules"] = " ".join(sorted({i.rule_id for i in issues}))
        w.writerow({k: ("" if v is None else v) for k, v in row.items()})
    return buf.getvalue(), dict(counts)


def _decisions(s: Session, code: str) -> list[dict[str, Any]]:
    rows = []
    for e in s.exec(select(m.AuditEntry).where(m.AuditEntry.action.startswith("issue.")).order_by(m.AuditEntry.id)):  # type: ignore[attr-defined]
        p = json.loads(e.payload or "{}")
        if p.get("school_code") == code:
            rows.append({"ts": e.ts, "actor": e.actor, "role": e.role, "action": e.action.split(".", 1)[1],
                         "record": e.record_ref, "rule": p.get("rule_id"), "field": p.get("field"),
                         "old": p.get("old"), "new": p.get("new"), "note": p.get("note") or ""})
    return rows


def report_data(s: Session, code: str, rules) -> dict[str, Any]:
    school = s.get(m.School, code)
    issues = list(s.exec(select(m.Issue).where(m.Issue.school_code == code)))
    by_status = Counter(i.status for i in issues)
    chain = verify_chain(s)
    return {
        "school": {"code": code, "name": school.name if school else code,
                   "district": school.district if school else "", "block": school.block if school else ""},
        "summary": school_summary(s, code),
        "found": len(issues),
        "fixed": by_status.get("approved", 0) + by_status.get("edited", 0),
        "resolved": by_status.get("resolved", 0),
        "held": [i for i in issues if i.status == "held"],
        "open_by_rule": Counter(i.rule_id for i in issues if i.status == "open"),
        "decisions": _decisions(s, code),
        "rules": {r.id: r.version for r in rules},
        "chain_ok": chain.ok,
        "chain_rows": chain.checked,
    }


def _fmt_change(d: dict) -> str:
    if not d["field"]:
        return "No change to the record"
    return f"{escape(str(d['field']))}: {escape(str(d['old'] or '(empty)'))} &rarr; {escape(str(d['new']))}"


def report_html(s: Session, code: str, rules, actor: str) -> str:
    d = report_data(s, code, rules)
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    sm = d["summary"]
    e = escape
    held_rows = "".join(
        f"<tr><td>{e(i.rule_id)}</td><td>{e(i.entity_ref)}</td><td>{e(i.detail)}</td></tr>" for i in d["held"]
    ) or '<tr><td colspan="3" class="muted">Nothing is on hold.</td></tr>'
    dec_rows = "".join(
        f"<tr><td>{e(x['ts'][:16].replace('T', ' '))}</td><td>{e(x['actor'])}</td><td>{e(x['action'])}</td>"
        f"<td>{e(x['rule'] or '')}</td><td>{e(x['record'])}</td><td>{_fmt_change(x)}"
        f"{'<br><span class=muted>' + e(x['note']) + '</span>' if x['note'] else ''}</td></tr>"
        for x in d["decisions"]
    ) or '<tr><td colspan="6" class="muted">No decisions recorded yet.</td></tr>'
    open_rows = "".join(f"<li><b>{e(r)}</b>: {n}</li>" for r, n in sorted(d["open_by_rule"].items())) \
        or "<li>None</li>"
    rules = ", ".join(f"{e(k)} v{e(v)}" for k, v in sorted(d["rules"].items()))
    chain = (f'<span class="ok">Verified: {d["chain_rows"]} audit rows, chain intact</span>' if d["chain_ok"]
             else '<span class="bad">Audit chain is BROKEN. Do not submit until an admin investigates.</span>')
    tone = "ok" if sm["readiness"] >= 85 else "warn" if sm["readiness"] >= 60 else "bad"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Readiness report {e(code)}</title>
<style>
  :root {{ --ink:#0A1230; --cream:#F7F0E1; --sand:#E9DCC0; --coral:#B3261E; --aqua:#0B7A6C; --saffron:#8A5A00; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--cream); color:var(--ink); font: 14px/1.5 Inter, system-ui, sans-serif; }}
  main {{ max-width: 960px; margin: 0 auto; padding: 32px 28px; }}
  h1 {{ font: 700 26px/1.2 Sora, Inter, sans-serif; margin: 0; }}
  h2 {{ font: 600 16px/1.3 Sora, Inter, sans-serif; margin: 28px 0 8px; }}
  .muted {{ color: #4a5170; }}
  .top {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; border-bottom:2px solid var(--ink); padding-bottom:14px; }}
  .stats {{ display:grid; grid-template-columns: repeat(5, 1fr); gap:10px; margin-top:18px; }}
  .stat {{ background:#fff; border:1px solid var(--sand); border-radius:12px; padding:10px 12px; }}
  .stat b {{ display:block; font: 700 24px Sora, Inter, sans-serif; }}
  .ok {{ color: var(--aqua); font-weight:600; }} .warn {{ color: var(--saffron); font-weight:600; }} .bad {{ color: var(--coral); font-weight:600; }}
  table {{ width:100%; border-collapse: collapse; font-size: 12.5px; }}
  th, td {{ text-align:left; padding:6px 8px; border-bottom:1px solid var(--sand); vertical-align: top; }}
  th {{ font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color:#4a5170; }}
  .notice {{ margin-top: 28px; padding: 10px 12px; border:1px dashed var(--ink); border-radius: 10px; font-size: 12px; }}
  button {{ font: 600 13px Inter, sans-serif; background: var(--ink); color: var(--cream); border: 0; border-radius: 999px; padding: 8px 16px; cursor: pointer; }}
  @media print {{ button {{ display:none; }} main {{ padding: 0; }} body {{ background: #fff; }} }}
</style></head>
<body><main>
  <div class="top">
    <div>
      <div class="muted">Rsafe &middot; Submission readiness report</div>
      <h1>{e(d['school']['name'])} ({e(code)})</h1>
      <div class="muted">{e(d['school']['block'])}, {e(d['school']['district'])} &middot; generated {now} by {e(actor)}</div>
    </div>
    <button type="button" onclick="window.print()">Print or save as PDF</button>
  </div>
  <div class="stats">
    <div class="stat">Readiness<b class="{tone}">{sm['readiness']}%</b></div>
    <div class="stat">Issues found<b>{d['found']}</b></div>
    <div class="stat">Fixed by a person<b>{d['fixed']}</b></div>
    <div class="stat">Held for review<b>{len(d['held'])}</b></div>
    <div class="stat">Still open<b>{sum(d['open_by_rule'].values())}</b></div>
  </div>
  <p class="muted">{sm['students']} student records. {d['resolved']} issue(s) cleared on re-check after a related fix.</p>
  <h2>Audit chain</h2><p>{chain}</p>
  <h2>Held for review</h2>
  <table><thead><tr><th>Rule</th><th>Record</th><th>Reason</th></tr></thead><tbody>{held_rows}</tbody></table>
  <h2>Still open, by rule</h2><ul>{open_rows}</ul>
  <h2>Decisions (who approved what)</h2>
  <table><thead><tr><th>Time (UTC)</th><th>By</th><th>Action</th><th>Rule</th><th>Record</th><th>Change</th></tr></thead><tbody>{dec_rows}</tbody></table>
  <h2>Rules used</h2><p class="muted">{rules}</p>
  <div class="notice">{e(SYNTHETIC_NOTICE)} Nothing is submitted to UDISE+ by Rsafe; a person uploads the file.</div>
</main></body></html>"""
