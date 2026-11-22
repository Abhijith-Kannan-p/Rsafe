"""Hash-chained audit log: a clean chain passes; edits, deletions and forgeries are caught."""

import json

from sqlalchemy import text
from sqlmodel import Session, select

from app.db import engine
from app.models import AuditEntry
from app.services import audit
from tests.conftest import login


def fresh_chain(n=5) -> Session:
    from sqlmodel import SQLModel

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    s = Session(engine)
    for k in range(n):
        audit.append(s, f"actor{k}", "principal", "issue.approve", f"student:S{k}", {"k": k, "new": f"v{k}"})
    return s


def test_clean_chain_passes():
    s = fresh_chain()
    r = audit.verify_chain(s)
    assert r.ok and r.checked == 5 and r.first_broken_id is None
    rows = list(s.exec(select(AuditEntry).order_by(AuditEntry.id)))
    assert rows[0].prev_hash == audit.GENESIS
    assert all(b.prev_hash == a.hash for a, b in zip(rows, rows[1:]))
    assert r.head_hash == rows[-1].hash


def test_empty_chain_passes():
    s = fresh_chain(0)
    assert audit.verify_chain(s).ok


def test_edited_payload_reports_first_broken_row():
    s = fresh_chain()
    s.execute(text("UPDATE auditentry SET payload = :p WHERE id = 3"), {"p": '{"k":3,"new":"forged"}'})
    s.commit()
    r = audit.verify_chain(s)
    assert not r.ok and r.first_broken_id == 3 and r.checked == 2
    assert "changed" in r.reason


def test_edited_actor_is_caught():
    s = fresh_chain()
    s.execute(text("UPDATE auditentry SET actor = 'someone else' WHERE id = 2"))
    s.commit()
    assert audit.verify_chain(s).first_broken_id == 2


def test_recomputed_hash_still_breaks_the_next_link():
    # An attacker who edits row 2 AND fixes row 2's hash still breaks row 3's prev_hash link.
    s = fresh_chain()
    row = s.get(AuditEntry, 2)
    row.payload = '{"k":2,"new":"forged"}'
    row.hash = audit.row_hash(row)
    s.add(row)
    s.commit()
    r = audit.verify_chain(s)
    assert r.first_broken_id == 3 and "does not point" in r.reason


def test_deleted_row_is_caught():
    s = fresh_chain()
    s.execute(text("DELETE FROM auditentry WHERE id = 3"))
    s.commit()
    assert audit.verify_chain(s).first_broken_id == 4


def test_payload_is_canonical_json():
    s = fresh_chain(1)
    row = s.get(AuditEntry, 1)
    assert row.payload == json.dumps({"k": 0, "new": "v0"}, sort_keys=True, separators=(",", ":"))


# --------------------------------------------------------------------------- via the API

def test_seed_writes_a_valid_chain(client, seeded_db):
    login(client, "admin")
    r = client.get("/api/audit/verify").json()
    assert r["ok"] and r["checked"] >= 2  # data.load + validation.run
    actions = [e["action"] for e in client.get("/api/audit").json()]
    assert "data.load" in actions and "validation.run" in actions


def test_tamper_button_then_verify_fails_at_that_row(client, seeded_db):
    login(client, "principal")
    issue = next(i for i in client.get("/api/issues").json() if i["suggested_value"] and i["status"] == "open")
    client.post(f"/api/issues/{issue['id']}/approve", json={"note": "checked register"})

    login(client, "admin")
    assert client.get("/api/audit/verify").json()["ok"]
    tampered = client.post("/api/audit/tamper", json={}).json()["tampered_id"]
    entry = next(e for e in client.get("/api/audit").json() if e["id"] == tampered)
    assert entry["action"].startswith("issue.")  # the demo picks a human action
    r = client.get("/api/audit/verify").json()
    assert not r["ok"] and r["first_broken_id"] == tampered


def test_audit_entries_have_short_hash(client, seeded_db):
    login(client, "admin")
    e = client.get("/api/audit").json()[0]
    assert len(e["short_hash"]) == 10 and e["hash"].startswith(e["short_hash"])
