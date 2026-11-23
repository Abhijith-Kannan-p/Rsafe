"""FastAPI entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect

from . import __version__
from .config import CORS_ORIGINS, SYNTHETIC_NOTICE
from .db import engine, init_db
from .models import SQLModel
from .roles import ROLE_LABELS
from .routes import audit as audit_routes
from .routes import export as export_routes
from .routes import issues as issue_routes
from .routes import rules as rules_routes
from .routes import session as session_routes
from .routes import upload as upload_routes
from .routes import views as view_routes
from .services.rules import load_rules


def check_schema() -> None:
    """Fail fast with a clear hint if rsafe.db was built by an older version."""
    insp = inspect(engine)
    for table in SQLModel.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        have = {c["name"] for c in insp.get_columns(table.name)}
        missing = set(table.columns.keys()) - have
        if missing:
            raise RuntimeError(
                f"Database schema is out of date (table {table.name} lacks {sorted(missing)}). "
                "Run `npm run seed` to rebuild it."
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_schema()
    init_db()
    # A malformed rule raises RuleLoadError here and stops startup: no silent skips.
    app.state.rules = load_rules()
    yield


app = FastAPI(title="Rsafe API", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session_routes.router)
app.include_router(issue_routes.router)
app.include_router(audit_routes.router)
app.include_router(rules_routes.router)
app.include_router(upload_routes.router)
app.include_router(export_routes.router)
app.include_router(view_routes.router)


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
