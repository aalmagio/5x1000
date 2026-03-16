"""
Connessione al database MySQL via SQLAlchemy (sync).
Fornisce get_db() come dependency FastAPI e query helpers.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from config import settings

engine = create_engine(
    settings.db_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """Dependency FastAPI: fornisce una sessione DB per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context manager per uso fuori da FastAPI (script, etc.)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def fetch_one(db: Session, sql: str, params: dict | None = None) -> dict | None:
    row = db.execute(text(sql), params or {}).mappings().first()
    return dict(row) if row else None


def fetch_all(db: Session, sql: str, params: dict | None = None) -> list[dict]:
    rows = db.execute(text(sql), params or {}).mappings().all()
    return [dict(r) for r in rows]
