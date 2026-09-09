"""Alembic upgrade succeeds on a clean SQLite database and creates core tables."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from database import run_migrations


ROOT = Path(__file__).resolve().parents[1]


def test_alembic_upgrade_head_creates_core_tables(tmp_path):
    db_path = tmp_path / "migrate.db"
    url = f"sqlite:///{db_path.as_posix()}"

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.attributes["database_url"] = url

    command.upgrade(cfg, "head")

    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "alembic_version" in tables
        assert "users" in tables
        assert "jobs" in tables
        assert "book_indexes" in tables
        assert "subscriptions" in tables
        assert "credit_transactions" in tables
        assert "stripe_events" in tables
        assert "campaigns" in tables
        assert "campaign_characters" in tables

        job_cols = {c["name"] for c in inspect(engine).get_columns("jobs")}
        assert "use_character_sheets" in job_cols
        assert "party_size" in job_cols
        assert "character_sheets" in job_cols
        assert "blueprint_json" in job_cols
        assert "book_id" in job_cols
    finally:
        engine.dispose()


def test_run_migrations_stamps_legacy_schema_without_alembic_version(tmp_path):
    """Legacy DBs created with create_all get stamped, then upgraded for newer revisions."""
    from database import Base
    import models.entities  # noqa: F401

    db_path = tmp_path / "legacy.db"
    url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        # Simulate schema as of baseline only (no blueprint_json / book_id / campaigns)
        conn.exec_driver_sql("DROP TABLE IF EXISTS campaign_characters")
        conn.exec_driver_sql("DROP TABLE IF EXISTS campaigns")
        cols = {c["name"] for c in inspect(engine).get_columns("jobs")}
        keep = [
            "id",
            "user_id",
            "status",
            "complexity",
            "language",
            "filename",
            "s3_key",
            "campaign_s3_key",
            "credits_charged",
            "idempotency_key",
            "share_slug",
            "share_public",
            "system_preset",
            "use_character_sheets",
            "party_size",
            "character_sheets",
            "created_at",
            "completed_at",
        ]
        select_cols = ", ".join(c for c in keep if c in cols)
        conn.exec_driver_sql(f"CREATE TABLE jobs_old AS SELECT {select_cols} FROM jobs")
        conn.exec_driver_sql("DROP TABLE jobs")
        conn.exec_driver_sql("ALTER TABLE jobs_old RENAME TO jobs")
    assert "users" in inspect(engine).get_table_names()
    assert "alembic_version" not in inspect(engine).get_table_names()
    assert "campaigns" not in inspect(engine).get_table_names()
    assert "blueprint_json" not in {c["name"] for c in inspect(engine).get_columns("jobs")}
    engine.dispose()

    run_migrations(url)

    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "alembic_version" in tables
        assert "users" in tables
        assert "campaigns" in tables
        assert "campaign_characters" in tables
        job_cols = {c["name"] for c in inspect(engine).get_columns("jobs")}
        assert "blueprint_json" in job_cols
        assert "book_id" in job_cols
    finally:
        engine.dispose()
