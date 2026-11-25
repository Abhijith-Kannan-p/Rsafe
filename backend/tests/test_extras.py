"""Extra features: demo reset, test submit, trend, coverage, search, translations, metrics, report."""

import json
import re

from sqlmodel import func, select

from app.models import AuditEntry, Issue, Student
from app.services.rules import load_rules
from tests.conftest import login


def _ananya(client):
    return next(i for i in client.get("/api/issues", params={"rule_id": "STU-005"}).json() if "Ananya" in i["detail"])


# ------------------------------------------------------------------ demo reset

def test_demo_reset_rebuilds_data_and_logs_who_did_it(client, seeded_db, db):
    login(client, "principal", "SYN-0002")
    client.post(f"/api/issues/{_ananya(client)['id']}/approve", json={})
    r = client.post("/api/demo/reset")
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.exec(select(Student).where(Student.student_ref == "SYN-0002-S0029")).one().name == "Ananya Kumar"
    actions = [e.action for e in db.exec(select(AuditEntry).order_by(AuditEntry.id))]
    assert actions == ["data.load", "validation.run", "demo.reset"]
    last = db.exec(select(AuditEntry).order_by(AuditEntry.id.desc())).first()
    assert last.actor.startswith("Demo Principal")
    assert client.get("/api/audit/verify").status_code in (200, 403)  # principal is not admin; chain checked below
    login(client, "admin")
    assert client.get("/api/audit/verify").json()["ok"] is True


def test_demo_reset_needs_a_session(client, seeded_db):
    client.cookies.clear()
    assert client.post("/api/demo/reset").status_code == 401


# ------------------------------------------------------------------ metrics

def test_metrics_report_validation_timing_without_personal_data(client, seeded_db):
    login(client, "principal", "SYN-0002")
    client.post("/api/validate", json={})
    client.cookies.clear()
    r = client.get("/api/metrics")  # public, like /api/health
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok" and d["rules"]["loaded"] == 11 and d["data"]["students"] > 0
    run = d["validation"]["recent_runs"][0]
    assert run["records"] > 0 and run["total_ms"] >= run["rules_ms"] >= 0 and run["ms_per_1000_records"] > 0
    text = r.text
    assert "SYN-0002-S" not in text and "Demo Principal" not in text and not re.search(r"\d{12}", text)


# ------------------------------------------------------------------ test submit

def test_dry_run_changes_nothing_and_explains_each_row(client, seeded_db, db):
    login(client, "principal", "SYN-0002")
    before_issues = db.exec(select(func.count()).select_from(Issue)).one()
    before_students = [s.model_dump() for s in db.exec(select(Student).order_by(Student.id))]
    r = client.post("/api/submit/dry-run", json={})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["exported"] is False and d["records"] == 61 and len(d["rules"]) == 11
    assert d["ready"] is False and d["verdicts"]["likely_rejected"] > 0
    assert sum(d["verdicts"].values()) == d["records"]
    worst = d["rows"][0]
    assert worst["verdict"] in ("held_back", "likely_rejected") and worst["findings"]
    assert all(set(row["values"]) <= set(d["columns"]) for row in d["rows"])
    assert not re.search(r"\d{12}", r.text)  # masked Aadhaar only
    db.expire_all()
    assert db.exec(select(func.count()).select_from(Issue)).one() == before_issues
    assert [s.model_dump() for s in db.exec(select(Student).order_by(Student.id))] == before_students
    last = db.exec(select(AuditEntry).order_by(AuditEntry.id.desc())).first()
    assert last.action == "submit.dry_run" and '"exported":false' in last.payload


def test_dry_run_reflects_decisions(client, seeded_db):
    login(client, "principal", "SYN-0002")
    issue = _ananya(client)
    before = next(r for r in client.post("/api/submit/dry-run", json={}).json()["rows"]
                  if r["values"]["student_ref"] == issue["entity_ref"])
    assert before["verdict"] == "would_send_flagged"  # STU-005 is medium
    client.post(f"/api/issues/{issue['id']}/approve", json={})
    after = next(r for r in client.post("/api/submit/dry-run", json={}).json()["rows"]
                 if r["values"]["student_ref"] == issue["entity_ref"])
    assert after["verdict"] == "would_send" and after["values"]["name"] == "Ananya R. Kumar"


def test_dry_run_roles(client, seeded_db):
    login(client, "teacher")
    assert client.post("/api/submit/dry-run", json={}).status_code == 403
    login(client, "mis_coordinator")
    assert client.post("/api/submit/dry-run", json={}).status_code == 400  # must pick a school
    assert client.post("/api/submit/dry-run", json={"school_code": "SYN-0003"}).status_code == 200
    login(client, "principal", "SYN-0002")
    assert client.post("/api/submit/dry-run", json={"school_code": "SYN-0003"}).status_code == 404


# ------------------------------------------------------------------ readiness trend

def test_trend_steps_up_after_a_fix_and_names_the_cause(client, seeded_db):
    login(client, "principal", "SYN-0002")
    first = client.get("/api/trend").json()["points"]
    assert len(first) == 1 and first[0]["cause"]["action"] == "data.load"
    client.post(f"/api/issues/{_ananya(client)['id']}/approve", json={})
    pts = client.get("/api/trend").json()["points"]
    assert len(pts) == 2 and pts[1]["readiness"] > pts[0]["readiness"]
    assert pts[1]["cause"]["action"] == "issue.approve" and pts[1]["cause"]["rule_id"] == "STU-005"


