"""Upload a school's student CSV: preview (no writes), then commit (replaces that school's
students, writes an audit row and re-validates). Principal only."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..auth import Identity, require
from ..db import get_session
from ..roles import Role
from ..services import upload

router = APIRouter(prefix="/api/upload", tags=["upload"])
principal = require(Role.PRINCIPAL)


class UploadBody(BaseModel):
    csv: str = Field(max_length=upload.MAX_BYTES)
    mapping: Optional[dict[str, str]] = None
    filename: str = Field(default="upload.csv", max_length=200)


@router.get("/fields")
def fields(_: Identity = Depends(principal)) -> list[dict]:
    return [{"field": f.field, "label": f.label, "required": f.required} for f in upload.FIELDS]


@router.post("/preview")
def preview(body: UploadBody, who: Identity = Depends(principal)) -> dict:
    return upload.preview(body.csv, who.school_code or "", body.mapping)


@router.post("/commit")
def commit(body: UploadBody, request: Request, who: Identity = Depends(principal),
           s: Session = Depends(get_session)) -> dict:
    return upload.commit(s, request.app.state.rules, who, body.csv, body.mapping, body.filename)
