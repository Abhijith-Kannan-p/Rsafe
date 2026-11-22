import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

# Tests never touch the developer's database or keys.
os.environ.setdefault("RSAFE_DATABASE_URL", "sqlite://")
os.environ.setdefault("RSAFE_KEYS_DIR", tempfile.mkdtemp(prefix="rsafe-test-keys-"))


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def seed_dir(tmp_path_factory):
    import seed

    out = tmp_path_factory.mktemp("seed-data")
    seed.write_dataset(seed.generate(), out, seed.DEFAULT_SEED)
    return out


@pytest.fixture
def seeded_db(seed_dir):
    """Fresh copy of the demo database (in-memory app engine), validated once by the system user."""
    from app.db import engine
    from app.services.loader import seed_and_validate

    return seed_and_validate(seed_dir, engine)


@pytest.fixture
def db(seeded_db):
    from sqlmodel import Session

    from app.db import engine

    with Session(engine) as s:
        yield s


def login(client, role, school_code=None):
    body = {"role": role} | ({"school_code": school_code} if school_code else {})
    r = client.post("/api/session", json=body)
    assert r.status_code == 200, r.text
    return r.json()
