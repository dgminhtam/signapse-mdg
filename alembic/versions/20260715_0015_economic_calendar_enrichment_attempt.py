"""Track economic calendar enrichment attempts.

Revision ID: 20260715_0015
Revises: 20260703_0014
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260715_0015"
down_revision: str | None = "20260703_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "economic_calendar_events",
        sa.Column("enrichment_attempted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("economic_calendar_events", "enrichment_attempted_at")
