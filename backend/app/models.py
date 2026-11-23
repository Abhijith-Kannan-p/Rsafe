"""Database tables.

Privacy invariant: no table has a column for a full Aadhaar number. Students carry only
`aadhaar_token` (keyed HMAC) and `aadhaar_last4`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class School(SQLModel, table=True):
    code: str = Field(primary_key=True)  # synthetic codes look like SYN-0001
    name: str
    district: str
    block: str
    cluster: str
    status: str = "open"  # open | closed | merged
    merged_into: Optional[str] = None


class Student(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_ref: str = Field(index=True)  # school-internal reference
    school_code: str = Field(index=True, foreign_key="school.code")
    admission_no: str = ""
    name: str = ""
    dob: str = ""  # kept as the raw string; rules decide whether it parses
    gender: str = ""
    class_grade: Optional[int] = None
    section: str = ""
    guardian_name: str = ""
    aadhaar_token: Optional[str] = Field(default=None, index=True)  # HMAC(school key), base32
    match_token: Optional[str] = Field(default=None, index=True)  # HMAC(cluster match key), base32
    aadhaar_last4: Optional[str] = None
    aadhaar_problem: Optional[str] = None  # e.g. invalid_length (the raw value itself is never kept)
    aadhaar_status: str = ""  # verified | missing | update_pending
    enrolment_status: str = "active"  # active | dropout | transferred
    previous_school_code: str = ""
    transfer_status: str = ""
    batch_id: Optional[str] = None


class AdmissionRegisterEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    school_code: str = Field(index=True)
    admission_no: str = Field(index=True)
    name: str
    dob: str = ""


class PriorYearRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_ref: str = Field(index=True)
    school_code: str
    gender: str = ""
    class_grade: Optional[int] = None


class Teacher(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    teacher_ref: str = Field(index=True)
    school_code: str = Field(index=True)
    name: str
    subjects: str = ""  # semicolon-separated qualified subjects


class TeacherAssignment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    teacher_ref: str = Field(index=True)
    school_code: str
    class_grade: int
    section: str
    subject: str


class Facility(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    facility_ref: str = Field(index=True)
    school_code: str = Field(index=True)
    facility_type: str
    status: str  # functional | non_functional


class MaintenanceLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    facility_ref: str = Field(index=True)
    school_code: str
    date: str
    condition: str  # working | broken | repaired
    note: str = ""


class AttendanceRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_ref: str = Field(index=True)
    school_code: str
    date: str
    present: bool = True


class FeeRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_ref: str = Field(index=True)
    school_code: str
    date: str
    amount: int


class Issue(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # Stable identity across validation runs: sha256(rule|entity|ref|detail). Lets a re-run keep
    # human decisions and mark vanished problems as resolved.
    fingerprint: str = Field(index=True)
    rule_id: str = Field(index=True)
    rule_version: str
    severity: str  # high | medium | low
    entity: str  # student | teacher | facility
    entity_ref: str
    school_code: str = Field(index=True)
    title: str = ""
    message: str
    detail: str = ""
    fix: str
    confidence: Optional[str] = None
    suggested_value: Optional[str] = None
    suggested_field: Optional[str] = None
    evidence: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    # open | held (waiting for review, change NOT applied) | approved | edited | resolved (gone on re-run)
    status: str = Field(default="open", index=True)
    note: str = ""
    acted_by: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AuditEntry(SQLModel, table=True):
    """Hash-chained audit row; see app/services/audit.py.

    ts is an ISO string, not a datetime, so the value that was hashed is exactly the value read back.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: str
    actor: str
    role: str
    action: str
    record_ref: str = ""
    payload: str = ""  # canonical JSON string
    prev_hash: str = ""
    hash: str = Field(default="", index=True)
