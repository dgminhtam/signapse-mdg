"""Replace the retired USD crypto registry with Binance Spot USDT pairs.

Existing candles retain their recorded identity; test-data erasure is an explicit
operator operation, not an automatic production data migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261105_0021"
down_revision: str | None = "20260727_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _insert(symbol: str, mappings: tuple[tuple[str, str], ...]) -> None:
    connection = op.get_bind()
    symbol_id = connection.execute(
        sa.text(
            """INSERT INTO supported_symbols
            (symbol, asset_class, enabled, price_display_decimals,
             calendar_source, calendar_name, calendar_timezone)
            VALUES (:symbol, 'CRYPTO', true, 2, 'internal', '24/7', 'UTC')
            RETURNING id"""
        ),
        {"symbol": symbol},
    ).scalar_one()
    for index, (provider, provider_symbol) in enumerate(mappings):
        connection.execute(
            sa.text(
                """INSERT INTO symbol_provider_mappings
                (supported_symbol_id, provider, provider_symbol, is_active)
                VALUES (:id, :provider, :provider_symbol, :active)"""
            ),
            {
                "id": symbol_id,
                "provider": provider,
                "provider_symbol": provider_symbol,
                "active": index == 0,
            },
        )


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM supported_symbols WHERE symbol IN ('BTC/USD', 'ETH/USD')")
    )
    _insert("BTC/USDT", (("BINANCE_SPOT", "BTCUSDT"),))
    _insert("ETH/USDT", (("BINANCE_SPOT", "ETHUSDT"),))


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM supported_symbols WHERE symbol IN ('BTC/USDT', 'ETH/USDT')")
    )
    _insert("BTC/USD", (("TWELVE_DATA", "BTC/USD"), ("YFINANCE", "BTC-USD")))
    _insert("ETH/USD", (("BINANCE_SPOT", "ETHUSD"), ("YFINANCE", "ETH-USD")))
