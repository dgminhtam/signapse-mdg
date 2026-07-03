"""Add economic calendar enrichment fields.

Revision ID: 20260703_0014
Revises: 20260701_0013
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260703_0014"
down_revision: str | None = "20260701_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("economic_calendar_events", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("economic_calendar_events", sa.Column("news_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("economic_calendar_events", "news_url")
    op.drop_column("economic_calendar_events", "description")
