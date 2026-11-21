"""Keyed tokens and the key store."""

import re

import pytest

from app.config import REPO_DIR
from app.services.ingest import normalise_student
from app.services.keys import KeyStore
from app.services.tokens import Tokenizer, normalise_aadhaar, short

ID = "012345678901"  # synthetic: real Aadhaar numbers never start with 0


@pytest.fixture
def tk(tmp_path):
    return Tokenizer(KeyStore(tmp_path))


@pytest.mark.parametrize("raw", ["012345678901", "0123 4567 8901", "0123-4567-8901", " 012345678901 "])
def test_normalise_accepts_common_formats(raw):
    assert normalise_aadhaar(raw) == ID


@pytest.mark.parametrize("raw", ["", None, "12345", "0123456789012", "abc"])
def test_normalise_rejects_wrong_length(raw):
    assert normalise_aadhaar(raw) is None


def test_tokens_are_deterministic_and_base32(tk):
    t1, t2 = tk.school_token("SYN-0001", ID), tk.school_token("SYN-0001", "0123 4567 8901")
    assert t1 == t2
    assert re.fullmatch(r"[a-z2-7]{52}", t1)
    assert not re.search(r"\d{3}", t1)  # base32 digits are 2-7 and never run long enough to look like an ID
    assert short(t1) == t1[:6]


def test_school_tokens_differ_between_schools(tk):
    assert tk.school_token("SYN-0001", ID) != tk.school_token("SYN-0002", ID)


def test_match_tokens_agree_across_schools_in_one_cluster(tk):
    a = normalise_student({"school_code": "SYN-0001", "aadhaar": ID}, tk, "CL-01")
    b = normalise_student({"school_code": "SYN-0002", "aadhaar": ID}, tk, "CL-01")
    assert a["match_token"] == b["match_token"]
    assert a["aadhaar_token"] != b["aadhaar_token"]


def test_match_tokens_differ_between_clusters(tk):
    assert tk.match_token("CL-01", ID) != tk.match_token("CL-02", ID)


def test_school_and_match_token_differ(tk):
    assert tk.school_token("CL-01", ID) != tk.match_token("CL-01", ID)


def test_different_keys_different_tokens(tmp_path):
    a = Tokenizer(KeyStore(tmp_path / "a")).school_token("SYN-0001", ID)
    b = Tokenizer(KeyStore(tmp_path / "b")).school_token("SYN-0001", ID)
    assert a != b


def test_keys_persist_across_instances(tmp_path):
    t1 = Tokenizer(KeyStore(tmp_path)).match_token("CL-01", ID)
    t2 = Tokenizer(KeyStore(tmp_path)).match_token("CL-01", ID)
    assert t1 == t2
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files == ["cluster_master.key"]  # cluster keys are derived, not stored
    assert len(bytes.fromhex((tmp_path / "cluster_master.key").read_text())) == 32


def test_key_names_are_sanitised(tmp_path):
    with pytest.raises(ValueError):
        KeyStore(tmp_path).school_key("../escape")


def test_ingest_drops_raw_id_and_keeps_last4(tk):
    rec = normalise_student({"school_code": "SYN-0001", "aadhaar": ID, "name": "X"}, tk, "CL-01")
    assert "aadhaar" not in rec
    assert rec["aadhaar_last4"] == "8901"
    assert ID not in str(rec)


def test_ingest_flags_wrong_length(tk):
    rec = normalise_student({"school_code": "SYN-0001", "aadhaar": "12345678"}, tk, "CL-01")
    assert rec["aadhaar_problem"] == "invalid_length"
    assert rec["aadhaar_token"] is None and rec["match_token"] is None
    assert rec["aadhaar_last4"] == "5678"


def test_keys_folder_is_git_ignored():
    assert ".keys/" in (REPO_DIR / ".gitignore").read_text().splitlines()
