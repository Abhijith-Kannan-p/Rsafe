"""Exports for the Principal (own school) and MIS Coordinator (cluster schools). Each export
writes an audit row, so the log shows who took the file and when."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session

from ..auth import Identity, require
from ..config import REFERENCE_DATE
from ..db import get_session
from ..roles import Role
from ..services import audit, scope
from ..services.export import cleaned_csv, report_html

router = APIRouter(prefix="/api/export", tags=["export"])
exporters = require(Role.PRINCIPAL, Role.MIS_COORDINATOR)


def _school(s: Session, who: Identity, school_code: Optional[str]) -> str:
    allowed = scope.visible_schools(s, who)
    code = school_code or (who.school_code if who.role == Role.PRINCIPAL else None)
    if not code:
        raise HTTPException(400, "Choose a school to export.")
    if code not in allowed:
        raise HTTPException(404, "School not found.")
    return code


@router.get("/csv")
def export_csv(school_code: Optional[str] = None, who: Identity = Depends(exporters),
               s: Session = Depends(get_session)) -> Response:
    code = _school(s, who, school_code)
    text, counts = cleaned_csv(s, code)
    audit.append(s, who.actor, who.role.value, "export.csv", f"school:{code}", {"school_code": code, "rows": counts})
    name = f"rsafe_clean_{code}_{REFERENCE_DATE.isoformat()}.csv"
    return Response(text, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/report", response_class=HTMLResponse)
def export_report(request: Request, school_code: Optional[str] = None, who: Identity = Depends(exporters),
                  s: Session = Depends(get_session)) -> HTMLResponse:
    code = _school(s, who, school_code)
    html = report_html(s, code, request.app.state.rules, who.actor)
    audit.append(s, who.actor, who.role.value, "export.report", f"school:{code}", {"school_code": code})
    return HTMLResponse(html)
