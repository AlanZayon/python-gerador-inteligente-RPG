"""SQLAlchemy database setup and Alembic-backed init."""

import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
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


def _alembic_config(url: str | None = None):
    from alembic.config import Config

    root = Path(__file__).resolve().parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    target = url or DATABASE_URL
    cfg.set_main_option("sqlalchemy.url", target)
    cfg.attributes["database_url"] = target
    return cfg


def run_migrations(url: str | None = None) -> None:
    """Apply Alembic migrations to head.

    If the database already has the legacy schema (created via create_all)
    but no alembic_version row, stamp to head instead of recreating tables.
    """
    from alembic import command

    target_url = url or DATABASE_URL
    cfg = _alembic_config(target_url)

    target_engine = create_engine(
        target_url,
        connect_args={"check_same_thread": False} if target_url.startswith("sqlite") else {},
    )
    try:
        tables = set(inspect(target_engine).get_table_names())
        if "users" in tables and "alembic_version" not in tables:
            # Legacy create_all DB: mark baseline applied, then upgrade for newer revisions.
            command.stamp(cfg, "0001_baseline")
        command.upgrade(cfg, "head")
    finally:
        target_engine.dispose()


def init_db():
    """Ensure schema is at Alembic head. Prefer migrations over create_all."""
    import models.entities  # noqa: F401

    run_migrations()
