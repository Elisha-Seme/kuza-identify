"""SQLAlchemy engine, session factory, and declarative base.

The engine is configured to work in three environments unchanged:
  * local docker / dev  -> a normal pooled engine
  * serverless (Vercel) against a connection-pooled Postgres (Neon/Supabase
    pooler) -> NullPool + prepared statements disabled, which is what pgbouncer
    transaction-mode pooling requires.

DATABASE_URL is accepted in the plain `postgresql://…` form providers hand out
and normalised to the psycopg driver here, so the value can be pasted verbatim.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()


def _normalise_url(url: str) -> str:
    # Providers give `postgresql://…`; SQLAlchemy needs the driver name.
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url


_url = _normalise_url(settings.database_url)

# A pooled/serverless connection (pgbouncer transaction mode) can't reuse
# server-side prepared statements or hold a long-lived pool.
_is_pooled = "pooler." in _url or settings.serverless

if _is_pooled:
    engine = create_engine(
        _url,
        poolclass=NullPool,
        connect_args={"prepare_threshold": None},
        future=True,
    )
else:
    engine = create_engine(_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for every ORM model."""


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
