"""Read-only rule listing. Role restriction (Admin) is added in Phase 4."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/rules", tags=["rules"])


def _summary(rule) -> dict:
    return rule.model_dump(exclude={"source"})


@router.get("")
def list_rules(request: Request) -> list[dict]:
    return [_summary(r) for r in request.app.state.rules]


@router.get("/{rule_id}")
def get_rule(rule_id: str, request: Request) -> dict:
    for r in request.app.state.rules:
        if r.id == rule_id:
            return _summary(r) | {"source": r.source}
    raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
