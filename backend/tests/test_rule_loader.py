"""YAML loader: real rules load; malformed rules fail loudly with the file name."""

import textwrap

import pytest

from app.services.rules import RuleLoadError, load_rule_file, load_rules

GOOD = """
id: STU-001
version: "1.0.0"
title: Test rule
severity: high
entity: student
check: name_wellformed
message: Something is wrong.
fix: Fix it.
"""


def write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return p


def test_real_rules_load():
    rules = load_rules()
    ids = [r.id for r in rules]
    assert {"STU-001", "STU-002", "STU-003", "STU-004"} <= set(ids)
    assert len(ids) == len(set(ids))
    for r in rules:
        assert r.version.count(".") == 2
        assert r.source.startswith("id:")
        assert r.addresses  # every rule names the failure reason it targets


def test_params_reach_the_rule():
    stu002 = next(r for r in load_rules() if r.id == "STU-002")
    assert stu002.params == {"min_offset": 4, "max_offset": 8}


def test_good_file_loads(tmp_path):
    rule = load_rule_file(write(tmp_path, "STU-001.yaml", GOOD), {"name_wellformed"})
    assert rule.message == "Something is wrong."


@pytest.mark.parametrize(
    "mutation, expected",
    [
        (("severity: high", "severity: critical"), "severity"),
        (("entity: student", "entity: bus"), "entity"),
        (('version: "1.0.0"', "version: one"), "version"),
        (("check: name_wellformed", "check: does_not_exist"), "unknown check"),
        (("fix: Fix it.", "fix: Fix it.\nsurprise: 1"), "surprise"),
        (("message: Something is wrong.", ""), "message"),
    ],
)
def test_bad_files_are_rejected(tmp_path, mutation, expected):
    text = GOOD.replace(*mutation)
    with pytest.raises(RuleLoadError) as exc:
        load_rule_file(write(tmp_path, "STU-001.yaml", text), {"name_wellformed"})
    assert "STU-001.yaml" in str(exc.value)
    assert expected in str(exc.value)


def test_invalid_yaml_rejected(tmp_path):
    with pytest.raises(RuleLoadError, match="invalid YAML"):
        load_rule_file(write(tmp_path, "STU-001.yaml", "id: [unclosed"), set())


def test_file_name_must_match_id(tmp_path):
    with pytest.raises(RuleLoadError, match="must match"):
        load_rule_file(write(tmp_path, "STU-009.yaml", GOOD), {"name_wellformed"})


def test_second_file_cannot_reuse_an_id(tmp_path):
    # File names must equal ids, so a copy of STU-001 under another name is rejected.
    write(tmp_path, "STU-001.yaml", GOOD)
    write(tmp_path, "STU-002.yaml", GOOD)
    with pytest.raises(RuleLoadError, match="STU-002.yaml: file name must match rule id STU-001"):
        load_rules(tmp_path)


def test_scope_mismatch_rejected(tmp_path):
    write(tmp_path, "STU-001.yaml", GOOD + "scope: dataset\n")
    with pytest.raises(RuleLoadError, match="is a record check"):
        load_rules(tmp_path)


def test_empty_directory_rejected(tmp_path):
    with pytest.raises(RuleLoadError, match="no rules"):
        load_rules(tmp_path)


def test_rules_api_needs_a_session(client):
    assert client.get("/api/rules").status_code == 401


def test_rules_api(client, seeded_db):
    client.post("/api/session", json={"role": "teacher"})
    rules = client.get("/api/rules").json()
    assert {r["id"] for r in rules} >= {"STU-001", "STU-002", "STU-003", "STU-004"}
    assert "source" not in rules[0]
    one = client.get("/api/rules/STU-002").json()
    assert one["version"] == "1.0.0" and "min_offset" in one["source"]
    assert client.get("/api/rules/STU-999").status_code == 404
