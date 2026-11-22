"""CSV upload: column mapping, row checks, no raw IDs echoed, and import only on confirm."""

import re

import pytest
from sqlmodel import select

import seed
from app.models import AuditEntry, Issue, Student
from tests.conftest import login

TWELVE = re.compile(r"(?<![0-9A-Za-z])\d{12}(?![0-9A-Za-z])|\b\d{4}[ -]\d{4}[ -]\d{4}\b")


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    out = tmp_path_factory.mktemp("samples")
    seed.write_samples(seed.generate(), out)
    return (out / "school_export_SYN-0002.csv").read_text(encoding="utf-8")


def n_rows(text):
    return len(text.strip().splitlines()) - 1


def test_sample_really_has_raw_ids(sample):
    assert TWELVE.search(sample)  # so the "nothing echoed" checks below can't pass vacuously


def test_preview_maps_spreadsheet_headings(client, seeded_db, sample):
    login(client, "principal", "SYN-0002")
    r = client.post("/api/upload/preview", json={"csv": sample})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["mapping"]["Student Name"] == "name"
    assert p["mapping"]["Date of Birth"] == "dob"
    assert p["mapping"]["Aadhaar No"] == "aadhaar"
    assert p["mapping"]["Remarks"] == ""
    assert p["rows_total"] == n_rows(sample) > 50 and p["can_import"] and not p["file_errors"]
    # The seeded problems show up as warnings before validation runs
    msgs = " ".join(x["message"] for x in p["problems"])
    assert "31/02/2015" in msgs and "not a real date" in msgs
    assert p["counts"]["warnings"] >= 2 and p["counts"]["errors"] == 0


def test_preview_never_echoes_raw_ids(client, seeded_db, sample):
    login(client, "principal", "SYN-0002")
    text = client.post("/api/upload/preview", json={"csv": sample}).text
    assert not TWELVE.search(text)
    assert "XXXX XXXX" in text


def test_preview_does_not_write(client, seeded_db, sample, db):
    before = db.exec(select(AuditEntry)).all()
    login(client, "principal", "SYN-0002")
    client.post("/api/upload/preview", json={"csv": sample})
    db.expire_all()
    assert len(db.exec(select(AuditEntry)).all()) == len(before)


def test_missing_required_mapping_blocks_import(client, seeded_db, sample):
    login(client, "principal", "SYN-0002")
    p = client.post("/api/upload/preview", json={"csv": sample}).json()
    mapping = p["mapping"] | {"Date of Birth": ""}
    p2 = client.post("/api/upload/preview", json={"csv": sample, "mapping": mapping}).json()
    assert not p2["can_import"] and any("Date of birth" in e for e in p2["file_errors"])
    r = client.post("/api/upload/commit", json={"csv": sample, "mapping": mapping})
    assert r.status_code == 422


def test_wrong_school_rows_are_errors(client, seeded_db, sample):
    login(client, "principal", "SYN-0001")  # uploading SYN-0002's file
    p = client.post("/api/upload/preview", json={"csv": sample}).json()
    assert not p["can_import"]
    assert p["counts"]["errors"] == n_rows(sample)
    assert client.post("/api/upload/commit", json={"csv": sample}).status_code == 422


def test_duplicate_ids_and_empty_file(client, seeded_db, sample):
    login(client, "principal", "SYN-0002")
    lines = sample.splitlines()
    dup = "\n".join([*lines, lines[1]])
    p = client.post("/api/upload/preview", json={"csv": dup}).json()
    assert any("also on row 2" in x["message"] for x in p["problems"])
    assert client.post("/api/upload/preview", json={"csv": "  \n"}).status_code == 422


def test_commit_replaces_school_and_revalidates(client, seeded_db, sample, db):
    login(client, "principal", "SYN-0002")
    before = {i.fingerprint for i in db.exec(select(Issue).where(Issue.school_code == "SYN-0002",
                                                                  Issue.status.in_(("open", "held"))))}
    r = client.post("/api/upload/commit", json={"csv": sample, "filename": "school_export_SYN-0002.csv"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == body["replaced"] == n_rows(sample)
    db.expire_all()
    after = {i.fingerprint for i in db.exec(select(Issue).where(Issue.school_code == "SYN-0002",
                                                                 Issue.status.in_(("open", "held"))))}
    assert after == before  # same data in, same problems out
    actions = [e.action for e in db.exec(select(AuditEntry).order_by(AuditEntry.id.desc())).all()[:2]]
    assert actions == ["validation.run", "data.import"]
    assert len(db.exec(select(Student).where(Student.school_code == "SYN-0002")).all()) == n_rows(sample)
    assert len(db.exec(select(Student)).all()) == seeded_db["counts"]["students"]  # other schools untouched


def test_reimport_reopens_a_reverted_fix(client, seeded_db, sample, db):
    """Approve a name fix, then upload the old file again: the fix is undone, so the issue reopens."""
    login(client, "principal", "SYN-0002")
    issue = next(i for i in client.get("/api/issues", params={"rule_id": "STU-005"}).json()
                 if "Ananya" in i["detail"])
    assert client.post(f"/api/issues/{issue['id']}/approve", json={}).json()["issue"]["status"] == "approved"
    client.post("/api/upload/commit", json={"csv": sample})
    assert client.get(f"/api/issues/{issue['id']}").json()["status"] == "open"


@pytest.mark.parametrize("role", ["teacher", "mis_coordinator", "admin", "student_parent"])
def test_only_principal_can_upload(client, seeded_db, sample, role):
    login(client, role)
    assert client.post("/api/upload/preview", json={"csv": sample}).status_code == 403
    assert client.post("/api/upload/commit", json={"csv": sample}).status_code == 403
