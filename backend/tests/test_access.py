"""Role-based access, enforced by the backend."""

import pytest

from tests.conftest import login

ALL_ROLES = ["principal", "teacher", "mis_coordinator", "admin", "student_parent"]


def test_no_session_is_401(client, seeded_db):
    for path in ["/api/issues", "/api/summary", "/api/audit", "/api/audit/verify", "/api/rules", "/api/session"]:
        assert client.get(path).status_code == 401, path
    assert client.post("/api/validate", json={}).status_code == 401


def test_forged_cookie_rejected(client, seeded_db):
    client.cookies.set("rsafe_session", "eyJyb2xlIjoiYWRtaW4ifQ.forged.sig")
    assert client.get("/api/issues").status_code == 401


def test_unknown_role_rejected(client, seeded_db):
    assert client.post("/api/session", json={"role": "superuser"}).status_code == 422


def test_closed_school_rejected(client, seeded_db):
    assert client.post("/api/session", json={"role": "principal", "school_code": "SYN-0004"}).status_code == 400


# role -> (audit, validate, approve/edit, hold)
MATRIX = {
    "principal": (403, 200, True, True),
    "teacher": (403, 403, True, False),
    "mis_coordinator": (403, 200, False, False),
    "admin": (200, 200, False, False),
    "student_parent": (403, 403, False, False),
}


@pytest.mark.parametrize("role", ALL_ROLES)
def test_role_matrix(client, seeded_db, role):
    audit_code, validate_code, can_fix, can_hold = MATRIX[role]
    login(client, role)
    assert client.get("/api/audit").status_code == audit_code
    assert client.get("/api/audit/verify").status_code == audit_code
    assert client.post("/api/audit/tamper", json={}).status_code == (200 if role == "admin" else 403)
    assert client.post("/api/validate", json={}).status_code == validate_code

    issues = [i for i in client.get("/api/issues").json() if i["status"] == "open"]
    assert issues, f"{role} should see at least one open issue"
    target = issues[0]
    r = client.post(f"/api/issues/{target['id']}/approve", json={})
    assert (r.status_code == 200) == can_fix, r.text
    if not can_fix:
        assert r.status_code == 403
    open_left = [i for i in client.get("/api/issues").json() if i["status"] == "open"]
    if open_left:
        r = client.post(f"/api/issues/{open_left[0]['id']}/hold", json={})
        assert (r.status_code == 200) == can_hold
        if not can_hold:
            assert r.status_code == 403


def test_principal_sees_only_own_school(client, seeded_db):
    login(client, "principal", "SYN-0001")
    assert {i["school_code"] for i in client.get("/api/issues").json()} == {"SYN-0001"}
    assert [x["school_code"] for x in client.get("/api/summary").json()["schools"]] == ["SYN-0001"]


def test_other_schools_issue_is_404_not_403(client, seeded_db):
    login(client, "principal", "SYN-0002")
    theirs = client.get("/api/issues").json()[0]["id"]
    login(client, "principal", "SYN-0001")
    assert client.get(f"/api/issues/{theirs}").status_code == 404
    assert client.post(f"/api/issues/{theirs}/approve", json={}).status_code == 404
    assert client.post("/api/validate", json={"school_code": "SYN-0002"}).status_code == 404


def test_mis_sees_whole_cluster(client, seeded_db):
    login(client, "mis_coordinator")
    assert {i["school_code"] for i in client.get("/api/issues").json()} == {"SYN-0001", "SYN-0002", "SYN-0003"}


def test_teacher_sees_only_own_classes(client, seeded_db, db):
    from sqlmodel import select

    from app.models import Student, TeacherAssignment

    me = login(client, "teacher")
    classes = {(a.class_grade, a.section) for a in db.exec(
        select(TeacherAssignment).where(TeacherAssignment.teacher_ref == me["teacher_ref"]))}
    mine = {s.student_ref for s in db.exec(select(Student).where(Student.school_code == me["school_code"]))
            if (s.class_grade, s.section) in classes}
    issues = client.get("/api/issues").json()
    assert issues
    for i in issues:
        assert (i["entity"] == "student" and i["entity_ref"] in mine) or \
               (i["entity"] == "teacher" and i["entity_ref"] == me["teacher_ref"])
    login(client, "principal", me["school_code"])
    assert len(client.get("/api/issues").json()) > len(issues)


def test_teacher_cannot_release_held(client, seeded_db, db):
    """Put a held issue inside the teacher's own classes, then try to release it."""
    from sqlmodel import select

    from app.models import Issue, Student, TeacherAssignment

    me = login(client, "teacher", "SYN-0001")
    held = db.exec(select(Issue).where(Issue.status == "held", Issue.school_code == "SYN-0001")).first()
    st = db.exec(select(Student).where(Student.student_ref == held.entity_ref)).one()
    db.add(TeacherAssignment(teacher_ref=me["teacher_ref"], school_code="SYN-0001",
                             class_grade=st.class_grade, section=st.section, subject="Mathematics"))
    db.commit()
    assert client.get(f"/api/issues/{held.id}").status_code == 200  # visible to the teacher now
    for action, body in [("approve", {}), ("edit", {"field": "enrolment_status", "value": "active"})]:
        r = client.post(f"/api/issues/{held.id}/{action}", json=body)
        assert r.status_code == 403 and "principal" in r.json()["detail"]


def test_parent_sees_only_own_child(client, seeded_db):
    me = login(client, "student_parent")
    issues = client.get("/api/issues").json()
    assert issues and {i["entity_ref"] for i in issues} == {me["student_ref"]}


def test_summary_is_scoped_to_what_the_role_sees(client, seeded_db):
    login(client, "principal", "SYN-0002")
    school = client.get("/api/summary").json()["schools"][0]
    login(client, "student_parent")
    mine = client.get("/api/summary").json()["schools"][0]
    assert mine["students"] == 1 and mine["active"] == len(client.get("/api/issues").json())
    login(client, "teacher", "SYN-0002")
    t = client.get("/api/summary").json()["schools"][0]
    assert 0 < t["students"] < school["students"]
    assert t["active"] == len([i for i in client.get("/api/issues").json()
                               if i["entity"] == "student" and i["status"] in ("open", "held")])
