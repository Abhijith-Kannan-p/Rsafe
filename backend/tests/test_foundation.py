"""Phase 1: API boots, schema has no raw-Aadhaar column, seed is reproducible and synthetic."""

import hashlib
import json
from collections import Counter

from sqlmodel import SQLModel

import seed
from app import models  # noqa: F401
from app.db import init_db, make_engine


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["synthetic"] is True


def test_meta_lists_all_roles(client):
    roles = {r["id"] for r in client.get("/api/meta").json()["roles"]}
    assert roles == {"principal", "teacher", "mis_coordinator", "admin", "student_parent"}


def test_schema_creates_and_has_no_raw_aadhaar_column():
    engine = make_engine("sqlite://")
    init_db(engine)
    student_cols = set(SQLModel.metadata.tables["student"].columns.keys())
    assert {"aadhaar_token", "aadhaar_last4"} <= student_cols
    for table in SQLModel.metadata.tables.values():
        assert "aadhaar" not in table.columns.keys(), f"raw aadhaar column in {table.name}"


def _fingerprint(ds: seed.Dataset) -> str:
    blob = json.dumps([ds.students, ds.admission_register, ds.teacher_assignments,
                       ds.maintenance_log, ds.attendance, ds.fees], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def test_seed_is_reproducible():
    assert _fingerprint(seed.generate(42)) == _fingerprint(seed.generate(42))
    assert _fingerprint(seed.generate(42)) != _fingerprint(seed.generate(43))


def test_seed_shape_and_injections():
    ds = seed.generate()
    counts = Counter(s["school_code"] for s in ds.students)
    assert set(counts) == {"SYN-0001", "SYN-0002", "SYN-0003"}
    assert all(60 <= n <= 62 for n in counts.values())

    by_rule = Counter(i.rule for i in ds.injected)
    assert by_rule["STU-008"] == 3          # three held dropout cases
    assert by_rule["STU-007"] == 4          # two students, each seen in two schools
    assert by_rule["FAC-001"] == 1
    assert by_rule["SYS-001"] == 1
    assert by_rule["TCH-001"] == 1
    for rule in ["STU-001", "STU-002", "STU-003", "STU-004", "STU-005", "STU-006"]:
        assert by_rule[rule] >= 1, rule

    messy = {i.ref for i in ds.injected if i.entity == "student"}
    assert 0.10 <= len(messy) / len(ds.students) <= 0.16

    register = {(r["school_code"], r["admission_no"]): r["name"] for r in ds.admission_register}
    ananya = next(s for s in ds.students if s["name"] == "Ananya Kumar")
    assert register[(ananya["school_code"], ananya["admission_no"])] == "Ananya R. Kumar"


def test_cross_school_duplicates_share_id_not_name():
    ds = seed.generate()
    ids = Counter(s["aadhaar"] for s in ds.students if s["aadhaar"])
    shared = [a for a, n in ids.items() if n > 1]
    # 2 cross-school pairs + 1 within-school duplicate pair
    assert len(shared) == 3
    cross = 0
    for a in shared:
        rows = [s for s in ds.students if s["aadhaar"] == a]
        if len({r["school_code"] for r in rows}) == 2:
            cross += 1
            assert rows[0]["name"] != rows[1]["name"]  # match must rely on the ID, not the name
    assert cross == 2


def test_synthetic_ids_can_never_be_real_aadhaar():
    # Real Aadhaar numbers never start with 0 or 1; every synthetic one starts with 0.
    for s in seed.generate().students:
        if s["aadhaar"]:
            assert len(s["aadhaar"]) == 12 and s["aadhaar"].startswith("0")
