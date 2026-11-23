"""Approve, edit and hold: change records only through a person, and always write the audit log."""

from sqlmodel import select

from app.models import AuditEntry, Issue, Student
from tests.conftest import login


def issues_by(client, **filters):
    return client.get("/api/issues", params=filters).json()


def last_audit(db):
    db.expire_all()
    return db.exec(select(AuditEntry).order_by(AuditEntry.id.desc())).first()


def student(db, ref):
    db.expire_all()
    return db.exec(select(Student).where(Student.student_ref == ref)).one()


def test_validation_does_not_change_records(client, seeded_db, db):
    before = [s.model_dump() for s in db.exec(select(Student).order_by(Student.id))]
    login(client, "principal")
    client.post("/api/validate", json={})
    db.expire_all()
    after = [s.model_dump() for s in db.exec(select(Student).order_by(Student.id))]
    assert before == after


def test_approve_applies_suggestion_and_resolves(client, seeded_db, db):
    login(client, "principal", "SYN-0002")
    issue = next(i for i in issues_by(client, rule_id="STU-005") if "Ananya" in i["detail"])
    r = client.post(f"/api/issues/{issue['id']}/approve", json={"note": "matches birth certificate"}).json()
    assert r["issue"]["status"] == "approved"
    assert student(db, issue["entity_ref"]).name == "Ananya R. Kumar"
    row = last_audit(db)  # last row is the automatic re-validation; the action is just before it
    action = db.get(AuditEntry, r["audit_id"])
    assert row.action == "validation.run"
    assert action.action == "issue.approve" and action.actor.startswith("Demo Principal")
    assert '"old":"Ananya Kumar"' in action.payload and '"new":"Ananya R. Kumar"' in action.payload
    # Re-running keeps the decision and does not raise the issue again
    client.post("/api/validate", json={})
    assert not [i for i in issues_by(client, rule_id="STU-005", status="open") if i["entity_ref"] == issue["entity_ref"]]


def test_edit_with_valid_value(client, seeded_db, db):
    login(client, "principal", "SYN-0002")
    issue = next(i for i in issues_by(client, rule_id="STU-002") if "31/02/2015" in i["detail"])
    r = client.post(f"/api/issues/{issue['id']}/edit", json={"field": "dob", "value": "28/02/2015"})
    assert r.status_code == 200, r.text
    assert r.json()["issue"]["status"] == "edited"
    assert student(db, issue["entity_ref"]).dob == "28/02/2015"


def test_edit_rejects_bad_values_and_changes_nothing(client, seeded_db, db):
    login(client, "principal", "SYN-0002")
    issue = next(i for i in issues_by(client, rule_id="STU-002") if "31/02/2015" in i["detail"])
    audit_before = last_audit(db).id
    for body, msg in [
        ({"field": "dob", "value": "31/02/2015"}, "DD/MM/YYYY"),
        ({"field": "aadhaar_token", "value": "x"}, "cannot be edited"),
        ({"field": "name", "value": "0123 4567 8901"}, "ID number"),
        ({"field": "class_grade", "value": "15"}, "1 to 12"),
    ]:
        r = client.post(f"/api/issues/{issue['id']}/edit", json=body)
        assert r.status_code == 422 and msg in r.json()["detail"], (body, r.text)
    assert student(db, issue["entity_ref"]).dob == "31/02/2015"
    assert last_audit(db).id == audit_before


def test_hold_then_cannot_hold_again(client, seeded_db, db):
    login(client, "principal", "SYN-0002")
    issue = issues_by(client, status="open")[0]
    assert client.post(f"/api/issues/{issue['id']}/hold", json={"note": "ask parent"}).json()["issue"]["status"] == "held"
    assert client.post(f"/api/issues/{issue['id']}/hold", json={}).status_code == 409
    assert db.get(AuditEntry, last_audit(db).id - 1).action == "issue.hold"


def test_dropout_flag_is_held_and_record_untouched(client, seeded_db, db):
    login(client, "principal", "SYN-0001")
    held = issues_by(client, rule_id="STU-008")
    assert held and all(i["status"] == "held" for i in held)
    for i in held:
        assert student(db, i["entity_ref"]).enrolment_status == "dropout"  # flag recorded, not acted on


def test_principal_releases_held_dropout_by_setting_active(client, seeded_db, db):
    login(client, "principal", "SYN-0001")
    i = issues_by(client, rule_id="STU-008")[0]
    r = client.post(f"/api/issues/{i['id']}/edit",
                    json={"field": "enrolment_status", "value": "active", "note": "attends daily"})
    assert r.status_code == 200 and r.json()["issue"]["status"] == "edited"
    assert student(db, i["entity_ref"]).enrolment_status == "active"


def test_confirm_without_suggestion(client, seeded_db, db):
    login(client, "principal", "SYN-0001")
    i = issues_by(client, rule_id="STU-008")[0]
    r = client.post(f"/api/issues/{i['id']}/approve", json={"note": "left the village, confirmed"})
    assert r.json()["issue"]["status"] == "approved"
    assert db.get(AuditEntry, r.json()["audit_id"]).action == "issue.confirm"
    assert student(db, i["entity_ref"]).enrolment_status == "dropout"


