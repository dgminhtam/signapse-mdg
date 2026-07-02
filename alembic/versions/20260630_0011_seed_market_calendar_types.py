"""Seed market calendar types.

Revision ID: 20260630_0011
Revises: 20260630_0010
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "20260630_0011"
down_revision: str | None = "20260630_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

market_calendars = sa.table(
    "market_calendars",
    sa.column("code", sa.Text()),
    sa.column("source", sa.Text()),
    sa.column("source_calendar", sa.Text()),
    sa.column("timezone", sa.Text()),
    sa.column("generated_from", sa.Date()),
    sa.column("generated_to", sa.Date()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

supported_symbols = sa.table(
    "supported_symbols",
    sa.column("symbol", sa.Text()),
    sa.column("calendar_code", sa.Text()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

CalendarSeedRow = dict[str, object]

MARKET_CALENDARS: tuple[CalendarSeedRow, ...] = (
    {
        "code": "CRYPTO_24_7",
        "source": "internal",
        "source_calendar": "24/7",
        "timezone": "UTC",
        "generated_from": None,
        "generated_to": None,
    },
    {
        "code": "FOREX_24_5",
        "source": "pandas_market_calendars",
        "source_calendar": "FOREX",
        "timezone": "America/New_York",
        "generated_from": None,
        "generated_to": None,
    },
    {
        "code": "US_REGULAR",
        "source": "pandas_market_calendars",
        "source_calendar": "NYSE",
        "timezone": "America/New_York",
        "generated_from": None,
        "generated_to": None,
    },
    {
        "code": "CME_ENERGY",
        "source": "pandas_market_calendars",
        "source_calendar": "CMEGlobex_Energy",
        "timezone": "America/New_York",
        "generated_from": None,
        "generated_to": None,
    },
    {
        "code": "CME_METALS",
        "source": "pandas_market_calendars",
        "source_calendar": "CMEGlobex_Metals",
        "timezone": "America/New_York",
        "generated_from": None,
        "generated_to": None,
    },
    {
        "code": "CME_AGRICULTURE",
        "source": "pandas_market_calendars",
        "source_calendar": "CMEGlobex_Grains",
        "timezone": "America/Chicago",
        "generated_from": None,
        "generated_to": None,
    },
    {
        "code": "ICE_SOFTS",
        "source": "pandas_market_calendars",
        "source_calendar": "ICEUS",
        "timezone": "America/New_York",
        "generated_from": None,
        "generated_to": None,
    },
)

SYMBOL_CALENDAR_MAPPINGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("CRYPTO_24_7", ("BTC/USD", "ETH/USD")),
    ("FOREX_24_5", ("AUD/USD", "EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD")),
    (
        "US_REGULAR",
        ("AAPL", "DJI", "MSFT", "NDX", "NVDA", "QQQ", "SPX", "SPY", "TSLA"),
    ),
    ("CME_ENERGY", ("BRENT", "NATGAS", "WTI")),
    ("CME_METALS", ("XAG/USD",)),
    ("CME_AGRICULTURE", ("CORN", "WHEAT")),
    ("ICE_SOFTS", ("COFFEE", "SUGAR")),
)

DOWNGRADE_NULL_SYMBOLS = (
    "BRENT",
    "BTC/USD",
    "COFFEE",
    "CORN",
    "ETH/USD",
    "NATGAS",
    "SUGAR",
    "WHEAT",
    "WTI",
    "XAG/USD",
)


def seed_market_calendar_types(connection: Connection) -> None:
    for values in MARKET_CALENDARS:
        statement = insert(market_calendars).values(**values)
        connection.execute(
            statement.on_conflict_do_update(
                index_elements=[market_calendars.c.code],
                set_={
                    "source": statement.excluded.source,
                    "source_calendar": statement.excluded.source_calendar,
                    "timezone": statement.excluded.timezone,
                    "generated_from": statement.excluded.generated_from,
                    "generated_to": statement.excluded.generated_to,
                    "updated_at": sa.func.now(),
                },
            )
        )


def seed_symbol_calendar_mappings(connection: Connection) -> None:
    for calendar_code, symbols in SYMBOL_CALENDAR_MAPPINGS:
        connection.execute(
            supported_symbols.update()
            .where(supported_symbols.c.symbol.in_(symbols))
            .values(calendar_code=calendar_code, updated_at=sa.func.now())
        )


def upgrade() -> None:
    connection = op.get_bind()
    seed_market_calendar_types(connection)
    seed_symbol_calendar_mappings(connection)


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        supported_symbols.update()
        .where(supported_symbols.c.symbol.in_(DOWNGRADE_NULL_SYMBOLS))
        .values(calendar_code=None, updated_at=sa.func.now())
    )
    connection.execute(
        market_calendars.delete().where(
            market_calendars.c.code.in_(
                (
                    "CRYPTO_24_7",
                    "CME_ENERGY",
                    "CME_METALS",
                    "CME_AGRICULTURE",
                    "ICE_SOFTS",
                )
            )
        )
    )
