"""Turns raw school CSV rows into stored records.

This is the privacy boundary. The raw Aadhaar value is read here, turned into two keyed
tokens and the last four digits, and then dropped. Nothing downstream ever sees it.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .context import Context
from .tokens import Tokenizer, normalise_aadhaar

RAW_ID_FIELDS = ("aadhaar", "aadhaar_number", "uid")


def _int_or_none(v: Any) -> int | None:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def normalise_student(row: dict[str, Any], tokenizer: Tokenizer | None = None, cluster: str = "") -> dict[str, Any]:
    raw = next((row.get(f) for f in RAW_ID_FIELDS if row.get(f)), "")
    rec = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k not in RAW_ID_FIELDS}
    digits = "".join(c for c in str(raw) if c.isdigit())
    valid = normalise_aadhaar(digits)
    rec["aadhaar_last4"] = digits[-4:] if len(digits) >= 4 else None
    rec["aadhaar_problem"] = "invalid_length" if digits and not valid else None
    rec["aadhaar_token"] = tokenizer.school_token(rec["school_code"], valid) if tokenizer and valid else None
    rec["match_token"] = tokenizer.match_token(cluster, valid) if tokenizer and valid and cluster else None
    rec["class_grade"] = _int_or_none(row.get("class_grade"))
    return rec


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def load_dataset(
    data_dir: Path, tokenizer: Tokenizer | None = None, **ctx_kwargs: Any
) -> tuple[dict[str, list[dict]], Context]:
    """Load the CSV set written by seed.py into (records by entity, context)."""
    tokenizer = tokenizer or Tokenizer()
    schools = read_csv(data_dir / "schools.csv")
    cluster_of = {s["code"]: s["cluster"] for s in schools}
    students = [
        normalise_student(r, tokenizer, cluster_of.get(r.get("school_code", ""), ""))
        for r in read_csv(data_dir / "students.csv")
    ]
    ctx = Context.build(
        prior_year=read_csv(data_dir / "prior_year.csv"),
        admission_register=read_csv(data_dir / "admission_register.csv"),
        attendance=read_csv(data_dir / "attendance.csv"),
        fees=read_csv(data_dir / "fees.csv"),
        assignments=read_csv(data_dir / "teacher_assignments.csv"),
        maintenance=read_csv(data_dir / "maintenance_log.csv"),
        schools=schools,
        **ctx_kwargs,
    )
    data = {
        "student": students,
        "teacher": read_csv(data_dir / "teachers.csv"),
        "facility": read_csv(data_dir / "facilities.csv"),
    }
    return data, ctx
