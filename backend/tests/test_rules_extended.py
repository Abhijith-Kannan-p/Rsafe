"""STU-005 to STU-008, TCH-001, FAC-001, SYS-001: known-good and known-bad cases."""

from datetime import date

import pytest

from app.services.context import Context
from app.services.engine import run_rules
from app.services.rules import load_rules

RULES = {r.id: r for r in load_rules()}
TODAY = date(2026, 11, 16)


def ctx(**kw):
    return Context.build(today=TODAY, academic_year_start=2026, **kw)


def student(**over):
    base = {"student_ref": "S1", "school_code": "SYN-0001", "admission_no": "A1", "name": "Ananya Kumar",
            "dob": "14/03/2016", "gender": "F", "class_grade": 5, "aadhaar_last4": "1234",
            "aadhaar_token": "tok-a", "match_token": "m-a", "enrolment_status": "active",
            "previous_school_code": "", "transfer_status": ""}
    base.update(over)
    return base


def run(rule_id, records, c=None, entity="student"):
    return run_rules([RULES[rule_id]], {entity: records}, c or ctx())


# ------------------------------------------------------------------ STU-005

def reg(name):
    return ctx(admission_register=[{"school_code": "SYN-0001", "admission_no": "A1", "name": name}])


@pytest.mark.parametrize("register_name", ["Ananya Kumar", "ANANYA KUMAR", "Ananya  Kumar", "Ananya Kumar."])
def test_stu005_good(register_name):
    assert run("STU-005", [student()], reg(register_name)) == []


def test_stu005_good_without_register_entry():
    assert run("STU-005", [student()], ctx()) == []


@pytest.mark.parametrize(
    "register_name, kind, conf",
    [
        ("Kumar Ananya", "same words in a different order", "High"),
        ("Ananya R. Kumar", "differs only by an initial", "High"),
        ("Ananiya Kumar", "small spelling difference", "High"),
        ("Anu Kumari", "spelled differently", "Medium"),
        ("Mohammed Irfan", "does not match", "Low"),
    ],
)
def test_stu005_bad(register_name, kind, conf):
    [issue] = run("STU-005", [student()], reg(register_name))
    assert kind in issue.detail
    assert issue.confidence.startswith(conf)
    assert issue.suggested_value == register_name  # proposal only; never applied automatically
    assert 0 <= issue.evidence["similarity"] <= 1


def test_stu005_blank_name_left_to_stu001():
    assert run("STU-005", [student(name="")], reg("Ananya Kumar")) == []


# ------------------------------------------------------------------ STU-006

def test_stu006_good_distinct_tokens():
    assert run("STU-006", [student(), student(student_ref="S2", aadhaar_token="tok-b", name="Riya Das")]) == []


def test_stu006_good_same_token_different_schools():
    # cross-school is STU-007's job
    assert run("STU-006", [student(), student(student_ref="S2", school_code="SYN-0002")]) == []


def test_stu006_bad_same_token():
    issues = run("STU-006", [student(), student(student_ref="S2", admission_no="A2")])
    assert {i.entity_ref for i in issues} == {"S1", "S2"}
    assert issues[0].evidence["match_on"] == "aadhaar_token"


def test_stu006_fallback_name_and_dob_when_no_token():
    issues = run("STU-006", [student(aadhaar_token=None), student(student_ref="S2", aadhaar_token=None)])
    assert len(issues) == 2 and issues[0].confidence.startswith("Medium")


def test_stu006_twins_with_tokens_not_flagged():
    # same name and DOB but different Aadhaar tokens: different children
    assert run("STU-006", [student(), student(student_ref="S2", aadhaar_token="tok-b")]) == []


# ------------------------------------------------------------------ STU-007

def test_stu007_good_same_school_only():
    assert run("STU-007", [student(), student(student_ref="S2")]) == []


def test_stu007_good_no_token():
    assert run("STU-007", [student(match_token=None), student(student_ref="S2", school_code="SYN-0002", match_token=None)]) == []


def test_stu007_bad_matches_by_token_not_name():
    a = student()
    b = student(student_ref="X9", school_code="SYN-0002", name="Completely Different")
    issues = run("STU-007", [a, b])
    assert {(i.school_code, i.entity_ref) for i in issues} == {("SYN-0001", "S1"), ("SYN-0002", "X9")}
    i = next(x for x in issues if x.entity_ref == "S1")
    assert i.evidence["schools"] == ["SYN-0001", "SYN-0002"]
    assert i.evidence["matches"] == [{"school_code": "SYN-0002", "student_ref": "X9"}]
    assert "Completely Different" not in str(i.to_dict())


