"""Database URL normalization tests."""

from database import _normalize_database_url


def test_postgres_url_normalized():
    assert _normalize_database_url("postgres://user:pass@host/db") == (
        "postgresql://user:pass@host/db"
    )


def test_postgresql_url_unchanged():
    url = "postgresql://user:pass@host/db"
    assert _normalize_database_url(url) == url
