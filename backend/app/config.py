"""Central settings. Everything is local; there are no external services."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent

DATA_DIR = BACKEND_DIR / "data"
RULES_DIR = BACKEND_DIR / "rules"
# Per-school HMAC keys and the cluster master secret live here (git-ignored).
KEYS_DIR = Path(os.environ.get("RSAFE_KEYS_DIR", REPO_DIR / ".keys"))

# Academic year 2026-27. Ages are measured on 30 Sep of this year.
ACADEMIC_YEAR_START = int(os.environ.get("RSAFE_ACADEMIC_YEAR_START", "2026"))

# "Today" for date-relative rules (STU-008's 30-day window). Pinned to the synthetic data's
# reference date so the demo shows the same results on any day. Override with RSAFE_TODAY.
REFERENCE_DATE = date.fromisoformat(os.environ.get("RSAFE_TODAY", "2026-11-16"))

# Enables demo-only endpoints such as the audit "Tamper row" button.
DEMO_MODE = os.environ.get("RSAFE_DEMO_MODE", "1") == "1"

# Session cookie lifetime (seconds).
SESSION_MAX_AGE = 8 * 3600

DATABASE_URL =os.environ.get("RSAFE_DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'rsafe.db'}")

# Built frontend served by the API in a single-service deployment (see app/static.py).
STATIC_DIR = Path(os.environ.get("RSAFE_STATIC_DIR", REPO_DIR / "frontend" / "dist"))

# Mark the session cookie Secure (HTTPS only). On for deployments behind HTTPS; off for local http.
COOKIE_SECURE = os.environ.get("RSAFE_COOKIE_SECURE", "0") == "1"

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