def test_stu007_same_name_different_token_not_matched():
    assert run("STU-007", [student(), student(student_ref="X9", school_code="SYN-0002", match_token="m-z")]) == []


# ------------------------------------------------------------------ STU-008

def activity(att=(), fees=()):
    return ctx(
        attendance=[{"student_ref": "S1", "date": d, "present": "1"} for d in att],
        fees=[{"student_ref": "S1", "date": d} for d in fees],
    )


def test_stu008_good_active_student_with_attendance():
    assert run("STU-008", [student()], activity(att=["10/11/2026"])) == []


def test_stu008_good_genuine_dropout():
    assert run("STU-008", [student(enrolment_status="dropout")], activity(att=["15/07/2026"], fees=["01/08/2026"])) == []


def test_stu008_absent_days_do_not_count():
    c = ctx(attendance=[{"student_ref": "S1", "date": "10/11/2026", "present": "0"}])
    assert run("STU-008", [student(enrolment_status="dropout")], c) == []


def test_stu008_bad_recent_attendance_is_held():
    [i] = run("STU-008", [student(enrolment_status="dropout")], activity(att=["03/11/2026", "10/11/2026"]))
    assert i.held is True
    assert i.evidence["days_present"] == 2 and i.evidence["last_attendance"] == "10/11/2026"
    assert "attended on 2 days" in i.detail


def test_stu008_bad_recent_fee_is_held():
    [i] = run("STU-008", [student(enrolment_status="Dropout")], activity(fees=["05/11/2026"]))
    assert i.held and "fee was paid on 05/11/2026" in i.detail


# ------------------------------------------------------------------ TCH-001

def teacher(subjects="Mathematics"):
    return {"teacher_ref": "T1", "school_code": "SYN-0002", "name": "T", "subjects": subjects}


def assignments(*subjects):
    return ctx(assignments=[{"teacher_ref": "T1", "class_grade": 7, "section": "A", "subject": s} for s in subjects])


def test_tch001_good():
    assert run("TCH-001", [teacher("Mathematics;Science")], assignments("Mathematics", "science"), "teacher") == []


def test_tch001_bad():
    [i] = run("TCH-001", [teacher()], assignments("Mathematics", "Hindi"), "teacher")
    assert i.entity_ref == "T1" and "Hindi for class 7A" in i.detail


# ------------------------------------------------------------------ FAC-001

def facility(status):
    return {"facility_ref": "F1", "school_code": "SYN-0002", "facility_type": "toilet_girls", "status": status}


def log(*entries):
    return ctx(maintenance=[{"facility_ref": "F1", "date": d, "condition": c, "note": "n"} for d, c in entries])


@pytest.mark.parametrize("status, entries", [
    ("functional", [("01/09/2026", "working")]),
    ("functional", [("01/09/2026", "broken"), ("01/10/2026", "repaired")]),
    ("non_functional", [("01/09/2026", "broken")]),
    ("functional", []),
])
def test_fac001_good(status, entries):
    assert run("FAC-001", [facility(status)], log(*entries), "facility") == []


def test_fac001_bad_functional_but_broken():
    # log rows out of order on purpose: the latest by date must win
    [i] = run("FAC-001", [facility("functional")], log(("03/11/2026", "broken"), ("01/09/2026", "working")), "facility")
    assert "toilet girls is marked functional" in i.detail and i.evidence["latest_log_date"] == "03/11/2026"


def test_fac001_bad_non_functional_but_repaired():
    [i] = run("FAC-001", [facility("non_functional")], log(("01/10/2026", "repaired")), "facility")
    assert "non-functional" in i.detail


# ------------------------------------------------------------------ SYS-001

SCHOOLS = [
    {"code": "SYN-0001", "name": "Riverside", "status": "open", "merged_into": ""},
    {"code": "SYN-0004", "name": "Old Town", "status": "merged", "merged_into": "SYN-0001"},
    {"code": "SYN-0005", "name": "Hill", "status": "open", "merged_into": ""},
]


@pytest.mark.parametrize("prev, status", [("", ""), ("SYN-0004", "transferred_in"), ("SYN-0005", "")])
def test_sys001_good(prev, status):
    assert run("SYS-001", [student(previous_school_code=prev, transfer_status=status)], ctx(schools=SCHOOLS)) == []


def test_sys001_bad_transfer_gap():
    [i] = run("SYS-001", [student(previous_school_code="SYN-0004")], ctx(schools=SCHOOLS))
    assert "merged into SYN-0001" in i.detail and i.suggested_value == "transferred_in"


def test_sys001_bad_still_in_closed_school():
    [i] = run("SYS-001", [student(school_code="SYN-0004")], ctx(schools=SCHOOLS))
    assert "Still enrolled" in i.detail