def test_trend_scope(client, seeded_db):
    login(client, "principal", "SYN-0002")
    assert client.get("/api/trend", params={"school_code": "SYN-0001"}).status_code == 404
    login(client, "teacher")
    assert client.get("/api/trend").status_code == 403


# ------------------------------------------------------------------ coverage

def test_coverage_groups_rules_by_failure_reason(client, seeded_db):
    login(client, "mis_coordinator")
    d = client.get("/api/coverage").json()
    reasons = {x["reason"]: x for x in d["reasons"]}
    assert {r["id"] for r in reasons["Duplicate enrolment"]["rules"]} == {"STU-006", "STU-007"}
    assert sum(len(x["rules"]) for x in d["reasons"]) == 11
    assert sum(x["found"] for x in d["reasons"]) == 27  # every injected problem, nothing else
    login(client, "principal", "SYN-0002")
    assert sum(x["found"] for x in client.get("/api/coverage").json()["reasons"]) == 12


# ------------------------------------------------------------------ search

def test_search_is_scoped_and_never_matches_aadhaar(client, seeded_db, db):
    login(client, "principal", "SYN-0002")
    hits = client.get("/api/search", params={"q": "ananya"}).json()
    assert [h["student_ref"] for h in hits] == ["SYN-0002-S0029"] and hits[0]["issue_id"]
    assert client.get("/api/search", params={"q": "SYN-0001-S00"}).json() == []  # another school
    last4 = db.exec(select(Student).where(Student.student_ref == "SYN-0002-S0029")).one().aadhaar_last4
    assert all("aadhaar" not in json.dumps(h).lower() for h in client.get("/api/search", params={"q": last4}).json())
    login(client, "student_parent")
    assert client.get("/api/search", params={"q": "ananya"}).status_code == 403


# ------------------------------------------------------------------ translations

def test_translations_cover_every_rule_and_match_the_yaml():
    data = json.loads(open("rules/i18n.json", encoding="utf-8").read())
    assert data["languages"]["hi"]["status"] == "needs_review" and data["languages"]["ml"]["status"] == "needs_review"
    for rule in load_rules():
        t = data["rules"][rule.id]
        assert t["en"] == {"title": rule.title, "message": rule.message, "fix": rule.fix}, rule.id
        for lang, script in (("hi", "ऀ-ॿ"), ("ml", "ഀ-ൿ")):
            assert t[lang]["needs_review"] is True
            for k in ("title", "message", "fix"):
                assert re.search(f"[{script}]", t[lang][k]), (rule.id, lang, k)


def test_translations_endpoint(client, seeded_db):
    login(client, "student_parent")
    assert set(client.get("/api/rules/i18n").json()["rules"]) == {r.id for r in load_rules()}


# ------------------------------------------------------------------ report

def test_report_has_audit_summary(client, seeded_db):
    login(client, "principal", "SYN-0002")
    client.post(f"/api/issues/{_ananya(client)['id']}/approve", json={"note": "register"})
    html = client.get("/api/export/report").text
    assert "Audit summary" in html and "Head hash" in html
    assert re.search(r"Readiness went from <b>\d+%</b> at the first validation to <b>\d+%</b>", html)
    assert "Demo Principal (SYN-0002)" in html and "1 fixes approved" in html


# ------------------------------------------------------------------ recent decisions

def test_principal_sees_teachers_change_on_dashboard(client, seeded_db):
    login(client, "teacher", "SYN-0002")
    issue = _ananya(client)
    assert client.post(f"/api/issues/{issue['id']}/approve", json={"note": "matches register"}).status_code == 200
    login(client, "principal", "SYN-0002")
    d = client.get("/api/decisions").json()
    top = d["decisions"][0]
    assert d["by_teacher"] == 1
    assert top["role"] == "teacher" and top["action"] == "approve" and top["issue_id"] == issue["id"]
    assert top["name"] == "Ananya R. Kumar" and top["old"] == "Ananya Kumar" and top["new"] == "Ananya R. Kumar"
    assert top["field"] == "name" and top["note"] == "matches register"
    # the MIS coordinator sees it too; another school's principal does not
    login(client, "mis_coordinator")
    assert any(x["audit_id"] == top["audit_id"] for x in client.get("/api/decisions").json()["decisions"])
    assert client.get("/api/decisions", params={"school_code": "SYN-0001"}).json()["decisions"] == []
    login(client, "principal", "SYN-0001")
    assert client.get("/api/decisions").json() == {"decisions": [], "by_teacher": 0}
    assert client.get("/api/decisions", params={"school_code": "SYN-0002"}).status_code == 404


def test_decisions_roles_and_limit(client, seeded_db):
    for role in ("teacher", "admin", "student_parent"):
        login(client, role)
        assert client.get("/api/decisions").status_code == 403
    login(client, "principal", "SYN-0002")
    for i in [x for x in client.get("/api/issues").json() if x["status"] == "open"][:3]:
        client.post(f"/api/issues/{i['id']}/approve", json={})
    d = client.get("/api/decisions", params={"limit": 2}).json()["decisions"]
    assert len(d) == 2 and d[0]["audit_id"] > d[1]["audit_id"]
