"""STU-001 to STU-004: known-good and known-bad records for each rule."""

from datetime import date

import pytest

from app.services.context import Context
from app.services.engine import run_rules
from app.services.rules import load_rules

RULES = {r.id: r for r in load_rules()}
CTX = Context.build(
    prior_year=[
        {"student_ref": "S1", "school_code": "SYN-0001", "gender": "M", "class_grade": 4},
        {"student_ref": "S2", "school_code": "SYN-0001", "gender": "F", "class_grade": 4},
    ],
    academic_year_start=2026,
    today=date(2026, 11, 16),
)


def student(**over):
    base = {
        "student_ref": "S1", "school_code": "SYN-0001", "admission_no": "01ADM0001",
        "name": "Rahul Sharma", "dob": "14/03/2016", "gender": "M", "class_grade": 5,
        "aadhaar_last4": "4821", "aadhaar_status": "verified", "enrolment_status": "active",
    }
    base.update(over)
    return base


def run(rule_id, rec):
    return run_rules([RULES[rule_id]], {"student": [rec]}, CTX)


# -------------------------------------------------- the clean record passes every rule

def test_clean_record_passes_all_core_rules():
    assert run_rules([RULES[i] for i in ("STU-001", "STU-002", "STU-003", "STU-004")],
                     {"student": [student()]}, CTX) == []


# -------------------------------------------------- STU-001

@pytest.mark.parametrize("name", ["Ananya R. Kumar", "D'Souza Mary", "Anne-Marie Thomas", "अनन्या कुमार", "അനന്യ"])
def test_stu001_good(name):
    assert run("STU-001", student(name=name)) == []


@pytest.mark.parametrize(
    "name, fragment, suggestion",
    [
        ("", "No name", None),
        ("   ", "No name", None),
        ("R4hul Sharma", "digit 4", None),
        ("Priya@ Nair", "symbol @", "Priya Nair"),
        ("Kiran  Das", "extra spaces", "Kiran Das"),
        (" Meera Iyer#", "symbol #", "Meera Iyer"),
    ],
)
def test_stu001_bad(name, fragment, suggestion):
    [issue] = run("STU-001", student(name=name))
    assert issue.rule_id == "STU-001" and issue.rule_version == "1.0.0"
    assert issue.severity == "high"
    assert fragment in issue.detail
    assert issue.suggested_value == suggestion
    assert issue.entity_ref == "S1" and issue.school_code == "SYN-0001"


def test_stu001_digit_has_confidence_note():
    [issue] = run("STU-001", student(name="R4hul Sharma"))
    assert issue.confidence and "digit" in issue.confidence


# -------------------------------------------------- STU-002

@pytest.mark.parametrize("dob, grade", [("14/03/2016", 5), ("01/10/2020", 1), ("30/09/2010", 10), ("29/02/2016", 5)])
def test_stu002_good(dob, grade):
    assert run("STU-002", student(dob=dob, class_grade=grade)) == []


@pytest.mark.parametrize(
    "dob, grade, problem, fragment",
    [
        ("", 5, None, "No date of birth"),
        ("31/02/2015", 5, "impossible_date", "not a real calendar date"),
        ("2013-13-05", 5, "unparseable", "cannot be read"),
        ("14-03-2016", 5, "unparseable", "cannot be read"),
        ("14/06/2023", 8, "age_band", "3 years old"),
        ("01/01/2000", 5, "age_band", "outside the usual 9 to 13"),
        ("01/01/2027", 5, "future", "in the future"),
    ],
)
def test_stu002_bad(dob, grade, problem, fragment):
    [issue] = run("STU-002", student(dob=dob, class_grade=grade))
    assert fragment in issue.detail
    assert issue.evidence.get("problem") == problem


def test_stu002_iso_date_gets_converted_suggestion():
    [issue] = run("STU-002", student(dob="2016-03-14"))
    assert issue.suggested_value == "14/03/2016"
    assert issue.confidence.startswith("High")


def test_stu002_age_band_reports_evidence():
    [issue] = run("STU-002", student(dob="14/06/2023", class_grade=8))
    assert issue.evidence["age"] == 3
    assert issue.evidence["expected_age"] == [12, 16]
    assert issue.evidence["age_measured_on"] == "30/09/2026"


def test_stu002_no_class_skips_age_band():
    assert run("STU-002", student(dob="14/06/2023", class_grade=None)) == []


# -------------------------------------------------- STU-003

@pytest.mark.parametrize("gender", ["M", "m", "Male", "BOY"])
def test_stu003_good(gender):
    assert run("STU-003", student(gender=gender)) == []


def test_stu003_good_without_prior_year():
    assert run("STU-003", student(student_ref="NEW-1", gender="F")) == []


def test_stu003_missing_suggests_prior_year_value():
    [issue] = run("STU-003", student(gender=""))
    assert issue.detail == "Gender is blank."
    assert issue.suggested_value == "M"
    assert "Confirm" in issue.confidence


def test_stu003_mismatch_with_prior_year():
    [issue] = run("STU-003", student(student_ref="S2", gender="M"))
    assert "Male this year but was Female last year" in issue.detail
    assert issue.suggested_value is None  # never guess which year is right
    assert issue.confidence.startswith("Medium")


def test_stu003_unknown_value():
    [issue] = run("STU-003", student(gender="X"))
    assert "not one of" in issue.detail


# -------------------------------------------------- STU-004

@pytest.mark.parametrize("status", ["verified", "Verified", ""])
def test_stu004_good(status):
    assert run("STU-004", student(aadhaar_status=status)) == []


@pytest.mark.parametrize(
    "last4, status, problem",
    [
        (None, "missing", "missing"),
        ("", "verified", "missing"),
        ("4821", "update_pending", "update_pending"),
        ("4821", "Update Pending", "update_pending"),
        ("4821", "missing", "status_mismatch"),
    ],
)
def test_stu004_bad(last4, status, problem):
    [issue] = run("STU-004", student(aadhaar_last4=last4, aadhaar_status=status))
    assert issue.evidence["problem"] == problem


def test_stu004_evidence_is_masked():
    [issue] = run("STU-004", student(aadhaar_status="update_pending"))
    assert issue.evidence["aadhaar"] == "XXXX XXXX 4821"
