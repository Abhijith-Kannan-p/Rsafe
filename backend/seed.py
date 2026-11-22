"""Synthetic data generator for Rsafe.

EVERYTHING HERE IS FAKE. Names are drawn from generic lists, school codes use the
"SYN-" prefix, and synthetic Aadhaar-like IDs always start with the digit 0. Real
Aadhaar numbers never start with 0 or 1, so a generated ID can never be a real one.

The output is fully reproducible for a given --seed. Every deliberately injected
problem is written to injected.json so tests can check the rules against ground truth.

Usage:
    python seed.py                          # default demo set -> data/
    python seed.py --per-school 1667 --out data/perf   # ~5,000 students for perf runs
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

DEFAULT_SEED = 20261125
REFERENCE_DATE = date(2026, 11, 16)  # fixed "today" for reproducible data
ACADEMIC_YEAR = "2026-27"

FIRST_F = [
    "Aditi", "Anjali", "Bhavya", "Chitra", "Deepa", "Divya", "Fathima", "Gauri", "Harini",
    "Isha", "Jyothi", "Kavya", "Lakshmi", "Meera", "Neha", "Nikita", "Pooja", "Priya",
    "Riya", "Sana", "Shreya", "Sneha", "Swathi", "Tanvi", "Uma", "Vaishnavi", "Zoya",
]
FIRST_M = [
    "Aarav", "Abhinav", "Aditya", "Akash", "Arjun", "Bharat", "Deepak", "Farhan", "Ganesh",
    "Harsh", "Imran", "Karthik", "Kiran", "Manoj", "Naveen", "Nikhil", "Pranav", "Rahul",
    "Rohan", "Sachin", "Sanjay", "Tarun", "Varun", "Vikram", "Vishnu", "Yash",
]
LAST = [
    "Sharma", "Nair", "Menon", "Reddy", "Das", "Patel", "Singh", "Kumar", "Pillai", "Iyer",
    "Rao", "Joshi", "Verma", "Gupta", "Thomas", "Khan", "Varghese", "Mishra", "Bose", "Shetty",
]

# (code, name, district, block, cluster, status, merged_into)
SCHOOLS = [
    ("SYN-0001", "Govt Model School Riverside", "Synthetic District", "North Block", "CL-01", "open", ""),
    ("SYN-0002", "Govt UP School Hillview", "Synthetic District", "North Block", "CL-01", "open", ""),
    ("SYN-0003", "Govt High School Lakeside", "Synthetic District", "North Block", "CL-01", "open", ""),
    # Closed and merged into SYN-0001: the source of the transfer-gap case (SYS-001).
    ("SYN-0004", "Govt LP School Old Town", "Synthetic District", "North Block", "CL-01", "merged", "SYN-0001"),
]
ACTIVE_SCHOOLS = [s[0] for s in SCHOOLS if s[5] == "open"]

SUBJECTS = ["Mathematics", "Science", "English", "Hindi", "Social Science", "Malayalam"]
FACILITY_TYPES = [
    "drinking_water", "toilet_boys", "toilet_girls", "electricity", "library", "ramp", "playground",
]

STUDENT_COLUMNS = [
    "student_ref", "school_code", "admission_no", "name", "dob", "gender", "class_grade",
    "section", "guardian_name", "aadhaar", "aadhaar_status", "enrolment_status",
    "previous_school_code", "transfer_status",
]


@dataclass
class Injection:
    rule: str
    entity: str
    school_code: str
    ref: str
    note: str


@dataclass
class Dataset:
    schools: list[dict] = field(default_factory=list)
    students: list[dict] = field(default_factory=list)
    admission_register: list[dict] = field(default_factory=list)
    prior_year: list[dict] = field(default_factory=list)
    teachers: list[dict] = field(default_factory=list)
    teacher_assignments: list[dict] = field(default_factory=list)
    facilities: list[dict] = field(default_factory=list)
    maintenance_log: list[dict] = field(default_factory=list)
    attendance: list[dict] = field(default_factory=list)
    fees: list[dict] = field(default_factory=list)
    injected: list[Injection] = field(default_factory=list)


def fmt(d: date) -> str:
    """Canonical UDISE-style date format: DD/MM/YYYY."""
    return d.strftime("%d/%m/%Y")


def school_days(end: date, count: int) -> list[date]:
    days, d = [], end
    while len(days) < count:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return sorted(days)


class Generator:
    def __init__(self, seed: int, per_school: int):
        self.rng = random.Random(seed)
        self.per_school = per_school
        self.ds = Dataset()
        self._aadhaar_seen: set[str] = set()
        self._adm_counter: dict[str, int] = {}

    # ---------- primitives ----------
    def synthetic_aadhaar(self) -> str:
        while True:
            value = "0" + "".join(self.rng.choice("0123456789") for _ in range(11))
            if value not in self._aadhaar_seen:
                self._aadhaar_seen.add(value)
                return value

    def person_name(self, gender: str) -> str:
        first = self.rng.choice(FIRST_F if gender == "F" else FIRST_M)
        return f"{first} {self.rng.choice(LAST)}"

    def dob_for_class(self, class_grade: int) -> date:
        age = class_grade + 5 + self.rng.choice([0, 0, 0, 1])
        year = REFERENCE_DATE.year - age
        start = date(year - 1, 10, 1)  # age measured at 30 Sep of the academic year
        return start + timedelta(days=self.rng.randrange(365))

    def next_admission_no(self, school: str) -> str:
        n = self._adm_counter.get(school, 0) + 1
        self._adm_counter[school] = n
        return f"{school[-2:]}ADM{n:04d}"

    def make_student(self, school: str, idx: int, **overrides) -> dict:
        gender = overrides.pop("gender", None) or self.rng.choice(["M", "F"])
        class_grade = overrides.pop("class_grade", None) or self.rng.randint(1, 10)
        row = {
            "student_ref": f"{school}-S{idx:04d}",
            "school_code": school,
            "admission_no": self.next_admission_no(school),
            "name": self.person_name(gender),
            "dob": fmt(self.dob_for_class(class_grade)),
            "gender": gender,
            "class_grade": class_grade,
            "section": self.rng.choice(["A", "B"]),
            "guardian_name": self.person_name("M" if self.rng.random() < 0.7 else "F"),
            "aadhaar": self.synthetic_aadhaar(),
            "aadhaar_status": "verified",
            "enrolment_status": "active",
            "previous_school_code": "",
            "transfer_status": "",
        }
        row.update(overrides)
        return row

    def register(self, s: dict, name: str | None = None) -> None:
        self.ds.admission_register.append({
            "school_code": s["school_code"],
            "admission_no": s["admission_no"],
            "name": s["name"] if name is None else name,
            "dob": s["dob"],
        })

    def inject(self, rule: str, s: dict, note: str, entity: str = "student") -> None:
        self.ds.injected.append(Injection(rule, entity, s["school_code"], s["student_ref"], note))

    # ---------- build ----------
    def build(self) -> Dataset:
        ds = self.ds
        for code, name, district, block, cluster, status, merged_into in SCHOOLS:
            ds.schools.append({
                "code": code, "name": name, "district": district, "block": block,
                "cluster": cluster, "status": status, "merged_into": merged_into,
            })

        by_school: dict[str, list[dict]] = {}
        for school in ACTIVE_SCHOOLS:
            by_school[school] = [self.make_student(school, i + 1) for i in range(self.per_school)]

        self._inject_student_problems(by_school)

        for school in ACTIVE_SCHOOLS:
            for s in by_school[school]:
                ds.students.append(s)
                self.register(s, s.pop("_register_name", None))
                ds.prior_year.append({
                    "student_ref": s["student_ref"], "school_code": school,
                    "gender": s.pop("_prior_gender", s["gender"]),
                    "class_grade": max(1, int(s["class_grade"]) - 1),
                })

        self._activity(by_school)
        self._staff_and_facilities()
        return ds

    def _pick(self, pool: list[dict], used: set[str]) -> dict:
        while True:
            s = self.rng.choice(pool)
            if s["student_ref"] not in used:
                used.add(s["student_ref"])
                return s

    def _inject_student_problems(self, by_school: dict[str, list[dict]]) -> None:
        used: set[str] = set()
        all_students = [s for code in ACTIVE_SCHOOLS for s in by_school[code]]
        pick = lambda pool=all_students: self._pick(pool, used)  # noqa: E731

        # STU-001: name missing or malformed (register shows the same bad value)
        for bad, note in [("R4hul Sharma", "digit inside name"), ("Priya@ Nair", "stray symbol"),
                          ("", "name missing")]:
            s = pick()
            s["name"] = bad
            s["_register_name"] = bad
            self.inject("STU-001", s, note)

        # STU-002: DOB missing, unparseable, or out of age band
        s = pick(); s["dob"] = ""; self.inject("STU-002", s, "dob missing")
        s = pick(); s["dob"] = "31/02/2015"; self.inject("STU-002", s, "impossible date 31 Feb")
        s = pick(); s["dob"] = "2013-13-05"; self.inject("STU-002", s, "unparseable format")
        s = pick(); s["class_grade"] = 8; s["dob"] = fmt(date(2023, 6, 14))
        self.inject("STU-002", s, "age 3 in class 8 (outside age band)")

        # STU-003: gender missing or inconsistent with prior-year record
        s = pick(); s["_prior_gender"] = s["gender"]; s["gender"] = ""
        self.inject("STU-003", s, "gender missing")
        for _ in range(2):
            s = pick()
            s["_prior_gender"] = "M" if s["gender"] == "F" else "F"
            self.inject("STU-003", s, f"gender {s['gender']} vs prior year {s['_prior_gender']}")

        # STU-004: Aadhaar missing or update pending
        s = pick(); s["aadhaar"] = ""; s["aadhaar_status"] = "missing"
        self.inject("STU-004", s, "aadhaar missing")
        for _ in range(2):
            s = pick(); s["aadhaar_status"] = "update_pending"
            self.inject("STU-004", s, "aadhaar marked update pending")

        # STU-005: spelling mismatch family (two siblings, same guardian, register uses middle initial)
        sib_pool = by_school["SYN-0002"]
        a = self._pick(sib_pool, used); b = self._pick(sib_pool, used)
        guardian = "Ramesh Kumar"
        a.update(name="Ananya Kumar", gender="F", guardian_name=guardian)
        b.update(name="Arjun Kumar", gender="M", guardian_name=guardian)
        a["_register_name"] = "Ananya R. Kumar"
        b["_register_name"] = "Arjun R. Kumar"
        self.inject("STU-005", a, "register says 'Ananya R. Kumar'")
        self.inject("STU-005", b, "register says 'Arjun R. Kumar'")

        # STU-006: the same student entered twice in one school
        pool = by_school["SYN-0003"]
        orig = self._pick(pool, used)
        dup = dict(orig)
        dup["student_ref"] = f"SYN-0003-S{len(pool) + 1:04d}"
        dup["admission_no"] = self.next_admission_no("SYN-0003")
        pool.append(dup)
        used.add(dup["student_ref"])
        self.inject("STU-006", orig, f"duplicate of {dup['student_ref']} (same ID, name, DOB)")
        self.inject("STU-006", dup, f"duplicate of {orig['student_ref']}")

        # STU-007: two students enrolled in two schools (same ID, name written differently)
        for src_code, dst_code, variant in [("SYN-0001", "SYN-0002", lambda n: n.split()[0] + " " + n.split()[1][0] + "."),
                                            ("SYN-0002", "SYN-0003", lambda n: n.upper())]:
            src = self._pick(by_school[src_code], used)
            dst_pool = by_school[dst_code]
            copy = dict(src)
            copy.update(
                student_ref=f"{dst_code}-S{len(dst_pool) + 1:04d}",
                school_code=dst_code,
                admission_no=self.next_admission_no(dst_code),
                name=variant(src["name"]),
                section=self.rng.choice(["A", "B"]),
            )
            dst_pool.append(copy)
            used.add(copy["student_ref"])
            self.inject("STU-007", src, f"also enrolled at {dst_code} as {copy['student_ref']}")
            self.inject("STU-007", copy, f"also enrolled at {src_code} as {src['student_ref']}")

        # STU-008: marked dropout but recent activity -> must be HELD, never applied
        for kind in ["attendance", "attendance", "fee"]:
            s = pick()
            s["enrolment_status"] = "dropout"
            s["_recent_activity"] = kind
            self.inject("STU-008", s, f"marked dropout but recent {kind} record")
        # Genuine dropouts with no recent activity (should NOT be flagged)
        for _ in range(3):
            s = pick()
            s["enrolment_status"] = "dropout"
            s["_recent_activity"] = "none"

        # SYS-001: students moved from merged school SYN-0004 into SYN-0001
        main = by_school["SYN-0001"]
        for i in range(4):
            s = self._pick(main, used)
            s["previous_school_code"] = "SYN-0004"
            s["transfer_status"] = "transferred_in"
            if i == 0:
                s["transfer_status"] = ""
                self.inject("SYS-001", s, "came from merged SYN-0004 with no transfer status")

    def _activity(self, by_school: dict[str, list[dict]]) -> None:
        recent = school_days(REFERENCE_DATE, 15)
        old = school_days(date(2026, 7, 31), 10)
        for code in ACTIVE_SCHOOLS:
            for s in by_school[code]:
                ref = s["student_ref"]
                act = s.pop("_recent_activity", None)
                if s["enrolment_status"] == "dropout" and act in ("none", "fee"):
                    days = old
                else:
                    days = recent
                for d in days:
                    self.ds.attendance.append({
                        "student_ref": ref, "school_code": code, "date": fmt(d),
                        "present": int(self.rng.random() < 0.92),
                    })
                if act == "fee":
                    self.ds.fees.append({"student_ref": ref, "school_code": code,
                                         "date": fmt(date(2026, 11, 5)), "amount": 250})
                elif act != "none" and self.rng.random() < 0.3:
                    self.ds.fees.append({"student_ref": ref, "school_code": code,
                                         "date": fmt(date(2026, 8, self.rng.randint(1, 28))), "amount": 250})

    def _staff_and_facilities(self) -> None:
        ds = self.ds
        for code in ACTIVE_SCHOOLS:
            for t in range(8):
                ref = f"{code}-T{t + 1:02d}"
                gender = self.rng.choice(["M", "F"])
                main_subject = SUBJECTS[t % len(SUBJECTS)]
                extra = self.rng.choice([s for s in SUBJECTS if s != main_subject])
                subjects = [main_subject] if self.rng.random() < 0.5 else [main_subject, extra]
                ds.teachers.append({"teacher_ref": ref, "school_code": code,
                                    "name": self.person_name(gender), "subjects": ";".join(subjects)})
                for _ in range(2):
                    ds.teacher_assignments.append({
                        "teacher_ref": ref, "school_code": code,
                        "class_grade": self.rng.randint(1, 10), "section": self.rng.choice(["A", "B"]),
                        "subject": self.rng.choice(subjects),
                    })
            for f_type in FACILITY_TYPES:
                ref = f"{code}-F-{f_type}"
                functional = self.rng.random() < 0.85
                ds.facilities.append({"facility_ref": ref, "school_code": code, "facility_type": f_type,
                                      "status": "functional" if functional else "non_functional"})
                ds.maintenance_log.append({"facility_ref": ref, "school_code": code,
                                           "date": fmt(date(2026, 9, self.rng.randint(1, 28))),
                                           "condition": "working" if functional else "broken",
                                           "note": "routine inspection"})

        # TCH-001: Mathematics-only teacher assigned to teach Hindi
        # (teacher T01 always has Mathematics as main subject; narrow them to Mathematics only)
        t = next(x for x in ds.teachers if x["teacher_ref"] == "SYN-0002-T01")
        t["subjects"] = "Mathematics"
        for a in ds.teacher_assignments:
            if a["teacher_ref"] == t["teacher_ref"]:
                a["subject"] = "Mathematics"
        ds.teacher_assignments.append({"teacher_ref": t["teacher_ref"], "school_code": "SYN-0002",
                                       "class_grade": 7, "section": "A", "subject": "Hindi"})
        ds.injected.append(Injection("TCH-001", "teacher", "SYN-0002", t["teacher_ref"],
                                     "qualified in Mathematics, assigned Hindi for class 7A"))

        # FAC-001: girls' toilet marked functional, latest maintenance entry says broken
        ref = "SYN-0002-F-toilet_girls"
        for f in ds.facilities:
            if f["facility_ref"] == ref:
                f["status"] = "functional"
        for m in ds.maintenance_log:
            if m["facility_ref"] == ref:
                m["condition"] = "working"
        ds.maintenance_log.append({"facility_ref": ref, "school_code": "SYN-0002",
                                   "date": fmt(date(2026, 11, 3)), "condition": "broken",
                                   "note": "door latch and flush broken, awaiting repair"})
        ds.injected.append(Injection("FAC-001", "facility", "SYN-0002", ref,
                                     "marked functional, maintenance log on 03/11/2026 says broken"))


def write_csv(path: Path, rows: list[dict], columns: list[str] | None = None) -> None:
    columns = columns or (list(rows[0].keys()) if rows else [])
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# Headings as a school's own spreadsheet might have them, for the upload screen's column mapping.
EXPORT_HEADINGS = {
    "student_ref": "Student ID", "school_code": "School Code", "admission_no": "Admission No",
    "name": "Student Name", "dob": "Date of Birth", "gender": "Gender", "class_grade": "Class",
    "section": "Section", "guardian_name": "Guardian Name", "aadhaar": "Aadhaar No",
    "aadhaar_status": "Aadhaar Status", "enrolment_status": "Enrolment Status",
    "previous_school_code": "Previous School", "transfer_status": "Transfer Status",
}
DEFAULT_OUT = Path(__file__).resolve().parent / "data"
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "frontend" / "public" / "samples"


def write_samples(ds: Dataset, out: Path = SAMPLES_DIR) -> None:
    """The "Load sample messy file" demo uploads: each open school's raw export (synthetic IDs,
    as the school's own file would have them), with spreadsheet-style headings and a Remarks
    column that maps to nothing. Same values as students.csv, so an import changes no data."""
    out.mkdir(parents=True, exist_ok=True)
    open_codes = [s["code"] for s in ds.schools if s["status"] == "open"]
    for code in open_codes:
        rows = []
        for i, st in enumerate(r for r in ds.students if r["school_code"] == code):
            row = {EXPORT_HEADINGS[c]: st.get(c, "") for c in STUDENT_COLUMNS}
            row["Remarks"] = "fee concession" if i % 17 == 5 else ""
            rows.append(row)
        write_csv(out / f"school_export_{code}.csv", rows, [*EXPORT_HEADINGS.values(), "Remarks"])


def generate(seed: int = DEFAULT_SEED, per_school: int = 60) -> Dataset:
    return Generator(seed, per_school).build()


def write_dataset(ds: Dataset, out: Path, seed: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "schools.csv", ds.schools)
    write_csv(out / "students.csv", ds.students, STUDENT_COLUMNS)
    write_csv(out / "admission_register.csv", ds.admission_register)
    write_csv(out / "prior_year.csv", ds.prior_year)
    write_csv(out / "teachers.csv", ds.teachers)
    write_csv(out / "teacher_assignments.csv", ds.teacher_assignments)
    write_csv(out / "facilities.csv", ds.facilities)
    write_csv(out / "maintenance_log.csv", ds.maintenance_log)
    write_csv(out / "attendance.csv", ds.attendance)
    write_csv(out / "fees.csv", ds.fees, ["student_ref", "school_code", "date", "amount"])
    (out / "injected.json").write_text(json.dumps({
        "synthetic": True,
        "seed": seed,
        "reference_date": REFERENCE_DATE.isoformat(),
        "academic_year": ACADEMIC_YEAR,
        "students_total": len(ds.students),
        "injected": [asdict(i) for i in ds.injected],
    }, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic Rsafe data (all fake).")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--per-school", type=int, default=60)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--no-db", action="store_true", help="only write CSVs, do not rebuild rsafe.db")
    args = parser.parse_args()

    ds = generate(args.seed, args.per_school)
    write_dataset(ds, args.out, args.seed)
    if args.out == DEFAULT_OUT:
        write_samples(ds)
    if not args.no_db:
        from app.db import engine
        from app.services.loader import seed_and_validate

        result = seed_and_validate(args.out, engine)
        print(f"Database rebuilt ({engine.url.database}): "
              + ", ".join(f"{k} {v}" for k, v in result["counts"].items()))
        print("  stored per student: two keyed tokens + last 4 digits. No raw Aadhaar.")
        for sch in result["validation"]["schools"]:
            print(f"  {sch['school_code']}: readiness {sch['readiness']}%, {sch['active']} active issues "
                  f"({sch['held']} held)")
    affected = len({i.ref for i in ds.injected if i.entity == "student"})
    print(f"Synthetic data written to {args.out}")
    print(f"  schools: {len(ds.schools)}  students: {len(ds.students)}  teachers: {len(ds.teachers)}  "
          f"facilities: {len(ds.facilities)}")
    print(f"  injected problems: {len(ds.injected)} "
          f"({affected} student records, {affected / len(ds.students):.1%} of students)")


if __name__ == "__main__":
    main()
