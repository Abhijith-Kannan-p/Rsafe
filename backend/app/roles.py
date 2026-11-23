"""Demo roles. Every route checks them server-side (see app/auth.py)."""

from enum import Enum


class Role(str, Enum):
    PRINCIPAL = "principal"
    TEACHER = "teacher"
    MIS_COORDINATOR = "mis_coordinator"
    ADMIN = "admin"
    STUDENT_PARENT = "student_parent"


ROLE_LABELS: dict[Role, str] = {
    Role.PRINCIPAL: "Principal",
    Role.TEACHER: "Teacher",
    Role.MIS_COORDINATOR: "MIS Coordinator",
    Role.ADMIN: "Admin",
    Role.STUDENT_PARENT: "Student and Parent",
}
