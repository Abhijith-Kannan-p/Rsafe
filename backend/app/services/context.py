"""Reference data the checks may consult: prior-year records, admission register, activity
logs, staff assignments, maintenance log, school statuses and the reference dates."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from ..config import ACADEMIC_YEAR_START, REFERENCE_DATE

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def parse_date(value: Any) -> date | None:
    """Strict DD/MM/YYYY parse. None if the text is not a real date in that format."""
    text = str(value or "").strip()
    if not DATE_RE.match(text):
        return None
    try:
        return datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        return None


def _truthy(v: Any) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "y")


@dataclass
class Context:
    academic_year_start: int = ACADEMIC_YEAR_START
    today: date = REFERENCE_DATE
    prior_year: dict[str, dict[str, Any]] = field(default_factory=dict)  # student_ref -> row
    admission_register: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)  # (school, adm_no)
    attendance: dict[str, list[date]] = field(default_factory=dict)  # student_ref -> sorted days present
    fees: dict[str, list[date]] = field(default_factory=dict)  # student_ref -> sorted payment dates
    assignments: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # teacher_ref -> rows
    maintenance: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # facility_ref -> rows by date
    schools: dict[str, dict[str, Any]] = field(default_factory=dict)  # code -> row

    @property
    def age_reference_date(self) -> date:
        """UDISE+ measures age on 30 September of the academic year."""
        return date(self.academic_year_start, 9, 30)

    @classmethod
    def build(
        cls,
        prior_year: list[dict] | None = None,
        admission_register: list[dict] | None = None,
        attendance: list[dict] | None = None,
        fees: list[dict] | None = None,
        assignments: list[dict] | None = None,
        maintenance: list[dict] | None = None,
        schools: list[dict] | None = None,
        **kwargs: Any,
    ) -> "Context":
        att: dict[str, list[date]] = defaultdict(list)
        for r in attendance or []:
            d = parse_date(r["date"])
            if d and _truthy(r.get("present", 1)):
                att[r["student_ref"]].append(d)
        fee: dict[str, list[date]] = defaultdict(list)
        for r in fees or []:
            d = parse_date(r["date"])
            if d:
                fee[r["student_ref"]].append(d)
        asg: dict[str, list[dict]] = defaultdict(list)
        for r in assignments or []:
            asg[r["teacher_ref"]].append(r)
        mnt: dict[str, list[dict]] = defaultdict(list)
        for r in maintenance or []:
            mnt[r["facility_ref"]].append(r)
        for rows in mnt.values():
            rows.sort(key=lambda r: parse_date(r["date"]) or date.min)
        return cls(
            prior_year={r["student_ref"]: r for r in prior_year or []},
            admission_register={(r["school_code"], r["admission_no"]): r for r in admission_register or []},
            attendance={k: sorted(v) for k, v in att.items()},
            fees={k: sorted(v) for k, v in fee.items()},
            assignments=dict(asg),
            maintenance=dict(mnt),
            schools={r["code"]: r for r in schools or []},
            **kwargs,
        )
