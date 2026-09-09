# 02: Alembic + tracked domain models

**What to build:** Schema evolution uses Alembic. Domain ORM models are versioned in git so a fresh clone can migrate and boot. New play tables will be added via migrations from here on—not ad-hoc `create_all` / manual `ALTER`.

**Blocked by:** 01 — Strip monetization

**Status:** resolved

- [x] Alembic is wired for the existing database URL (SQLite and Postgres-compatible)
- [x] Current schema is captured as a baseline migration (or equivalent bootstrap)
- [x] Domain models are tracked in version control (no longer ignore-only local artifacts)
- [x] `alembic upgrade head` succeeds on a clean database in CI/local
- [x] Ad-hoc job column migration path is superseded or clearly retired for new changes
