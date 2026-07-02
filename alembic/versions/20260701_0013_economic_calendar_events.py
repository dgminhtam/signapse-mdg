"""Create economic calendar event persistence.

Revision ID: 20260701_0013
Revises: 20260630_0012
Create Date: 2026-07-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260701_0013"
down_revision: str | None = "20260630_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "economic_calendar_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("calendar_type", sa.Text(), nullable=False),
        sa.Column("external_event_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("impact", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual", sa.Text(), nullable=True),
        sa.Column("forecast", sa.Text(), nullable=True),
        sa.Column("previous", sa.Text(), nullable=True),
        sa.Column("revision", sa.Text(), nullable=True),
        sa.Column("actual_better_worse", sa.Text(), nullable=True),
        sa.Column("revision_better_worse", sa.Text(), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "calendar_type IN ('FOREX', 'METALS', 'ENERGY', 'CRYPTO')",
            name="ck_economic_calendar_events_calendar_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "calendar_type",
            "external_event_id",
            name="uq_economic_calendar_events_identity",
        ),
    )
    op.create_index(
        "ix_economic_calendar_events_scheduled_at",
        "economic_calendar_events",
        ["scheduled_at"],
    )
    op.create_index(
        "ix_economic_calendar_events_type_scheduled_at",
        "economic_calendar_events",
        ["calendar_type", "scheduled_at"],
    )
    op.create_index(
        "ix_economic_calendar_events_currency_scheduled_at",
        "economic_calendar_events",
        ["currency", "scheduled_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_economic_calendar_events_currency_scheduled_at",
        table_name="economic_calendar_events",
    )
    op.drop_index(
        "ix_economic_calendar_events_type_scheduled_at",
        table_name="economic_calendar_events",
    )
    op.drop_index(
        "ix_economic_calendar_events_scheduled_at",
        table_name="economic_calendar_events",
    )
    op.drop_table("economic_calendar_events")
