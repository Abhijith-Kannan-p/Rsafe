"""Local key store for tokenisation. Keys live in .keys/ (git-ignored) as hex text.

- school_<CODE>.key   random 32-byte key, one per school, never leaves that school
- cluster_master.key  random 32-byte secret held by the cluster (MIS) side; each cluster's
                      matching key is DERIVED from it, so keys can be rotated per cluster

In this prototype one machine plays both sides, so both kinds of key sit in one folder.
In a real deployment the school import tool would hold its school key plus its cluster's
derived matching key, and the platform would hold neither.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from pathlib import Path

from ..config import KEYS_DIR

MATCH_KEY_CONTEXT = b"rsafe/match-key/v1/"
_SAFE = re.compile(r"^[A-Za-z0-9_-]+$")


class KeyStore:
    def __init__(self, directory: Path = KEYS_DIR):
        self.dir = Path(directory)
        self._cache: dict[str, bytes] = {}

    def _load_or_create(self, name: str) -> bytes:
        if name in self._cache:
            return self._cache[name]
        if not _SAFE.match(name):
            raise ValueError(f"unsafe key name: {name!r}")
        path = self.dir / f"{name}.key"
        if path.exists():
            key = bytes.fromhex(path.read_text(encoding="utf-8").strip())
        else:
            self.dir.mkdir(parents=True, exist_ok=True)
            key = secrets.token_bytes(32)
            path.write_text(key.hex(), encoding="utf-8")
        if len(key) != 32:
            raise ValueError(f"{path} must hold a 32-byte hex key")
        self._cache[name] = key
        return key

    def school_key(self, school_code: str) -> bytes:
        return self._load_or_create(f"school_{school_code}")

    def cluster_match_key(self, cluster_id: str) -> bytes:
        master = self._load_or_create("cluster_master")
        return hmac.new(master, MATCH_KEY_CONTEXT + cluster_id.encode(), hashlib.sha256).digest()
