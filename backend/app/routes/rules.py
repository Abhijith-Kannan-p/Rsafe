"""Read-only rule listing. Any signed-in role may read rules (to explain a flag); only the
Admin screen lists them all. Rules can't be changed through the API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import Identity, current_identity

router = APIRouter(prefix="/api/rules", tags=["rules"])


def _summary(rule) -> dict:
    return rule.model_dump(exclude={"source"})


@router.get("")
def list_rules(request: Request, _: Identity = Depends(current_identity)) -> list[dict]:
    return [_summary(r) for r in request.app.state.rules]


@router.get("/{rule_id}")
def get_rule(rule_id: str, request: Request, _: Identity = Depends(current_identity)) -> dict:
    for r in request.app.state.rules:
        if r.id == rule_id:
            return _summary(r) | {"source": r.source}
    raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
