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
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Literal

from .context import DATE_RE, Context, parse_date
from .tokens import short


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

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
parse_dob = parse_date


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
    if rec.get("aadhaar_problem") == "invalid_length":
        return Finding(
            "The Aadhaar number on record does not have 12 digits, so it cannot be matched.",
            ev | {"problem": "invalid_length"},
        )
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


# ---------------------------------------------------------------- STU-005

def _norm_name_tokens(name: str) -> list[str]:
    """Lowercase, letters only (any script), punctuation becomes a space."""
    cleaned = "".join(c if unicodedata.category(c)[0] in ("L", "M") else " " for c in name.lower())
    return cleaned.split()


def name_similarity(a: str, b: str) -> float:
    """Order-insensitive similarity in [0, 1] (token-sorted SequenceMatcher ratio)."""
    ta, tb = " ".join(sorted(_norm_name_tokens(a))), " ".join(sorted(_norm_name_tokens(b)))
    return SequenceMatcher(None, ta, tb).ratio()


@check("name_matches_register")
def name_matches_register(rec: dict, ctx: Context, params: dict) -> Finding | None:
    name = (rec.get("name") or "").strip()
    reg = ctx.admission_register.get((rec.get("school_code", ""), rec.get("admission_no", "")))
    if not name or not reg or not (reg.get("name") or "").strip():
        return None  # blank names are STU-001's job; no register entry means nothing to compare
    reg_name = reg["name"].strip()
    a, b = _norm_name_tokens(name), _norm_name_tokens(reg_name)
    if a == b:
        return None  # differences in case, dots or spacing only

    sim = round(name_similarity(name, reg_name), 2)
    full_a, full_b = [t for t in a if len(t) > 1], [t for t in b if len(t) > 1]
    ev = {
        "name": name, "register_name": reg_name, "similarity": sim,
        "only_in_record": sorted(set(a) - set(b)), "only_in_register": sorted(set(b) - set(a)),
    }
    high, medium = float(params.get("high", 0.8)), float(params.get("medium", 0.5))
    if sorted(a) == sorted(b):
        kind, conf = "has the same words in a different order", "High: same words; only the order differs."
    elif full_a == full_b:
        kind, conf = "differs only by an initial", "High: very likely the same person; one record is missing an initial."
    elif sim >= high:
        kind, conf = "has a small spelling difference", f"High ({sim:.2f}): likely the same name written differently."
    elif sim >= medium:
        kind, conf = "is spelled differently", f"Medium ({sim:.2f}): check the documents before choosing a spelling."
    else:
        kind, conf = "does not match", f"Low ({sim:.2f}): the names may belong to different people. Check the admission number."
    return Finding(
        f"The name '{name}' {kind} from the admission register ('{reg_name}').",
        ev, confidence=conf, suggested_value=reg_name, field="name",
    )


# ---------------------------------------------------------------- STU-006 (dataset)

@check("duplicate_in_school", scope="dataset")
def duplicate_in_school(records: list[dict], ctx: Context, params: dict) -> list[tuple[dict, Finding]]:
    out: list[tuple[dict, Finding]] = []
    by_token: dict[tuple[str, str], list[dict]] = {}
    for r in records:
        if r.get("aadhaar_token"):
            by_token.setdefault((r["school_code"], r["aadhaar_token"]), []).append(r)
    for (_, tok), group in sorted(by_token.items()):
        if len(group) < 2:
            continue
        for r in group:
            others = [o["student_ref"] for o in group if o is not r]
            out.append((r, Finding(
                f"This student appears {len(group)} times in this school with the same Aadhaar token "
                f"({short(tok)}...). Other entry: {', '.join(others)}.",
                {"token": short(tok), "aadhaar_last4": r.get("aadhaar_last4"), "other_refs": others,
                 "match_on": "aadhaar_token"},
                confidence="High: identical Aadhaar token.",
            )))

    # Fallback for records without a token: same normalised name and date of birth.
    by_name: dict[tuple[str, str, str], list[dict]] = {}
    for r in records:
        if (r.get("name") or "").strip() and parse_date(r.get("dob")):
            key = (r["school_code"], " ".join(_norm_name_tokens(r["name"])), r["dob"].strip())
            by_name.setdefault(key, []).append(r)
    for group in by_name.values():
        if len(group) < 2 or all(r.get("aadhaar_token") for r in group):
            continue  # fully tokenised groups were handled above (or are genuinely different people)
        for r in group:
            others = [o["student_ref"] for o in group if o is not r]
            out.append((r, Finding(
                f"Another record in this school has the same name and date of birth: {', '.join(others)}.",
                {"other_refs": others, "match_on": "name_and_dob"},
                confidence="Medium: same name and date of birth, but no Aadhaar to confirm. Could be a different child.",
            )))
    return out


# ---------------------------------------------------------------- STU-007 (dataset)

