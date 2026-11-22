"""Keyed tokens for Aadhaar numbers. The raw number is never stored.

    school token = HMAC_SHA256(school_key, normalised_aadhaar)         within-school duplicates
    match token  = HMAC_SHA256(cluster_match_key, normalised_aadhaar)  cross-school duplicates

Tokens are base32 (a-z, 2-7), 52 characters. Base32 rather than hex because a hex SHA-256
string contains a 12-digit run about 17% of the time. Base32 tokens use only the digits 2-7,
so they cannot contain a synthetic ID (those start with 0), and a 12-digit run is
astronomically unlikely and would still be glued to letters.

Limits (also in the README): a 12-digit ID space is small enough that anyone holding a key
can brute-force a token back to the number. Tokens are pseudonyms that protect IDs only
while keys stay secret; they are not anonymisation.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from .keys import KeyStore

DISPLAY_LEN = 6


def normalise_aadhaar(raw: object) -> str | None:
    """Digits only. Returns the 12-digit string, or None if it isn't exactly 12 digits."""
    digits = "".join(c for c in str(raw or "") if c.isdigit())
    return digits if len(digits) == 12 else None


def _token(key: bytes, value: str) -> str:
    digest = hmac.new(key, value.encode(), hashlib.sha256).digest()
    return base64.b32encode(digest).decode().rstrip("=").lower()


def short(token: str | None) -> str:
    return token[:DISPLAY_LEN] if token else ""


class Tokenizer:
    def __init__(self, keys: KeyStore | None = None):
        self.keys = keys or KeyStore()

    def school_token(self, school_code: str, raw: object) -> str | None:
        value = normalise_aadhaar(raw)
        return _token(self.keys.school_key(school_code), value) if value else None

    def match_token(self, cluster_id: str, raw: object) -> str | None:
        value = normalise_aadhaar(raw)
        return _token(self.keys.cluster_match_key(cluster_id), value) if value else None
