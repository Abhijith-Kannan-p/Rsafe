"""Run the core rules over the seeded dataset and compare with what seed.py injected.

Precision and recall must both be 100% for STU-001 to STU-004: every injected problem is
caught, and no clean record is flagged.
"""

import json
import re
from datetime import date

import pytest

import seed
from app.services.engine import readiness_score, run_rules
from app.services.ingest import load_dataset
from app.services.rules import load_rules

CORE = ("STU-001", "STU-002", "STU-003", "STU-004")


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
    rules = [r for r in load_rules() if r.id in CORE]
    return run_rules(rules, data, ctx)


@pytest.mark.parametrize("rule_id", CORE)
def test_flags_match_injected_exactly(rule_id, dataset, issues):
    _, _, injected = dataset
    expected = {i["ref"] for i in injected if i["rule"] == rule_id}
    found = {i.entity_ref for i in issues if i.rule_id == rule_id}
    assert found == expected, f"missed={expected - found} false_positives={found - expected}"


def test_ingest_drops_raw_ids(dataset):
    data, _, _ = dataset
    for rec in data["student"]:
        assert "aadhaar" not in rec
        assert rec["aadhaar_last4"] is None or re.fullmatch(r"\d{4}", rec["aadhaar_last4"])


def test_no_twelve_digit_number_in_issues(issues):
    blob = json.dumps([i.to_dict() for i in issues])
    assert not re.search(r"\d{12}", blob)


def test_issue_ordering_and_score(dataset, issues):
    data, _, _ = dataset
    ranks = [{"high": 0, "medium": 1, "low": 2}[i.severity] for i in issues]
    assert ranks == sorted(ranks)
    score = readiness_score(len(data["student"]), issues)
    assert 80 <= score < 100


def test_context_today_is_fixed(dataset):
    _, ctx, _ = dataset
    assert ctx.today == date(2026, 11, 16)
