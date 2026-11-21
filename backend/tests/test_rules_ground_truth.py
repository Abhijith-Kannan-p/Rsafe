"""Run every rule over the seeded dataset and compare with what seed.py injected.

Precision and recall must both be 100% for every rule: each injected problem is caught,
and no clean record is flagged.
"""

import json
import re
from datetime import date

import pytest

import seed
from app.services.engine import readiness_score, run_rules
from app.services.ingest import load_dataset
from app.services.rules import load_rules

ALL_RULES = ["STU-001", "STU-002", "STU-003", "STU-004", "STU-005", "STU-006", "STU-007", "STU-008",
             "TCH-001", "FAC-001", "SYS-001"]


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    out = tmp_path_factory.mktemp("seed")
    seed.write_dataset(seed.generate(), out, seed.DEFAULT_SEED)
    data, ctx = load_dataset(out, today=seed.REFERENCE_DATE, academic_year_start=2026)
    injected = json.loads((out / "injected.json").read_text())["injected"]
    return data, ctx, injected


@pytest.fixture(scope="module")
def issues(dataset):
    data, ctx, _ = dataset
    return run_rules(load_rules(), data, ctx)


def test_every_rule_is_loaded():
    assert sorted(r.id for r in load_rules()) == sorted(ALL_RULES)


@pytest.mark.parametrize("rule_id", ALL_RULES)
def test_flags_match_injected_exactly(rule_id, dataset, issues):
    _, _, injected = dataset
    expected = {i["ref"] for i in injected if i["rule"] == rule_id}
    found = {i.entity_ref for i in issues if i.rule_id == rule_id}
    assert expected, f"seed injects nothing for {rule_id}"
    assert found == expected, f"missed={expected - found} false_positives={found - expected}"


def test_only_dropout_issues_are_held(issues):
    held = {i.rule_id for i in issues if i.held}
    assert held == {"STU-008"}
    assert sum(i.held for i in issues) == 3


def test_cross_school_match_ignores_names(dataset, issues):
    data, _, _ = dataset
    names = {r["student_ref"]: r["name"] for r in data["student"]}
    for i in (x for x in issues if x.rule_id == "STU-007"):
        other = i.evidence["matches"][0]["student_ref"]
        assert names[i.entity_ref] != names[other]  # seed writes the name differently in each school
        assert names[other] not in json.dumps(i.to_dict())  # the other school's name is never shown
        assert len(i.evidence["token"]) == 6 and len(i.evidence["schools"]) == 2


def test_rule_versions_are_stamped(issues):
    assert all(i.rule_version == "1.0.0" for i in issues)


def test_no_twelve_digit_number_in_issues(issues):
    blob = json.dumps([i.to_dict() for i in issues])
    assert not re.search(r"\d{12}", blob)


def test_issue_ordering_and_score(dataset, issues):
    data, _, _ = dataset
    ranks = [{"high": 0, "medium": 1, "low": 2}[i.severity] for i in issues]
    assert ranks == sorted(ranks)
    student_issues = [i for i in issues if i.entity == "student"]
    assert 60 <= readiness_score(len(data["student"]), student_issues) < 100


def test_context_today_is_fixed(dataset):
    _, ctx, _ = dataset
    assert ctx.today == date(2026, 11, 16)
