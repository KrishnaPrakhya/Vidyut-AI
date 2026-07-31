from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from services.persistence.models import Base

DATABASE_URL_ENV_VAR = "DATABASE_URL"
CONNECT_TIMEOUT_SECONDS = 5


@dataclass
class DatabaseStatus:
    configured: bool
    reachable: bool
    url_host: str | None = None
    error: str | None = None

    @property
    def status(self) -> str:
        if not self.configured:
            return "not_configured"
        return "connected" if self.reachable else "unreachable"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "configured": self.configured,
            "reachable": self.reachable,
            "host": self.url_host,
            "error": self.error,
        }


def database_url() -> str | None:
    url = os.environ.get(DATABASE_URL_ENV_VAR, "").strip()
    return url or None


@lru_cache(maxsize=1)
def _engine_for(url: str) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


def get_engine() -> Engine | None:
    url = database_url()
    if url is None:
        return None
    return _engine_for(url)


def check() -> DatabaseStatus:
    url = database_url()
    if url is None:
        return DatabaseStatus(configured=False, reachable=False)

    host = url.rsplit("@", 1)[-1] if "@" in url else url
    try:
        engine = _engine_for(url)
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        return DatabaseStatus(configured=True, reachable=True, url_host=host)
    except SQLAlchemyError as exc:
        return DatabaseStatus(
            configured=True, reachable=False, url_host=host, error=str(exc.__cause__ or exc)
        )


def create_schema() -> DatabaseStatus:
    status = check()
    if not status.reachable:
        return status
    engine = get_engine()
    assert engine is not None
    Base.metadata.create_all(engine)
    return status


@contextmanager
def session_scope() -> Iterator[Session | None]:
    engine = get_engine()
    if engine is None:
        yield None
        return

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
