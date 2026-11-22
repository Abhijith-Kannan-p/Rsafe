"""CSV upload: map columns, check rows, then (only when a person confirms) replace a school's
student records and re-validate.

Privacy: the uploaded text holds raw synthetic IDs. They are read here, tokenised by
ingest.normalise_student, and never echoed: every value sent back in a preview goes through
`_mask`, which hides anything shaped like a 12-digit ID.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, delete, select

from .. import models as m
from ..auth import Identity
from . import audit
from .context import parse_date
from .ingest import normalise_student
from .tokens import Tokenizer
from .validation import run_validation

MAX_BYTES = 2_000_000
MAX_ROWS = 10_000
PREVIEW_ROWS = 25


@dataclass(frozen=True)
class FieldSpec:
    field: str
    label: str
    required: bool
    synonyms: tuple[str, ...]


FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("student_ref", "Student ID", True, ("student id", "student ref", "ref", "student no")),
    FieldSpec("school_code", "School code", False, ("school code", "school", "udise code", "school id")),
    FieldSpec("admission_no", "Admission number", False, ("admission no", "admission number", "adm no")),
    FieldSpec("name", "Student name", True, ("student name", "name", "full name")),
    FieldSpec("dob", "Date of birth", True, ("date of birth", "dob", "birth date", "birthdate")),
    FieldSpec("gender", "Gender", True, ("gender", "sex")),
    FieldSpec("class_grade", "Class", True, ("class", "grade", "standard", "class grade", "std")),
    FieldSpec("section", "Section", True, ("section", "division", "div")),
    FieldSpec("guardian_name", "Guardian name", False, ("guardian name", "guardian", "parent name")),
    FieldSpec("aadhaar", "Aadhaar number", False, ("aadhaar", "aadhaar no", "aadhaar number", "uid", "aadhar no")),
    FieldSpec("aadhaar_status", "Aadhaar status", False, ("aadhaar status", "aadhar status")),
    FieldSpec("enrolment_status", "Enrolment status", False, ("enrolment status", "enrollment status", "status")),
    FieldSpec("previous_school_code", "Previous school", False, ("previous school", "previous school code", "prev school")),
    FieldSpec("transfer_status", "Transfer status", False, ("transfer status", "transfer")),
)
FIELD_NAMES = {f.field for f in FIELDS}

ID_SHAPED = re.compile(r"\d{4}\D?\d{4}\D?\d{4}")


def _norm_header(h: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", h.lower()).split())


def suggest_mapping(headers: list[str]) -> dict[str, str]:
    """header -> field ('' when nothing fits). Exact field names win, then synonyms."""
    used: set[str] = set()
    out: dict[str, str] = {}
    for h in headers:
        n = _norm_header(h)
        hit = next((f.field for f in FIELDS if f.field not in used
                    and (n == _norm_header(f.field) or n in f.synonyms)), "")
        if hit:
            used.add(hit)
        out[h] = hit
    return out


def _mask(value: str) -> str:
    return ID_SHAPED.sub(lambda mt: "XXXX XXXX " + re.sub(r"\D", "", mt.group())[-4:], value)


def _mask_aadhaar(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""
    return f"XXXX XXXX {digits[-4:]}" if len(digits) >= 4 else "(too short)"


def parse_csv(text: str) -> tuple[list[str], list[list[str]]]:
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 2 MB.")
    text = text.lstrip("﻿")
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise HTTPException(422, "The file is empty.")
    if len(rows) - 1 > MAX_ROWS:
        raise HTTPException(413, f"File has more than {MAX_ROWS} rows.")
    headers = [h.strip() for h in rows[0]]
    if len(set(headers)) != len(headers):
        raise HTTPException(422, "Two columns have the same heading. Rename one and upload again.")
    return headers, rows[1:]


@dataclass
class Checked:
    headers: list[str]
    mapping: dict[str, str]
    records: list[dict[str, str]]  # by field, raw (internal only, never returned)
    problems: list[dict[str, Any]]
    file_errors: list[str]

    @property
    def can_import(self) -> bool:
        return not self.file_errors and not any(p["level"] == "error" for p in self.problems)


def check(text: str, school_code: str, mapping: dict[str, str] | None = None) -> Checked:
    headers, body = parse_csv(text)
    mapping = {h: (mapping or {}).get(h, "") for h in headers} if mapping is not None else suggest_mapping(headers)
    file_errors: list[str] = []
    bad = [f for f in mapping.values() if f and f not in FIELD_NAMES]
    if bad:
        raise HTTPException(422, f"Unknown field(s): {', '.join(sorted(set(bad)))}.")
    twice = [f for f, n in Counter(v for v in mapping.values() if v).items() if n > 1]
    for f in twice:
        file_errors.append(f"More than one column is mapped to '{f}'.")
    mapped = set(mapping.values())
    for f in FIELDS:
        if f.required and f.field not in mapped:
            file_errors.append(f"No column is mapped to {f.label}.")

    records: list[dict[str, str]] = []
    problems: list[dict[str, Any]] = []
    seen_refs: dict[str, int] = {}

    def flag(row: int, field: str, level: str, message: str) -> None:
        problems.append({"row": row, "field": field, "level": level, "message": message})

    for n, cells in enumerate(body, start=2):  # row 1 is the heading
        rec = {f: "" for f in FIELD_NAMES}
        for h, cell in zip(headers, cells):
            if mapping.get(h):
                rec[mapping[h]] = cell.strip()
        if len(cells) > len(headers):
            flag(n, "", "warning", "Row has more cells than headings; the extra cells were ignored.")
        sc = rec["school_code"]
        if not sc:
            rec["school_code"] = school_code
        elif sc != school_code:
            flag(n, "school_code", "error", f"Row belongs to school {_mask(sc)}, not {school_code}.")
        ref = rec["student_ref"]
        if not ref:
            flag(n, "student_ref", "error", "Student ID is empty.")
        elif ref in seen_refs:
            flag(n, "student_ref", "error", f"Student ID {_mask(ref)} is also on row {seen_refs[ref]}.")
        else:
            seen_refs[ref] = n
        if "name" in mapped and not rec["name"]:
            flag(n, "name", "warning", "Name is empty.")
        if "dob" in mapped and not parse_date(rec["dob"]):
            what = f"'{_mask(rec['dob'])}' is not a real date in DD/MM/YYYY" if rec["dob"] else "Date of birth is empty"
            flag(n, "dob", "warning", f"{what}.")
        if "class_grade" in mapped and not (rec["class_grade"].isdigit() and 1 <= int(rec["class_grade"]) <= 12):
            flag(n, "class_grade", "warning", f"Class '{_mask(rec['class_grade'])}' is not a number from 1 to 12.")
        if "aadhaar" in mapped:
            digits = re.sub(r"\D", "", rec["aadhaar"])
            if digits and len(digits) != 12:
                flag(n, "aadhaar", "warning", f"Aadhaar has {len(digits)} digits, not 12.")
        records.append(rec)
    return Checked(headers, mapping, records, problems, file_errors)


def preview(text: str, school_code: str, mapping: dict[str, str] | None = None) -> dict[str, Any]:
    c = check(text, school_code, mapping)
    by_row: dict[int, list[dict]] = {}
    for p in c.problems:
        by_row.setdefault(p["row"], []).append(p)
    rows = []
    for i, rec in enumerate(c.records[:PREVIEW_ROWS]):
        n = i + 2
        values = {k: (_mask_aadhaar(v) if k == "aadhaar" else _mask(v)) for k, v in rec.items()}
        rows.append({"row": n, "values": values, "problems": by_row.get(n, [])})
    levels = Counter(p["level"] for p in c.problems)
    return {
        "headers": c.headers,
        "fields": [{"field": f.field, "label": f.label, "required": f.required} for f in FIELDS],
        "mapping": c.mapping,
        "rows_total": len(c.records),
        "rows": rows,
        "problems": c.problems[:500],
        "file_errors": c.file_errors,
        "counts": {"errors": levels.get("error", 0) + len(c.file_errors), "warnings": levels.get("warning", 0),
                   "rows_with_problems": len(by_row)},
        "can_import": c.can_import,
    }


def commit(s: Session, rules, who: Identity, text: str, mapping: dict[str, str] | None,
           filename: str, tokenizer: Tokenizer | None = None) -> dict[str, Any]:
    code = who.school_code or ""
    school = s.get(m.School, code)
    if school is None or school.status != "open":
        raise HTTPException(404, "School not found.")
    c = check(text, code, mapping)
    if not c.can_import:
        n = len(c.file_errors) + sum(p["level"] == "error" for p in c.problems)
        raise HTTPException(422, f"The file has {n} blocking error{'s' if n != 1 else ''}. Fix them and try again.")

    tokenizer = tokenizer or Tokenizer()
    students = []
    cols = set(m.Student.model_fields) - {"id"}
    for rec in c.records:
        norm = normalise_student(rec, tokenizer, school.cluster)
        students.append(m.Student(**{k: v for k, v in norm.items() if k in cols}))

    replaced = len(list(s.exec(select(m.Student.id).where(m.Student.school_code == code))))
    s.exec(delete(m.Student).where(m.Student.school_code == code))  # type: ignore[call-overload]
    s.add_all(students)
    audit.append(s, who.actor, who.role.value, "data.import", f"school:{code}", {
        "school_code": code, "filename": _mask(filename)[:120], "rows": len(students), "replaced": replaced,
        "warnings": sum(p["level"] == "warning" for p in c.problems),
        "mapped_fields": sorted(v for v in c.mapping.values() if v),
    }, commit=False)
    s.commit()
    result = run_validation(s, rules, [code], who.actor, who.role.value)
    return {"imported": len(students), "replaced": replaced, "summary": result["schools"][0],
            "changes": result["changes"][code]}
