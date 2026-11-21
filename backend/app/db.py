"""Engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from . import models  # noqa: F401  (registers tables on SQLModel.metadata)
from .config import DATABASE_URL


def make_engine(url: str = DATABASE_URL) -> Engine:
    if not url.startswith("sqlite"):
        return create_engine(url)
    kwargs: dict = {"connect_args": {"check_same_thread": False}}
    if url in ("sqlite://", "sqlite:///:memory:"):
        kwargs["poolclass"] = StaticPool  # one shared in-memory DB across threads (tests)
    return create_engine(url, **kwargs)


engine = make_engine()


def init_db(target: Engine | None = None) -> None:
    SQLModel.metadata.create_all(target or engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
