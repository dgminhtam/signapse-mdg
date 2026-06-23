"""Seed yfinance planned catalog symbols.

Revision ID: 20260622_0008
Revises: 20260622_0007
Create Date: 2026-06-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "20260622_0008"
down_revision: str | None = "20260622_0007"
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

YFINANCE_SEED_SYMBOLS = (
    {
        "symbol": "XAG/USD",
        "asset_class": "COMMODITY",
        "provider": "YFINANCE",
        "provider_symbol": "SI=F",
        "enabled": True,
    },
    {
        "symbol": "BRENT",
        "asset_class": "COMMODITY",
        "provider": "YFINANCE",
        "provider_symbol": "BZ=F",
        "enabled": True,
    },
    {
        "symbol": "SPX",
        "asset_class": "STOCK_INDEX",
        "provider": "YFINANCE",
        "provider_symbol": "^GSPC",
        "enabled": True,
    },
    {
        "symbol": "NDX",
        "asset_class": "STOCK_INDEX",
        "provider": "YFINANCE",
        "provider_symbol": "^NDX",
        "enabled": True,
    },
    {
        "symbol": "DJI",
        "asset_class": "STOCK_INDEX",
        "provider": "YFINANCE",
        "provider_symbol": "^DJI",
        "enabled": True,
    },
    {
        "symbol": "NATGAS",
        "asset_class": "COMMODITY",
        "provider": "YFINANCE",
        "provider_symbol": "NG=F",
        "enabled": True,
    },
    {
        "symbol": "COFFEE",
        "asset_class": "COMMODITY",
        "provider": "YFINANCE",
        "provider_symbol": "KC=F",
        "enabled": True,
    },
    {
        "symbol": "SUGAR",
        "asset_class": "COMMODITY",
        "provider": "YFINANCE",
        "provider_symbol": "SB=F",
        "enabled": True,
    },
    {
        "symbol": "WHEAT",
        "asset_class": "COMMODITY",
        "provider": "YFINANCE",
        "provider_symbol": "ZW=F",
        "enabled": True,
    },
    {
        "symbol": "CORN",
        "asset_class": "COMMODITY",
        "provider": "YFINANCE",
        "provider_symbol": "ZC=F",
        "enabled": True,
    },
)


def seed_yfinance_supported_symbols(connection: Connection) -> None:
    for values in YFINANCE_SEED_SYMBOLS:
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
    seed_yfinance_supported_symbols(op.get_bind())


def delete_yfinance_supported_symbols(connection: Connection) -> None:
    for values in YFINANCE_SEED_SYMBOLS:
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


def downgrade() -> None:
    delete_yfinance_supported_symbols(op.get_bind())
