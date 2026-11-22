"""Exports: cleaned CSV (masked IDs, current values) and the readiness report."""

import csv
import io

from sqlmodel import select

from app.models import AuditEntry
from tests.conftest import login


def rows(text):
    return list(csv.DictReader(io.StringIO(text)))


def test_csv_has_current_values_and_status(client, seeded_db):
    login(client, "principal", "SYN-0002")
    issue = next(i for i in client.get("/api/issues", params={"rule_id": "STU-005"}).json() if "Ananya" in i["detail"])
    client.post(f"/api/issues/{issue['id']}/approve", json={})
    r = client.get("/api/export/csv")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = {x["student_ref"]: x for x in rows(r.text)}
    assert len(data) == client.get("/api/summary").json()["schools"][0]["students"]
    assert data[issue["entity_ref"]]["name"] == "Ananya R. Kumar"
    assert {x["rsafe_status"] for x in data.values()} <= {"ready", "needs_review", "held"}
    assert any(x["rsafe_status"] == "needs_review" and x["rsafe_open_rules"] for x in data.values())
    assert all(x["aadhaar_masked"] == "" or x["aadhaar_masked"].startswith("XXXX XXXX ") for x in data.values())
    assert "aadhaar" not in rows(r.text)[0]


def test_held_students_marked_held(client, seeded_db):
    login(client, "principal", "SYN-0001")
    held = {i["entity_ref"] for i in client.get("/api/issues", params={"status": "held"}).json()}
    data = {x["student_ref"]: x for x in rows(client.get("/api/export/csv").text)}
    assert held and all(data[ref]["rsafe_status"] == "held" for ref in held)


def test_export_is_audited(client, seeded_db, db):
    login(client, "principal", "SYN-0002")
    client.get("/api/export/csv")
    client.get("/api/export/report")
    db.expire_all()
    last = db.exec(select(AuditEntry).order_by(AuditEntry.id.desc())).all()[:2]
    assert [e.action for e in last] == ["export.report", "export.csv"]


def test_report_lists_decisions_and_chain(client, seeded_db):
    login(client, "principal", "SYN-0002")
    issue = client.get("/api/issues", params={"status": "open"}).json()[0]
    client.post(f"/api/issues/{issue['id']}/hold", json={"note": "checking with parent"})
    html = client.get("/api/export/report").text
    assert "Submission readiness report" in html and "SYN-0002" in html
    assert "checking with parent" in html and "Demo Principal" in html
    assert "chain intact" in html and "synthetic" in html.lower()


def test_report_escapes_notes(client, seeded_db):
    login(client, "principal", "SYN-0002")
    issue = client.get("/api/issues", params={"status": "open"}).json()[0]
    client.post(f"/api/issues/{issue['id']}/hold", json={"note": "<script>alert(1)</script>"})
    html = client.get("/api/export/report").text
    assert "<script>alert" not in html and "&lt;script&gt;" in html


def test_mis_exports_cluster_school_with_code(client, seeded_db):
    login(client, "mis_coordinator")
    assert client.get("/api/export/csv").status_code == 400
    assert client.get("/api/export/csv", params={"school_code": "SYN-0003"}).status_code == 200


def test_export_scoping(client, seeded_db):
    login(client, "principal", "SYN-0001")
    assert client.get("/api/export/csv", params={"school_code": "SYN-0002"}).status_code == 404
    for role in ("teacher", "admin", "student_parent"):
        login(client, role)
        assert client.get("/api/export/csv").status_code == 403
        assert client.get("/api/export/report").status_code == 403
