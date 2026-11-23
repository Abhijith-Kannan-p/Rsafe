"""Demo reset and the health / metrics endpoint.

Reset is a demo-only convenience (RSAFE_DEMO_MODE=1, the default for this prototype). It
rebuilds the database from the committed synthetic data, which also starts a new audit log;
the first rows after a reset say who reset it.
"""

from __future__ import annotations

import json
import statistics
import time
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlmodel import Session, select

from .. import __version__
from .. import models as m
from ..auth import Identity, current_identity
from ..config import DATA_DIR, DEMO_MODE
from ..db import engine, get_session
from ..services import audit
from ..services.loader import seed_and_validate

router = APIRouter(prefix="/api", tags=["demo"])
STARTED = time.time()


@router.post("/demo/reset")
def reset(who: Identity = Depends(current_identity)) -> dict:
    if not DEMO_MODE:
        raise HTTPException(404, "Not found.")
    result = seed_and_validate(DATA_DIR, engine)
    with Session(engine) as s:
        entry = audit.append(s, who.actor, who.role.value, "demo.reset", "data",
                             {"synthetic": True, "counts": result["counts"]})
        audit_id = entry.id
    return {"reset": True, "audit_id": audit_id, "counts": result["counts"],
            "schools": result["validation"]["schools"]}


def _count(s: Session, model) -> int:
    return s.exec(select(func.count()).select_from(model)).one()


@router.get("/metrics")
def metrics(request: Request, s: Session = Depends(get_session)) -> dict[str, Any]:
    """Health plus scalability numbers. Public on purpose (like /api/health): counts and timings
    only, no names, refs or tokens."""
    runs = []
    rows = s.exec(select(m.AuditEntry).where(m.AuditEntry.action == "validation.run")
                  .order_by(m.AuditEntry.id.desc()).limit(20))  # type: ignore[union-attr]
    for e in rows:
        t = json.loads(e.payload or "{}").get("timing")
        if not t:
            continue
        per_k = round(t["total_ms"] / t["records"] * 1000, 1) if t.get("records") else None
        runs.append({"audit_id": e.id, "ts": e.ts, "schools": len(json.loads(e.payload).get("schools", [])),
                     "records": t.get("records"), "total_ms": t["total_ms"], "rules_ms": t["rules_ms"],
                     "read_ms": t["read_ms"], "store_ms": t["store_ms"], "ms_per_1000_records": per_k})
    per_k_values = [r["ms_per_1000_records"] for r in runs if r["ms_per_1000_records"] is not None]
    rules = request.app.state.rules
    return {
        "status": "ok",
        "version": __version__,
        "synthetic": True,
        "uptime_s": round(time.time() - STARTED),
        "rules": {"loaded": len(rules), "versions": {r.id: r.version for r in rules}},
        "data": {"schools": _count(s, m.School), "students": _count(s, m.Student), "teachers": _count(s, m.Teacher),
                 "facilities": _count(s, m.Facility), "attendance_rows": _count(s, m.AttendanceRecord)},
        "issues": dict(Counter(i for i in s.exec(select(m.Issue.status)))),
        "audit_rows": _count(s, m.AuditEntry),
        "validation": {
            "recent_runs": runs,
            "median_ms_per_1000_records": statistics.median(per_k_values) if per_k_values else None,
            "projection_note": "Validation time grows roughly linearly with records. npm run bench measures 5,000 students.",
        },
    }
