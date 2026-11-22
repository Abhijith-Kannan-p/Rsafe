"""Audit log (Admin only): list, verify the hash chain, and a demo-only tamper button."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session, select

from .. import models as m
from ..auth import Identity, require
from ..config import DEMO_MODE
from ..db import get_session
from ..roles import Role
from ..services.audit import verify_chain

router = APIRouter(prefix="/api/audit", tags=["audit"])
admin_only = require(Role.ADMIN)


def entry_out(e: m.AuditEntry) -> dict:
    return {
        "id": e.id, "ts": e.ts, "actor": e.actor, "role": e.role, "action": e.action,
        "record_ref": e.record_ref, "payload": json.loads(e.payload or "{}"),
        "hash": e.hash, "short_hash": e.hash[:10], "prev_hash": e.prev_hash,
    }


@router.get("")
def list_entries(limit: int = 500, _: Identity = Depends(admin_only), s: Session = Depends(get_session)) -> list[dict]:
    rows = s.exec(select(m.AuditEntry).order_by(m.AuditEntry.id.desc()).limit(min(limit, 5000)))
    return [entry_out(e) for e in rows]


@router.get("/verify")
def verify(_: Identity = Depends(admin_only), s: Session = Depends(get_session)) -> dict:
    return verify_chain(s).to_dict()


class TamperBody(BaseModel):
    entry_id: Optional[int] = None


@router.post("/tamper")
def tamper(body: TamperBody, _: Identity = Depends(admin_only), s: Session = Depends(get_session)) -> dict:
    """DEMO ONLY. Edits a row straight in the database, bypassing the audit service, to show
    that verification catches it. Deliberately not logged (it simulates an attacker)."""
    if not DEMO_MODE:
        raise HTTPException(404, "Not found.")
    if body.entry_id is not None:
        target = s.get(m.AuditEntry, body.entry_id)
    else:  # prefer a human action in the middle of the chain; fall back to any row
        rows = list(s.exec(select(m.AuditEntry).order_by(m.AuditEntry.id)))
        human = [r for r in rows if r.action.startswith("issue.")]
        pool = human or rows
        target = pool[len(pool) // 2] if pool else None
    if target is None:
        raise HTTPException(404, "No audit rows to tamper with.")
    payload = json.loads(target.payload or "{}")
    payload["note"] = (payload.get("note") or "") + " [silently edited]"
    if payload.get("new") is not None:
        payload["new"] = f"{payload['new']} (changed)"
    s.execute(text("UPDATE auditentry SET payload = :p WHERE id = :id"),
              {"p": json.dumps(payload, sort_keys=True, separators=(",", ":")), "id": target.id})
    s.commit()
    return {"tampered_id": target.id, "message": "Row edited directly in the database. Now run Verify chain."}
