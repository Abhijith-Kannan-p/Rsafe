"""What each role may see. Used by every route that returns records or issues."""

from __future__ import annotations

from sqlmodel import Session, select

from ..auth import Identity
from ..models import Issue, School, Student, TeacherAssignment
from ..roles import Role


def visible_schools(s: Session, who: Identity) -> list[str]:
    if who.role == Role.ADMIN:
        return [x.code for x in s.exec(select(School).where(School.status == "open"))]
    if who.role == Role.MIS_COORDINATOR:
        return [x.code for x in s.exec(select(School).where(School.cluster == who.cluster, School.status == "open"))]
    return [who.school_code] if who.school_code else []


def teacher_classes(s: Session, teacher_ref: str) -> set[tuple[int, str]]:
    rows = s.exec(select(TeacherAssignment).where(TeacherAssignment.teacher_ref == teacher_ref))
    return {(a.class_grade, a.section) for a in rows}


def teacher_student_refs(s: Session, who: Identity) -> set[str]:
    classes = teacher_classes(s, who.teacher_ref or "")
    students = s.exec(select(Student).where(Student.school_code == who.school_code))
    return {st.student_ref for st in students if (st.class_grade, st.section) in classes}


def visible_student_refs(s: Session, who: Identity) -> set[str] | None:
    """None means "every student in the visible schools"."""
    if who.role == Role.TEACHER:
        return teacher_student_refs(s, who)
    if who.role == Role.STUDENT_PARENT:
        return {who.student_ref} if who.student_ref else set()
    return None


def can_see_issue(s: Session, who: Identity, issue: Issue) -> bool:
    if issue.school_code not in visible_schools(s, who):
        return False
    if who.role == Role.TEACHER:
        if issue.entity == "teacher":
            return issue.entity_ref == who.teacher_ref
        return issue.entity == "student" and issue.entity_ref in teacher_student_refs(s, who)
    if who.role == Role.STUDENT_PARENT:
        return issue.entity == "student" and issue.entity_ref == who.student_ref
    return True


def filter_issues(s: Session, who: Identity, issues: list[Issue]) -> list[Issue]:
    schools = set(visible_schools(s, who))
    issues = [i for i in issues if i.school_code in schools]
    if who.role == Role.TEACHER:
        refs = teacher_student_refs(s, who)
        return [i for i in issues if (i.entity == "student" and i.entity_ref in refs)
                or (i.entity == "teacher" and i.entity_ref == who.teacher_ref)]
    if who.role == Role.STUDENT_PARENT:
        return [i for i in issues if i.entity == "student" and i.entity_ref == who.student_ref]
    return issues
