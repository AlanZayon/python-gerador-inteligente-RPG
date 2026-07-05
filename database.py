"""SQLAlchemy database setup."""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def _normalize_database_url(url: str) -> str:
    """Railway/Heroku use postgres://; SQLAlchemy 2.x expects postgresql://."""
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


DATABASE_URL = _normalize_database_url(
    os.getenv("DATABASE_URL", "sqlite:///./arcane_forge.db")
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _migrate_jobs_columns():
    """Add character-sheet columns to existing jobs tables (idempotent)."""
    columns = [
        ("use_character_sheets", "BOOLEAN DEFAULT 0"),
        ("party_size", "INTEGER DEFAULT 0"),
        ("character_sheets", "TEXT"),
    ]
    with engine.connect() as conn:
        for name, col_type in columns:
            try:
                conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {name} {col_type}"))
                conn.commit()
            except Exception:
                conn.rollback()


def init_db():
    from models import entities  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_jobs_columns()
