"""Privacy: no 12-digit number (and no raw synthetic ID) anywhere in the database or the API.

The seeded CSVs are the "school side" input and DO contain synthetic IDs; the test first
confirms that, so it can't pass vacuously. Everything after ingest must be clean.
"""

import csv
import re

import pytest
from sqlalchemy import text
from sqlmodel import SQLModel

import seed
from app.db import engine as app_engine
from app.db import make_engine
from app.services.loader import load_into_db, seed_and_validate

# A 12-digit run not glued to other letters/digits, or the spaced/dashed 4-4-4 form.
TWELVE = re.compile(r"(?<![0-9A-Za-z])\d{12}(?![0-9A-Za-z])|\b\d{4}[ -]\d{4}[ -]\d{4}\b")


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    out = tmp_path_factory.mktemp("privacy")
    seed.write_dataset(seed.generate(), out, seed.DEFAULT_SEED)
    with (out / "students.csv").open(encoding="utf-8") as fh:
        raw_ids = {r["aadhaar"] for r in csv.DictReader(fh) if r["aadhaar"]}
    return out, raw_ids


def dump_all(engine) -> str:
    parts = []
    with engine.connect() as conn:
        for table in SQLModel.metadata.sorted_tables:
            for row in conn.execute(text(f'SELECT * FROM "{table.name}"')):
                parts.append(" | ".join(str(v) for v in row))
    return "\n".join(parts)


def test_input_really_contains_ids(seeded):
    out, raw_ids = seeded
    assert len(raw_ids) > 150
    assert TWELVE.search((out / "students.csv").read_text())


def test_database_has_no_raw_ids(seeded, tmp_path):
    out, raw_ids = seeded
    db_file = tmp_path / "privacy.db"
    engine = make_engine(f"sqlite:///{db_file}")
    counts = load_into_db(out, engine)
    assert counts["students"] > 150

    dump = dump_all(engine)
    assert dump.count("\n") > 1000  # sanity: we really dumped the tables
    assert not TWELVE.search(dump), TWELVE.search(dump)
    assert not any(i in dump for i in raw_ids)

    engine.dispose()
    blob = db_file.read_bytes().decode("latin-1")  # whole file, including any free pages
    assert not any(i in blob for i in raw_ids)


def test_api_responses_have_no_raw_ids(seeded, client):
    """Signed in as every role, call every parameter-free GET route plus every issue and rule detail."""
    out, raw_ids = seeded
    seed_and_validate(out, app_engine)  # the app's (in-memory) database

    # Enumerate from the OpenAPI schema: app.routes does not list routes added via include_router.
    paths = client.app.openapi()["paths"]
    get_paths = [p for p, ops in paths.items() if "get" in ops and p.startswith("/api") and "{" not in p]
    assert {"/api/issues", "/api/audit", "/api/summary", "/api/rules", "/api/session"} <= set(get_paths)
    bodies = []
    for role in ["principal", "teacher", "mis_coordinator", "admin", "student_parent"]:
        assert client.post("/api/session", json={"role": role}).status_code == 200
        for path in get_paths:
            r = client.get(path)
            assert r.status_code < 500, path
            bodies.append(r.text)
        for issue in client.get("/api/issues").json():
            bodies.append(client.get(f"/api/issues/{issue['id']}").text)
        for rule in client.get("/api/rules").json():
            bodies.append(client.get(f"/api/rules/{rule['id']}").text)

    blob = "\n".join(bodies)
    assert len(bodies) > 100 and '"rule_id"' in blob and '"short_hash"' in blob
    assert not TWELVE.search(blob)
    assert not any(i in blob for i in raw_ids)
