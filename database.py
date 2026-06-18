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


def init_db():
    from models import entities  # noqa: F401

    Base.metadata.create_all(bind=engine)
