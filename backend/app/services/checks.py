"""Named check functions referenced by the YAML rules.

A record check has the signature  (record, ctx, params) -> Finding | list[Finding] | None.
A dataset check has the signature (records, ctx, params) -> list[tuple[record, Finding]].

Checks only flag and explain. They never modify a record. A `suggested_value` is a
proposal that a person must approve.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

from .context import Context


@dataclass
class Finding:
    detail: str  # one specific plain-language sentence about this record
    evidence: dict[str, Any] = field(default_factory=dict)
    confidence: str | None = None
    suggested_value: str | None = None
    field: str | None = None  # which record field the suggestion applies to


@dataclass(frozen=True)
class CheckDef:
    fn: Callable[..., Any]
    scope: Literal["record", "dataset"]


REGISTRY: dict[str, CheckDef] = {}


def check(name: str, scope: Literal["record", "dataset"] = "record"):
    def register(fn):
        if name in REGISTRY:
            raise ValueError(f"check '{name}' registered twice")
        REGISTRY[name] = CheckDef(fn, scope)
        return fn

    return register


# ---------------------------------------------------------------- helpers

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_dob(value: str) -> date | None:
    """Strict DD/MM/YYYY parse. Returns None if the text is not a real date in that format."""
    value = (value or "").strip()
    if not DATE_RE.match(value):
        return None
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError:
        return None


def age_on(dob: date, on: date) -> int:
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


GENDER_MAP = {
    "m": "M", "male": "M", "boy": "M",
    "f": "F", "female": "F", "girl": "F",
    "t": "T", "tg": "T", "transgender": "T",
}
GENDER_LABEL = {"M": "Male", "F": "Female", "T": "Transgender"}


def normalise_gender(value: Any) -> str | None:
    """Returns M/F/T, '' when blank, or None when the value is unrecognised."""
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return GENDER_MAP.get(text)


def mask_last4(last4: str | None) -> str:
    return f"XXXX XXXX {last4}" if last4 else "(none)"


# Letters (any script, incl. Indic vowel signs), space, dot, apostrophe, hyphen.
NAME_PUNCT = set(" .'-")


def _is_name_char(c: str) -> bool:
    return c in NAME_PUNCT or unicodedata.category(c)[0] in ("L", "M")


# ---------------------------------------------------------------- STU-001

@check("name_wellformed")
def name_wellformed(rec: dict, ctx: Context, params: dict) -> Finding | None:
    raw = rec.get("name") or ""
    name = raw.strip()
    if not name:
        return Finding("No name is recorded for this student.", {"name": raw}, field="name")

    digits = sorted({c for c in name if c.isdigit()})
    symbols = sorted({c for c in name if not c.isdigit() and not _is_name_char(c)})
    extra_space = raw != name or "  " in name

    problems: list[str] = []
    if digits:
        problems.append(f"contains the digit{'s' if len(digits) > 1 else ''} {', '.join(digits)}")
    if symbols:
        problems.append(f"contains the symbol{'s' if len(symbols) > 1 else ''} {' '.join(symbols)}")
    if extra_space:
        problems.append("has extra spaces")
    if not problems:
        return None

    suggestion = None
    if not digits:  # we can safely drop symbols and spaces, but cannot guess a letter hidden behind a digit
        cleaned = " ".join("".join(c for c in name if _is_name_char(c)).split())
        suggestion = cleaned or None

    return Finding(
        detail=f"The name '{raw}' {' and '.join(problems)}.",
        evidence={"name": raw, "digits": digits, "symbols": symbols, "extra_space": extra_space},
        suggested_value=suggestion,
        field="name",
        confidence=None if suggestion else "A digit may hide a letter (for example 4 for a). Check the admission register.",
    )


# ---------------------------------------------------------------- STU-002

@check("dob_valid")
def dob_valid(rec: dict, ctx: Context, params: dict) -> Finding | None:
    raw = (rec.get("dob") or "").strip()
    grade = rec.get("class_grade")
    ev: dict[str, Any] = {"dob": raw, "class": grade}

    if not raw:
        return Finding("No date of birth is recorded.", ev, field="dob")

    dob = parse_dob(raw)
    if dob is None:
        if ISO_RE.match(raw):
            try:
                iso = datetime.strptime(raw, "%Y-%m-%d").date()
                return Finding(
                    f"The date '{raw}' is written as year-month-day. UDISE+ expects DD/MM/YYYY.",
                    ev | {"problem": "wrong_format"},
                    suggested_value=iso.strftime("%d/%m/%Y"),
                    field="dob",
                    confidence="High: the date is valid, only the format differs.",
                )
            except ValueError:
                pass
        if DATE_RE.match(raw):
            return Finding(f"'{raw}' is not a real calendar date.", ev | {"problem": "impossible_date"}, field="dob")
        return Finding(f"'{raw}' cannot be read as a date in DD/MM/YYYY format.", ev | {"problem": "unparseable"}, field="dob")

    if dob > ctx.today:
        return Finding(f"The date of birth {raw} is in the future.", ev | {"problem": "future"}, field="dob")

    if grade in (None, ""):
        return None  # cannot check the age band without a class
    grade = int(grade)
    ref = ctx.age_reference_date
    age = age_on(dob, ref)
    lo = grade + int(params.get("min_offset", 4))
    hi = grade + int(params.get("max_offset", 8))
    ev |= {"age": age, "age_measured_on": ref.strftime("%d/%m/%Y"), "expected_age": [lo, hi]}
    if age < lo or age > hi:
        return Finding(
            f"A student born on {raw} is {age} years old on {ref.strftime('%d/%m/%Y')}, "
            f"outside the usual {lo} to {hi} for class {grade}.",
            ev | {"problem": "age_band"},
            field="dob",
            confidence="Medium: the date of birth or the class may be the wrong one.",
        )
    return None


# ---------------------------------------------------------------- STU-003

@check("gender_consistent")
def gender_consistent(rec: dict, ctx: Context, params: dict) -> Finding | None:
    raw = rec.get("gender")
    current = normalise_gender(raw)
    if current == "":
        prior = ctx.prior_year.get(rec.get("student_ref", ""))
        prior_g = normalise_gender(prior.get("gender")) if prior else None
        return Finding(
            "Gender is blank.",
            {"gender": raw or "", "prior_year_gender": prior_g or None},
            suggested_value=prior_g or None,
            field="gender",
            confidence="Suggestion taken from last year's record. Confirm before approving." if prior_g else None,
        )
    if current is None:
        return Finding(
            f"Gender value '{raw}' is not one of Male, Female or Transgender.",
            {"gender": raw}, field="gender",
        )

    prior = ctx.prior_year.get(rec.get("student_ref", ""))
    if prior:
        prior_g = normalise_gender(prior.get("gender"))
        if prior_g and prior_g != current:
            return Finding(
                f"Gender is {GENDER_LABEL[current]} this year but was {GENDER_LABEL[prior_g]} last year.",
                {"gender": GENDER_LABEL[current], "prior_year_gender": GENDER_LABEL[prior_g]},
                field="gender",
                confidence="Medium: either year's record could be the wrong one. Check the admission register.",
            )
    return None


# ---------------------------------------------------------------- STU-004

@check("aadhaar_present")
def aadhaar_present(rec: dict, ctx: Context, params: dict) -> Finding | None:
    status = str(rec.get("aadhaar_status") or "").strip().lower().replace(" ", "_")
    last4 = rec.get("aadhaar_last4") or None
    ev = {"aadhaar": mask_last4(last4), "aadhaar_status": status or "(blank)"}

    if not last4:
        return Finding("No Aadhaar number is recorded for this student.", ev | {"problem": "missing"})
    if status in ("update_pending", "pending"):
        return Finding(
            "The Aadhaar number is marked 'update pending', so it may be rejected at submission.",
            ev | {"problem": "update_pending"},
        )
    if status == "missing":
        return Finding(
            "A number is on record but its status still says 'missing'.",
            ev | {"problem": "status_mismatch"},
        )
    return None
