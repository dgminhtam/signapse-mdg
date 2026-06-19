"""Create and seed the supported symbol registry.

Revision ID: 20260619_0001
Revises:
Create Date: 2026-06-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "20260619_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

supported_symbols = sa.table(
    "supported_symbols",
    sa.column("symbol", sa.Text()),
    sa.column("asset_class", sa.Text()),
    sa.column("provider", sa.Text()),
    sa.column("provider_symbol", sa.Text()),
    sa.column("enabled", sa.Boolean()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

SEED_SYMBOLS = (
    {
        "symbol": "BTC/USD",
        "asset_class": "CRYPTO",
        "provider": "BINANCE_SPOT",
        "provider_symbol": "BTCUSD",
        "enabled": True,
    },
    {
        "symbol": "ETH/USD",
        "asset_class": "CRYPTO",
        "provider": "BINANCE_SPOT",
        "provider_symbol": "ETHUSD",
        "enabled": True,
    },
)


def seed_supported_symbols(connection: Connection) -> None:
    for values in SEED_SYMBOLS:
        statement = insert(supported_symbols).values(**values)
        connection.execute(
            statement.on_conflict_do_update(
                index_elements=[supported_symbols.c.symbol],
                set_={
                    "asset_class": statement.excluded.asset_class,
                    "provider": statement.excluded.provider,
                    "provider_symbol": statement.excluded.provider_symbol,
                    "enabled": statement.excluded.enabled,
                    "updated_at": sa.func.now(),
                },
            )
        )


def upgrade() -> None:
    op.create_table(
        "supported_symbols",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("asset_class", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_symbol", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.UniqueConstraint("symbol", name="uq_supported_symbols_symbol"),
        sa.UniqueConstraint(
            "provider",
            "provider_symbol",
            name="uq_supported_symbols_provider_symbol",
        ),
    )
    seed_supported_symbols(op.get_bind())


def downgrade() -> None:
    op.drop_table("supported_symbols")
