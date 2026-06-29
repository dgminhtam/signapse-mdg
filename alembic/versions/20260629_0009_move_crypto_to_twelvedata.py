"""Move crypto symbols to Twelve Data.

Revision ID: 20260629_0009
Revises: 20260622_0008
Create Date: 2026-06-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "20260629_0009"
down_revision: str | None = "20260622_0008"
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

CryptoSeedRow = dict[str, object]

TWELVEDATA_CRYPTO_SYMBOLS: tuple[CryptoSeedRow, ...] = (
    {
        "symbol": "BTC/USD",
        "asset_class": "CRYPTO",
        "provider": "TWELVE_DATA",
        "provider_symbol": "BTC/USD",
        "enabled": True,
    },
    {
        "symbol": "ETH/USD",
        "asset_class": "CRYPTO",
        "provider": "TWELVE_DATA",
        "provider_symbol": "ETH/USD",
        "enabled": True,
    },
)

BINANCE_CRYPTO_SYMBOLS: tuple[CryptoSeedRow, ...] = (
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


def upsert_crypto_symbols(connection: Connection, rows: tuple[CryptoSeedRow, ...]) -> None:
    for values in rows:
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
    upsert_crypto_symbols(op.get_bind(), TWELVEDATA_CRYPTO_SYMBOLS)


def downgrade() -> None:
    upsert_crypto_symbols(op.get_bind(), BINANCE_CRYPTO_SYMBOLS)
