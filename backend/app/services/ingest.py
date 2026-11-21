"""Turns raw school CSV rows into stored records.

This is the privacy boundary: the raw Aadhaar value is read here and dropped. Only the
last four digits leave this function (Phase 3 adds the keyed HMAC token at this point).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .context import Context

RAW_ID_FIELDS = ("aadhaar", "aadhaar_number", "uid")


def _int_or_none(v: Any) -> int | None:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def normalise_student(row: dict[str, Any]) -> dict[str, Any]:
    rec = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k not in RAW_ID_FIELDS}
    digits = "".join(c for c in str(row.get("aadhaar") or "") if c.isdigit())
    rec["aadhaar_last4"] = digits[-4:] if len(digits) >= 4 else None
    rec["class_grade"] = _int_or_none(row.get("class_grade"))
    return rec


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_dataset(data_dir: Path, **ctx_kwargs: Any) -> tuple[dict[str, list[dict]], Context]:
    """Load the CSV set written by seed.py into (records by entity, context)."""
    students = [normalise_student(r) for r in read_csv(data_dir / "students.csv")]
    ctx = Context.build(
        prior_year=read_csv(data_dir / "prior_year.csv"),
        admission_register=read_csv(data_dir / "admission_register.csv"),
        **ctx_kwargs,
    )
    return {"student": students}, ctx
