"""Add campaigns, campaign_characters, and jobs.book_id

Revision ID: 0003_campaigns
Revises: 0002_job_blueprint
Create Date: 2026-09-09
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_campaigns"
down_revision: Union[str, None] = "0002_job_blueprint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("book_id", sa.String(length=64), nullable=True))
        batch_op.create_index("ix_jobs_book_id", ["book_id"])

    op.create_table(
        "campaigns",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("job_id", sa.String(length=36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("host_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("blueprint_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("manuscript_s3_key", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ready"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_campaigns_job_id", "campaigns", ["job_id"], unique=True)
    op.create_index("ix_campaigns_host_user_id", "campaigns", ["host_user_id"])
    op.create_index("ix_campaigns_book_id", "campaigns", ["book_id"])

    op.create_table(
        "campaign_characters",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "campaign_id",
            sa.String(length=36),
            sa.ForeignKey("campaigns.id"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("sheet_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claimable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_campaign_characters_campaign_id", "campaign_characters", ["campaign_id"])


def downgrade() -> None:
    op.drop_table("campaign_characters")
    op.drop_table("campaigns")
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_index("ix_jobs_book_id")
        batch_op.drop_column("book_id")
