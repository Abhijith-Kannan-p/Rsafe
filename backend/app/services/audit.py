"""Tamper-evident audit log.

Each row stores prev_hash and
    hash = SHA256(prev_hash + canonical_json({ts, actor, role, action, record_ref, payload}))
so changing any field of any row, deleting a row, or reordering rows breaks the chain from
that row onwards. verify_chain() walks the chain and reports the first broken row.

Limit: removing rows from the END of the chain is not detectable from the chain alone. A real
deployment would periodically publish the latest hash somewhere outside the database.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from ..models import AuditEntry

GENESIS = "0" * 64
_append_lock = threading.Lock()


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def compute_hash(prev_hash: str, ts: str, actor: str, role: str, action: str, record_ref: str, payload: str) -> str:
    body = canonical({"ts": ts, "actor": actor, "role": role, "action": action,
                      "record_ref": record_ref, "payload": payload})
    return hashlib.sha256((prev_hash + body).encode("utf-8")).hexdigest()


def row_hash(row: AuditEntry) -> str:
    return compute_hash(row.prev_hash, row.ts, row.actor, row.role, row.action, row.record_ref, row.payload)


def append(s: Session, actor: str, role: str, action: str, record_ref: str = "",
           payload: dict[str, Any] | None = None, commit: bool = True) -> AuditEntry:
    """Append one row. Serialised by a lock so two writers cannot fork the chain."""
    with _append_lock:
        last = s.exec(select(AuditEntry).order_by(AuditEntry.id.desc()).limit(1)).first()
        prev = last.hash if last else GENESIS
        ts = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        body = canonical(payload or {})
        row = AuditEntry(ts=ts, actor=actor, role=role, action=action, record_ref=record_ref,
                         payload=body, prev_hash=prev)
        row.hash = row_hash(row)
        s.add(row)
        if commit:
            s.commit()
            s.refresh(row)
        else:
            s.flush()
        return row


@dataclass
class ChainReport:
    ok: bool
    checked: int
    first_broken_id: int | None = None
    reason: str | None = None
    head_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def verify_chain(s: Session) -> ChainReport:
    prev = GENESIS
    checked = 0
    for row in s.exec(select(AuditEntry).order_by(AuditEntry.id)):
        if row.prev_hash != prev:
            return ChainReport(False, checked, row.id,
                               "This row does not point to the row before it. A row was removed, inserted or reordered.")
        if row_hash(row) != row.hash:
            return ChainReport(False, checked, row.id,
                               "This row's contents were changed after it was written.")
        prev = row.hash
        checked += 1
    return ChainReport(True, checked, head_hash=prev if checked else None)
