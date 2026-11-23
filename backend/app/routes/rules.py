"""Read-only rule listing. Any signed-in role may read rules (to explain a flag); only the
Admin screen lists them all. Rules can't be changed through the API."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import Identity, current_identity
from ..config import RULES_DIR

I18N = RULES_DIR / "i18n.json"

router = APIRouter(prefix="/api/rules", tags=["rules"])


def _summary(rule) -> dict:
    return rule.model_dump(exclude={"source"})


@router.get("")
def list_rules(request: Request, _: Identity = Depends(current_identity)) -> list[dict]:
    return [_summary(r) for r in request.app.state.rules]


@router.get("/i18n")
def rule_translations(_: Identity = Depends(current_identity)) -> dict:
    """Rule reasons in English, Hindi and Malayalam (the last two flagged as machine translations)."""
    return json.loads(I18N.read_text(encoding="utf-8"))


@router.get("/{rule_id}")
def get_rule(rule_id: str, request: Request, _: Identity = Depends(current_identity)) -> dict:
    for r in request.app.state.rules:
        if r.id == rule_id:
            return _summary(r) | {"source": r.source}
    raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
