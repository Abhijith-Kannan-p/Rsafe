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
