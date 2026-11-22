"""Load the synthetic CSV set into SQLite (replacing what is there).

Students go through ingest.normalise_student, so only tokens and the last four digits of
the Aadhaar number reach the database.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, select

from .. import models as m
from . import audit
from .ingest import _int_or_none, load_dataset, read_csv
from .tokens import Tokenizer


def _pick(model, row: dict) -> dict:
    cols = set(model.model_fields)
    return {k: v for k, v in row.items() if k in cols and k != "id"}


def load_into_db(data_dir: Path, engine: Engine, tokenizer: Tokenizer | None = None) -> dict[str, int]:
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    data, _ = load_dataset(data_dir, tokenizer)
    d = data_dir

    counts: dict[str, int] = {}
    with Session(engine) as s:
        def add_all(name: str, objs: list) -> None:
            s.add_all(objs)
            counts[name] = len(objs)

        add_all("schools", [m.School(**_pick(m.School, r | {"merged_into": r.get("merged_into") or None}))
                            for r in read_csv(d / "schools.csv")])
        s.flush()
        add_all("students", [m.Student(**_pick(m.Student, r)) for r in data["student"]])
        add_all("admission_register", [m.AdmissionRegisterEntry(**_pick(m.AdmissionRegisterEntry, r))
                                       for r in read_csv(d / "admission_register.csv")])
        add_all("prior_year", [m.PriorYearRecord(**_pick(m.PriorYearRecord, r | {"class_grade": _int_or_none(r["class_grade"])}))
                               for r in read_csv(d / "prior_year.csv")])
        add_all("teachers", [m.Teacher(**_pick(m.Teacher, r)) for r in data["teacher"]])
        add_all("teacher_assignments", [m.TeacherAssignment(**_pick(m.TeacherAssignment, r | {"class_grade": int(r["class_grade"])}))
                                        for r in read_csv(d / "teacher_assignments.csv")])
        add_all("facilities", [m.Facility(**_pick(m.Facility, r)) for r in data["facility"]])
        add_all("maintenance_log", [m.MaintenanceLog(**_pick(m.MaintenanceLog, r)) for r in read_csv(d / "maintenance_log.csv")])
        add_all("attendance", [m.AttendanceRecord(**_pick(m.AttendanceRecord, r | {"present": r["present"] == "1"}))
                               for r in read_csv(d / "attendance.csv")])
        add_all("fees", [m.FeeRecord(**_pick(m.FeeRecord, r | {"amount": int(r["amount"])})) for r in read_csv(d / "fees.csv")])
        s.commit()
        audit.append(s, "System (seed)", "system", "data.load", str(data_dir.name),
                     {"synthetic": True, "counts": counts})
    return counts


def seed_and_validate(data_dir: Path, engine: Engine, tokenizer: Tokenizer | None = None) -> dict:
    """Load the CSVs, then run every rule once for every open school, as the system user."""
    from .rules import load_rules
    from .validation import run_validation

    counts = load_into_db(data_dir, engine, tokenizer)
    with Session(engine) as s:
        schools = [x.code for x in s.exec(select(m.School).where(m.School.status == "open").order_by(m.School.code))]
        result = run_validation(s, load_rules(), schools, "System (seed)", "system")
    return {"counts": counts, "validation": result}
