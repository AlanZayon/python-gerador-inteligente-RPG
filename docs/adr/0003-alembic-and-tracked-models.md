# Alembic and tracked domain models

All schema changes go through Alembic. Domain ORM models must be versioned in git (stop treating `models/` as ignore-only local artifacts). Ad-hoc `create_all` + manual `ALTER` is insufficient once Campaign, GameSession, events, and memory exist and need reviewable roll-forward/roll-back.
