"""Normalize symbol-to-provider mappings.

Revision ID: 20260727_0017
Revises: 20260727_0016
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260727_0017"
down_revision: str | None = "20260727_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "symbol_provider_mappings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("supported_symbol_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_symbol", sa.Text(), nullable=False),
        sa.Column("equivalence_key", sa.Text(), nullable=False),
        sa.Column("quote_priority", sa.SmallInteger(), nullable=True),
        sa.Column("candle_priority", sa.SmallInteger(), nullable=True),
        sa.Column("stream_priority", sa.SmallInteger(), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "btrim(provider) <> ''",
            name="ck_symbol_provider_mappings_provider_nonempty",
        ),
        sa.CheckConstraint(
            "btrim(provider_symbol) <> ''",
            name="ck_symbol_provider_mappings_provider_symbol_nonempty",
        ),
        sa.CheckConstraint(
            "btrim(equivalence_key) <> ''",
            name="ck_symbol_provider_mappings_equivalence_key_nonempty",
        ),
        sa.CheckConstraint(
            "quote_priority IS NULL OR quote_priority >= 0",
            name="ck_symbol_provider_mappings_quote_priority_nonnegative",
        ),
        sa.CheckConstraint(
            "candle_priority IS NULL OR candle_priority >= 0",
            name="ck_symbol_provider_mappings_candle_priority_nonnegative",
        ),
        sa.CheckConstraint(
            "stream_priority IS NULL OR stream_priority >= 0",
            name="ck_symbol_provider_mappings_stream_priority_nonnegative",
        ),
        sa.CheckConstraint(
            "quote_priority IS NOT NULL "
            "OR candle_priority IS NOT NULL "
            "OR stream_priority IS NOT NULL",
            name="ck_symbol_provider_mappings_has_capability",
        ),
        sa.ForeignKeyConstraint(
            ["supported_symbol_id"],
            ["supported_symbols.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "supported_symbol_id",
            "provider",
            name="uq_symbol_provider_mappings_symbol_provider",
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_symbol",
            name="uq_symbol_provider_mappings_provider_symbol",
        ),
        sa.UniqueConstraint(
            "supported_symbol_id",
            "quote_priority",
            name="uq_symbol_provider_mappings_quote_priority",
        ),
        sa.UniqueConstraint(
            "supported_symbol_id",
            "candle_priority",
            name="uq_symbol_provider_mappings_candle_priority",
        ),
        sa.UniqueConstraint(
            "supported_symbol_id",
            "stream_priority",
            name="uq_symbol_provider_mappings_stream_priority",
        ),
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO symbol_provider_mappings (
                supported_symbol_id,
                provider,
                provider_symbol,
                equivalence_key,
                quote_priority,
                candle_priority,
                stream_priority,
                enabled,
                created_at,
                updated_at
            )
            SELECT
                id,
                provider,
                provider_symbol,
                'mapping:' || id,
                0,
                0,
                0,
                true,
                created_at,
                updated_at
            FROM supported_symbols
            """
        )
    )

    symbol_count = connection.scalar(sa.text("SELECT count(*) FROM supported_symbols"))
    mapping_count = connection.scalar(sa.text("SELECT count(*) FROM symbol_provider_mappings"))
    priority_zero_count = connection.scalar(
        sa.text(
            """
            SELECT count(*)
            FROM symbol_provider_mappings
            WHERE quote_priority = 0
              AND candle_priority = 0
              AND stream_priority = 0
            """
        )
    )
    if symbol_count != mapping_count or mapping_count != priority_zero_count:
        raise RuntimeError("Symbol provider mapping backfill validation failed.")


def downgrade() -> None:
    op.drop_table("symbol_provider_mappings")
