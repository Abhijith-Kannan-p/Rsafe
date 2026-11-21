"""Demo roles. Enforcement on routes arrives in Phase 4."""

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
