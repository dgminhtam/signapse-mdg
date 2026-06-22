"""Seed Twelve Data Forex symbols.

Revision ID: 20260622_0003
Revises: 20260622_0002
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "20260622_0003"
down_revision: str | None = "20260622_0002"
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

FOREX_SEED_SYMBOLS = (
    {
        "symbol": "EUR/USD",
        "asset_class": "FOREX",
        "provider": "TWELVE_DATA",
        "provider_symbol": "EUR/USD",
        "enabled": True,
    },
    {
        "symbol": "GBP/USD",
        "asset_class": "FOREX",
        "provider": "TWELVE_DATA",
        "provider_symbol": "GBP/USD",
        "enabled": True,
    },
    {
        "symbol": "USD/JPY",
        "asset_class": "FOREX",
        "provider": "TWELVE_DATA",
        "provider_symbol": "USD/JPY",
        "enabled": True,
    },
    {
        "symbol": "AUD/USD",
        "asset_class": "FOREX",
        "provider": "TWELVE_DATA",
        "provider_symbol": "AUD/USD",
        "enabled": True,
    },
)


def seed_forex_supported_symbols(connection: Connection) -> None:
    for values in FOREX_SEED_SYMBOLS:
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
    seed_forex_supported_symbols(op.get_bind())


def downgrade() -> None:
    connection = op.get_bind()
    for values in FOREX_SEED_SYMBOLS:
        connection.execute(
            supported_symbols.delete().where(
                sa.and_(
                    supported_symbols.c.symbol == values["symbol"],
                    supported_symbols.c.asset_class == values["asset_class"],
                    supported_symbols.c.provider == values["provider"],
                    supported_symbols.c.provider_symbol == values["provider_symbol"],
                )
            )
        )
