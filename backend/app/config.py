"""Central settings. Everything is local; there are no external services."""

from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent

DATA_DIR = BACKEND_DIR / "data"
RULES_DIR = BACKEND_DIR / "rules"
# Per-school HMAC keys and the cluster key live here (git-ignored). Used from Phase 3.
KEYS_DIR = Path(os.environ.get("RSAFE_KEYS_DIR", REPO_DIR / ".keys"))

DATABASE_URL = os.environ.get("RSAFE_DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'rsafe.db'}")

# Signs the demo-role session cookie. A fixed dev default is fine for a local prototype.
SESSION_SECRET = os.environ.get("RSAFE_SESSION_SECRET", "rsafe-local-dev-only-not-a-secret")

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

SYNTHETIC_NOTICE = (
    "Prototype on synthetic data. Rsafe does not verify Aadhaar and makes no calls "
    "to UIDAI or any government portal."
)