@check("duplicate_across_schools", scope="dataset")
def duplicate_across_schools(records: list[dict], ctx: Context, params: dict) -> list[tuple[dict, Finding]]:
    """Matches on match_token only. Names are never used, and never shown across schools."""
    groups: dict[str, list[dict]] = {}
    for r in records:
        if r.get("match_token"):
            groups.setdefault(r["match_token"], []).append(r)
    out: list[tuple[dict, Finding]] = []
    for tok, group in sorted(groups.items()):
        schools = sorted({r["school_code"] for r in group})
        if len(schools) < 2:
            continue
        for r in group:
            elsewhere = sorted({o["school_code"] for o in group if o["school_code"] != r["school_code"]})
            out.append((r, Finding(
                f"The same Aadhaar token ({short(tok)}..., ending {r.get('aadhaar_last4')}) is also enrolled at "
                f"{', '.join(elsewhere)}.",
                {"token": short(tok), "aadhaar_last4": r.get("aadhaar_last4"), "schools": schools,
                 "matches": [{"school_code": o["school_code"], "student_ref": o["student_ref"]}
                             for o in group if o is not r],
                 "match_on": "match_token"},
                confidence="High: identical cluster match token, which means the same Aadhaar number. "
                           "Names were not used for this match.",
            )))
    return out


# ---------------------------------------------------------------- STU-008

def _fmt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


@check("dropout_with_activity")
def dropout_with_activity(rec: dict, ctx: Context, params: dict) -> Finding | None:
    if str(rec.get("enrolment_status") or "").strip().lower() != "dropout":
        return None
    window = int(params.get("window_days", 30))
    since = ctx.today - timedelta(days=window)
    ref = rec.get("student_ref", "")
    present = [d for d in ctx.attendance.get(ref, []) if since <= d <= ctx.today]
    paid = [d for d in ctx.fees.get(ref, []) if since <= d <= ctx.today]
    if not present and not paid:
        return None
    signs = []
    if present:
        signs.append(f"attended on {len(present)} day{'s' if len(present) > 1 else ''} (last on {_fmt(present[-1])})")
    if paid:
        signs.append(f"a fee was paid on {_fmt(paid[-1])}")
    return Finding(
        f"Marked as a dropout, but in the last {window} days the student {' and '.join(signs)}.",
        {"enrolment_status": "dropout", "window_days": window, "since": _fmt(since),
         "days_present": len(present), "last_attendance": _fmt(present[-1]) if present else None,
         "last_fee": _fmt(paid[-1]) if paid else None},
        confidence="Held: the dropout status is not applied until a person reviews it.",
    )


# ---------------------------------------------------------------- TCH-001

@check("teacher_subject_match")
def teacher_subject_match(rec: dict, ctx: Context, params: dict) -> list[Finding]:
    qualified = [s.strip() for s in str(rec.get("subjects") or "").split(";") if s.strip()]
    lower = {s.lower() for s in qualified}
    out = []
    for a in ctx.assignments.get(rec.get("teacher_ref", ""), []):
        subject = str(a.get("subject") or "").strip()
        if subject and subject.lower() not in lower:
            cls = f"{a.get('class_grade')}{a.get('section', '')}"
            out.append(Finding(
                f"Assigned to teach {subject} for class {cls}, but qualified only in "
                f"{', '.join(qualified) or 'no subject on record'}.",
                {"assigned_subject": subject, "class": cls, "qualified_subjects": qualified},
            ))
    return out


# ---------------------------------------------------------------- FAC-001

@check("facility_matches_log")
def facility_matches_log(rec: dict, ctx: Context, params: dict) -> Finding | None:
    log = ctx.maintenance.get(rec.get("facility_ref", ""), [])
    if not log:
        return None
    latest = log[-1]
    status = str(rec.get("status") or "").strip().lower()
    condition = str(latest.get("condition") or "").strip().lower()
    ev = {"status": status, "latest_log_date": latest.get("date"), "latest_condition": condition,
          "log_note": latest.get("note", "")}
    label = str(rec.get("facility_type", "facility")).replace("_", " ")
    if status == "functional" and condition == "broken":
        return Finding(
            f"The {label} is marked functional, but the maintenance log on {latest.get('date')} says broken "
            f"({latest.get('note', '')}).", ev,
        )
    if status == "non_functional" and condition in ("working", "repaired"):
        return Finding(
            f"The {label} is marked non-functional, but the maintenance log on {latest.get('date')} says {condition}.",
            ev,
        )
    return None


# ---------------------------------------------------------------- SYS-001

CLOSED = ("closed", "merged")


@check("transfer_after_closure")
def transfer_after_closure(rec: dict, ctx: Context, params: dict) -> Finding | None:
    prev = str(rec.get("previous_school_code") or "").strip()
    old = ctx.schools.get(prev) if prev else None
    if old and old.get("status") in CLOSED and not str(rec.get("transfer_status") or "").strip():
        into = f" into {old['merged_into']}" if old.get("merged_into") else ""
        return Finding(
            f"Came from {old.get('name', prev)} ({prev}), which was {old['status']}{into}, "
            f"but has no transfer status.",
            {"previous_school_code": prev, "previous_school_status": old["status"],
             "merged_into": old.get("merged_into") or None, "transfer_status": ""},
            suggested_value="transferred_in", field="transfer_status",
            confidence="High: the move is recorded, only the status is missing.",
        )
    own = ctx.schools.get(rec.get("school_code", ""))
    if own and own.get("status") in CLOSED and str(rec.get("enrolment_status", "")).lower() == "active":
        return Finding(
            f"Still enrolled as active in {own.get('name', own['code'])}, which is {own['status']}.",
            {"school_status": own["status"], "merged_into": own.get("merged_into") or None},
        )
    return None