def test_acted_issue_is_final(client, seeded_db):
    login(client, "principal", "SYN-0002")
    i = next(x for x in issues_by(client, status="open") if x["suggested_value"])
    client.post(f"/api/issues/{i['id']}/approve", json={})
    for action in ("approve", "hold"):
        assert client.post(f"/api/issues/{i['id']}/{action}", json={}).status_code == 409


def test_resolved_when_problem_disappears(client, seeded_db, db):
    """Fixing the root cause through one issue resolves related open issues on re-validation."""
    login(client, "principal", "SYN-0002")
    i = next(x for x in issues_by(client, rule_id="STU-004") if "update pending" in x["detail"])
    client.post(f"/api/issues/{i['id']}/edit", json={"field": "aadhaar_status", "value": "verified"})
    db.expire_all()
    assert db.get(Issue, i["id"]).status == "edited"
    client.post("/api/validate", json={})
    assert not [x for x in issues_by(client, rule_id="STU-004", status="open") if x["entity_ref"] == i["entity_ref"]]


def test_issue_detail_shows_record_and_rule(client, seeded_db):
    login(client, "principal", "SYN-0002")
    i = issues_by(client, rule_id="STU-005")[0]
    d = client.get(f"/api/issues/{i['id']}").json()
    assert d["rule"]["version"] == "1.0.0" and d["record"]["name"]
    assert "name" in d["editable_fields"]
    assert "fingerprint" not in d
    login(client, "admin")
    assert client.get(f"/api/issues/{i['id']}").json()["editable_fields"] == []


def test_every_action_keeps_chain_valid(client, seeded_db):
    login(client, "principal", "SYN-0002")
    for i in issues_by(client, status="open")[:5]:
        client.post(f"/api/issues/{i['id']}/hold", json={})
    login(client, "admin")
    assert client.get("/api/audit/verify").json()["ok"]


def test_notes_with_id_numbers_are_refused(client, seeded_db, db):
    """Notes are kept in the audit log forever, so an ID number must never get in there."""
    login(client, "principal", "SYN-0002")
    issue = next(i for i in issues_by(client, rule_id="STU-002") if "31/02/2015" in i["detail"])
    audit_before = last_audit(db).id
    for action, extra in (("approve", {}), ("hold", {}), ("edit", {"field": "dob", "value": "28/02/2015"})):
        r = client.post(f"/api/issues/{issue['id']}/{action}", json={"note": "checked 0123 4567 8901", **extra})
        assert r.status_code == 422 and "ID number" in r.json()["detail"], (action, r.text)
    assert last_audit(db).id == audit_before
    assert student(db, issue["entity_ref"]).dob == "31/02/2015"


def test_reject_suggestion_keeps_record_and_issue_open(client, seeded_db, db):
    login(client, "principal", "SYN-0002")
    issue = next(i for i in issues_by(client, rule_id="STU-005") if "Ananya" in i["detail"])
    r = client.post(f"/api/issues/{issue['id']}/reject-suggestion", json={"note": "register is wrong here"})
    assert r.status_code == 200, r.text
    assert r.json()["issue"]["status"] == "open" and r.json()["issue"]["suggested_value"] is None
    assert student(db, issue["entity_ref"]).name == "Ananya Kumar"  # untouched
    action = db.get(AuditEntry, r.json()["audit_id"])
    assert action.action == "issue.reject_suggestion" and '"rejected_value":"Ananya R. Kumar"' in action.payload
    # a re-run does not bring the rejected suggestion back
    client.post("/api/validate", json={})
    detail = client.get(f"/api/issues/{issue['id']}").json()
    assert detail["suggested_value"] is None and detail["status"] == "open"
    assert [h["action"] for h in detail["history"]] == ["reject_suggestion"]
    assert detail["history"][0]["rejected_value"] == "Ananya R. Kumar"
    # approving now confirms the record as it is
    r = client.post(f"/api/issues/{issue['id']}/approve", json={})
    assert db.get(AuditEntry, r.json()["audit_id"]).action == "issue.confirm"
    assert student(db, issue["entity_ref"]).name == "Ananya Kumar"


def test_reject_suggestion_needs_a_suggestion_and_a_staff_role(client, seeded_db):
    login(client, "principal", "SYN-0002")
    no_sugg = next(i for i in issues_by(client, status="open") if i["suggested_value"] is None)
    assert client.post(f"/api/issues/{no_sugg['id']}/reject-suggestion", json={}).status_code == 409
    sugg = next(i for i in issues_by(client, status="open") if i["suggested_value"])
    login(client, "mis_coordinator")
    assert client.post(f"/api/issues/{sugg['id']}/reject-suggestion", json={}).status_code == 403


def test_issue_detail_explains_the_rule(client, seeded_db):
    login(client, "principal", "SYN-0002")
    issue = next(i for i in issues_by(client, rule_id="STU-002") if "31/02/2015" in i["detail"])
    d = client.get(f"/api/issues/{issue['id']}").json()
    assert d["rule"]["check"] == "dob_valid" and d["rule"]["version"] == "1.0.0"
    assert any("admission register" in u for u in d["rule"]["uses"])
    assert d["rule"]["params"] and d["history"] == []
