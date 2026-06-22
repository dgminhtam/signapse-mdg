"""Create the market data candle cache.

Revision ID: 20260622_0002
Revises: 20260619_0001
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260622_0002"
down_revision: str | None = "20260619_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_data_candles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("asset_class", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_symbol", sa.Text(), nullable=False),
        sa.Column("timeframe", sa.Text(), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(), nullable=False),
        sa.Column("high", sa.Numeric(), nullable=False),
        sa.Column("low", sa.Numeric(), nullable=False),
        sa.Column("close", sa.Numeric(), nullable=False),
        sa.Column("volume", sa.Numeric(), nullable=False),
        sa.Column(
            "complete",
            sa.Boolean(),
            server_default=sa.text("true"),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_symbol",
            "timeframe",
            "open_time",
            name="uq_market_data_candles_identity",
        ),
    )
    op.create_index(
        "ix_market_data_candles_symbol_timeframe_open_time",
        "market_data_candles",
        ["symbol", "timeframe", "open_time"],
    )
    op.create_index(
        "ix_market_data_candles_provider_symbol_timeframe_open_time",
        "market_data_candles",
        ["provider", "provider_symbol", "timeframe", "open_time"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_data_candles_provider_symbol_timeframe_open_time",
        table_name="market_data_candles",
    )
    op.drop_index(
        "ix_market_data_candles_symbol_timeframe_open_time",
        table_name="market_data_candles",
    )
    op.drop_table("market_data_candles")
