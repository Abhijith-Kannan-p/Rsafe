"""Reference data the checks may consult (prior-year records, admission register, dates)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ..config import ACADEMIC_YEAR_START


@dataclass
class Context:
    academic_year_start: int = ACADEMIC_YEAR_START
    today: date = field(default_factory=date.today)
    prior_year: dict[str, dict[str, Any]] = field(default_factory=dict)  # student_ref -> row
    admission_register: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)  # (school, adm_no)

    @property
    def age_reference_date(self) -> date:
        """UDISE+ measures age on 30 September of the academic year."""
        return date(self.academic_year_start, 9, 30)

    @classmethod
    def build(
        cls,
        prior_year: list[dict] | None = None,
        admission_register: list[dict] | None = None,
        **kwargs: Any,
    ) -> "Context":
        return cls(
            prior_year={r["student_ref"]: r for r in prior_year or []},
            admission_register={(r["school_code"], r["admission_no"]): r for r in admission_register or []},
            **kwargs,
        )
