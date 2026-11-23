"""Cluster grid, teacher classes, and the parent's record with the mock confirmation."""

import pytest
from sqlmodel import select

from app.models import AuditEntry, Student
from app.routes.views import mock_code, school_status
from tests.conftest import login


class FakeIssue:
    def __init__(self, severity, status="open"):
        self.severity, self.status = severity, status


def test_school_status_rules():
    assert school_status([]) == "ready"
    assert school_status([FakeIssue("medium"), FakeIssue("low")]) == "fixing"
    assert school_status([FakeIssue("medium"), FakeIssue("high")]) == "blocked"
    assert school_status([FakeIssue("low", "held")]) == "blocked"


# ---------------------------------------------------------------- cluster

def test_cluster_lists_cluster_schools_with_reasons(client, seeded_db):
    login(client, "mis_coordinator")
    c = client.get("/api/cluster").json()
    assert c["cluster"] == "CL-01"
    tiles = {t["school_code"]: t for t in c["schools"]}
    assert set(tiles) == {"SYN-0001", "SYN-0002", "SYN-0003", "SYN-0004"}
    assert tiles["SYN-0004"]["status"] == "merged" and tiles["SYN-0004"]["merged_into"] == "SYN-0001"
    s1 = tiles["SYN-0001"]
    assert s1["status"] == "blocked"
    assert s1["reasons"][0]["blocking"]
    assert sum(r["count"] for r in s1["reasons"]) == s1["active"]
    assert any(r["rule_id"] == "STU-008" and r["held"] for r in s1["reasons"])


def test_cluster_status_moves_as_people_fix(client, seeded_db):
    """Clear every high and held issue at SYN-0003: it moves from blocked to fixing (or ready)."""
    login(client, "principal", "SYN-0003")
    for i in client.get("/api/issues").json():
        if i["status"] in ("open", "held") and (i["severity"] == "high" or i["status"] == "held"):
            client.post(f"/api/issues/{i['id']}/approve", json={"note": "checked"})
    login(client, "mis_coordinator")
    tile = next(t for t in client.get("/api/cluster").json()["schools"] if t["school_code"] == "SYN-0003")
    assert tile["status"] in ("fixing", "ready")
    assert tile["decided"] > 0


@pytest.mark.parametrize("role", ["principal", "teacher", "student_parent"])
def test_cluster_forbidden_for_school_roles(client, seeded_db, role):
    login(client, role)
    assert client.get("/api/cluster").status_code == 403


def test_admin_sees_cluster(client, seeded_db):
    login(client, "admin")
    assert len(client.get("/api/cluster").json()["schools"]) == 4


# ---------------------------------------------------------------- teacher

def test_teacher_classes(client, seeded_db, db):
    me = login(client, "teacher", "SYN-0002")
    data = client.get("/api/my/classes").json()
    assert data["teacher"]["teacher_ref"] == me["teacher_ref"]
    assert data["classes"]
    for c in data["classes"]:
        expected = {s.student_ref for s in db.exec(select(Student).where(
            Student.school_code == "SYN-0002", Student.class_grade == c["class_grade"], Student.section == c["section"]))}
        assert {s["student_ref"] for s in c["students"]} == expected
    visible = {i["id"] for i in client.get("/api/issues").json()}
    listed = {i["id"] for c in data["classes"] for s in c["students"] for i in s["issues"]} | \
             {i["id"] for i in data["own_issues"]}
    assert listed <= visible  # nothing outside what the issues API already allows


def test_my_classes_is_teacher_only(client, seeded_db):
    login(client, "principal")
    assert client.get("/api/my/classes").status_code == 403


# ---------------------------------------------------------------- parent

def test_parent_record(client, seeded_db):
    me = login(client, "student_parent")
    r = client.get("/api/my/record").json()
    assert r["student"]["student_ref"] == me["student_ref"]
    assert r["student"]["aadhaar"] is None or r["student"]["aadhaar"].startswith("XXXX XXXX ")
    assert r["issues"] and all(i["message"] for i in r["issues"])
    assert r["confirmation"] is None


def test_parent_confirm_flow_is_logged_and_changes_nothing(client, seeded_db, db):
    me = login(client, "student_parent")
    before = db.exec(select(Student).where(Student.student_ref == me["student_ref"])).one().model_dump()
    start = client.post("/api/my/confirm/start").json()
    assert start["mock"] and len(start["demo_code"]) == 6
    bad = "000000" if start["demo_code"] != "000000" else "111111"
    assert client.post("/api/my/confirm", json={"code": bad, "outcome": "correct"}).status_code == 422
    r = client.post("/api/my/confirm", json={"code": start["demo_code"], "outcome": "needs_change",
                                             "comment": "Name should have the initial R."})
    assert r.status_code == 200, r.text
    db.expire_all()
    e = db.get(AuditEntry, r.json()["audit_id"])
    assert e.action == "parent.report" and e.record_ref == f"student:{me['student_ref']}"
    assert db.exec(select(Student).where(Student.student_ref == me["student_ref"])).one().model_dump() == before
    assert client.get("/api/my/record").json()["confirmation"]["outcome"] == "needs_change"
    # Staff see it in the readiness report
    login(client, "principal", me["school_code"])
    assert "Name should have the initial R." in client.get("/api/export/report").text


def test_parent_comment_rejects_ids(client, seeded_db):
    me = login(client, "student_parent")
    r = client.post("/api/my/confirm", json={"code": mock_code(me["student_ref"]), "outcome": "needs_change",
                                             "comment": "aadhaar is 0123 4567 8901"})
    assert r.status_code == 422


def test_parent_endpoints_are_parent_only(client, seeded_db):
    login(client, "principal")
    assert client.get("/api/my/record").status_code == 403
    assert client.post("/api/my/confirm/start").status_code == 403


def test_schools_list(client, seeded_db):
    assert client.get("/api/schools").status_code == 401
    login(client, "teacher")
    assert [s["code"] for s in client.get("/api/schools").json()] == ["SYN-0001", "SYN-0002", "SYN-0003"]
