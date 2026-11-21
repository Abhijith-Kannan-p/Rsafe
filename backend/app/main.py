"""FastAPI entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import CORS_ORIGINS, SYNTHETIC_NOTICE
from .db import init_db
from .roles import ROLE_LABELS


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Rsafe API", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "synthetic": True}


@app.get("/api/meta")
def meta() -> dict:
    return {
        "name": "Rsafe",
        "version": __version__,
        "notice": SYNTHETIC_NOTICE,
        "roles": [{"id": r.value, "label": label} for r, label in ROLE_LABELS.items()],
    }
