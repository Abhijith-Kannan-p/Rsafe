"""YAML rule loader.

One file per rule in backend/rules/. Each file is validated against RuleSpec, and the
named `check` must exist in the check registry. Any problem stops loading with an
error that names the file, so a broken rule can never be silently skipped.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..config import RULES_DIR

Severity = Literal["high", "medium", "low"]
Entity = Literal["student", "teacher", "facility"]
Scope = Literal["record", "dataset"]

SEVERITY_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2}


class RuleLoadError(Exception):
    pass


class RuleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^(STU|TCH|FAC|SYS)-\d{3}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    title: str = Field(min_length=3)
    severity: Severity
    entity: Entity
    scope: Scope = "record"  # record: one record at a time; dataset: sees all records (duplicates)
    check: str
    message: str = Field(min_length=3)  # plain language, shown to the school
    fix: str = Field(min_length=3)  # suggested action
    addresses: str | None = None  # the government-reported failure reason this rule targets
    hold: bool = False  # True: issues start as "held" and the flagged change is NOT applied until reviewed
    params: dict[str, Any] = Field(default_factory=dict)
    source: str = ""  # raw YAML, kept for the read-only Rules screen

    @field_validator("message", "fix", "title")
    @classmethod
    def _strip(cls, v: str) -> str:
        return " ".join(v.split())


def load_rule_file(path: Path, known_checks: set[str] | None = None) -> RuleSpec:
    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RuleLoadError(f"{path.name}: invalid YAML ({exc})") from exc
    if not isinstance(data, dict):
        raise RuleLoadError(f"{path.name}: expected a mapping at the top level")
    try:
        rule = RuleSpec(**data, source=text)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise RuleLoadError(f"{path.name}: {problems}") from exc
    if path.stem != rule.id:
        raise RuleLoadError(f"{path.name}: file name must match rule id {rule.id}")
    if known_checks is not None and rule.check not in known_checks:
        raise RuleLoadError(f"{path.name}: unknown check '{rule.check}'")
    return rule


def load_rules(directory: Path = RULES_DIR) -> list[RuleSpec]:
    from .checks import REGISTRY  # local import: checks imports nothing from here at load time

    known = set(REGISTRY)
    rules: list[RuleSpec] = []
    seen: dict[str, str] = {}
    for path in sorted(directory.glob("*.yaml")):
        rule = load_rule_file(path, known)
        if rule.id in seen:
            raise RuleLoadError(f"{path.name}: duplicate rule id {rule.id} (also in {seen[rule.id]})")
        seen[rule.id] = path.name
        scope_kind = REGISTRY[rule.check].scope
        if scope_kind != rule.scope:
            raise RuleLoadError(f"{path.name}: check '{rule.check}' is a {scope_kind} check, rule says {rule.scope}")
        rules.append(rule)
    if not rules:
        raise RuleLoadError(f"no rules found in {directory}")
    return rules
