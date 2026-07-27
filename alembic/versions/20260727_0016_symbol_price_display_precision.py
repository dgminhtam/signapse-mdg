"""Define per-symbol price display precision.

Revision ID: 20260727_0016
Revises: 20260715_0015
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260727_0016"
down_revision: str | None = "20260715_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRICE_DISPLAY_DECIMALS = {
    "AUD/USD": 5,
    "EUR/USD": 5,
    "GBP/USD": 5,
    "USD/JPY": 3,
    "XAG/USD": 3,
    "NATGAS": 3,
    "BTC/USD": 2,
    "ETH/USD": 2,
    "XAU/USD": 2,
    "WTI": 2,
    "BRENT": 2,
    "COFFEE": 2,
    "SUGAR": 2,
    "WHEAT": 2,
    "CORN": 2,
    "AAPL": 2,
    "TSLA": 2,
    "NVDA": 2,
    "MSFT": 2,
    "SPY": 2,
    "QQQ": 2,
    "SPX": 2,
    "NDX": 2,
    "DJI": 2,
}


def upgrade() -> None:
    op.add_column(
        "supported_symbols",
        sa.Column("price_display_decimals", sa.SmallInteger(), nullable=True),
    )
    connection = op.get_bind()
    supported_symbols = sa.table(
        "supported_symbols",
        sa.column("symbol", sa.Text()),
        sa.column("price_display_decimals", sa.SmallInteger()),
    )
    for symbol, decimals in PRICE_DISPLAY_DECIMALS.items():
        connection.execute(
            supported_symbols.update()
            .where(supported_symbols.c.symbol == symbol)
            .values(price_display_decimals=decimals)
        )

    missing = connection.scalar(
        sa.select(sa.func.count())
        .select_from(supported_symbols)
        .where(supported_symbols.c.price_display_decimals.is_(None))
    )
    if missing:
        raise RuntimeError("Every supported symbol must define price display decimals.")

    op.alter_column("supported_symbols", "price_display_decimals", nullable=False)
    op.create_check_constraint(
        "ck_supported_symbols_price_display_decimals",
        "supported_symbols",
        "price_display_decimals BETWEEN 0 AND 18",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_supported_symbols_price_display_decimals",
        "supported_symbols",
        type_="check",
    )
    op.drop_column("supported_symbols", "price_display_decimals")
