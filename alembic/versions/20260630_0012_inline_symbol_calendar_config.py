"""Inline symbol calendar config.

Revision ID: 20260630_0012
Revises: 20260630_0011
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "20260630_0012"
down_revision: str | None = "20260630_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

supported_symbols = sa.table(
    "supported_symbols",
    sa.column("symbol", sa.Text()),
    sa.column("calendar_source", sa.Text()),
    sa.column("calendar_name", sa.Text()),
    sa.column("calendar_timezone", sa.Text()),
    sa.column("calendar_code", sa.Text()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

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

CalendarSeedRow = dict[str, object]

INLINE_CALENDAR_CONFIGS: tuple[tuple[str, str, str, str], ...] = (
    ("BTC/USD", "internal", "24/7", "UTC"),
    ("ETH/USD", "internal", "24/7", "UTC"),
    ("AUD/USD", "pandas_market_calendars", "FOREX", "America/New_York"),
    ("EUR/USD", "pandas_market_calendars", "FOREX", "America/New_York"),
    ("GBP/USD", "pandas_market_calendars", "FOREX", "America/New_York"),
    ("USD/JPY", "pandas_market_calendars", "FOREX", "America/New_York"),
    ("XAU/USD", "pandas_market_calendars", "FOREX", "America/New_York"),
    ("AAPL", "pandas_market_calendars", "NYSE", "America/New_York"),
    ("DJI", "pandas_market_calendars", "NYSE", "America/New_York"),
    ("MSFT", "pandas_market_calendars", "NYSE", "America/New_York"),
    ("NDX", "pandas_market_calendars", "NYSE", "America/New_York"),
    ("NVDA", "pandas_market_calendars", "NYSE", "America/New_York"),
    ("QQQ", "pandas_market_calendars", "NYSE", "America/New_York"),
    ("SPX", "pandas_market_calendars", "NYSE", "America/New_York"),
    ("SPY", "pandas_market_calendars", "NYSE", "America/New_York"),
    ("TSLA", "pandas_market_calendars", "NYSE", "America/New_York"),
    ("BRENT", "pandas_market_calendars", "CMEGlobex_Energy", "America/New_York"),
    ("NATGAS", "pandas_market_calendars", "CMEGlobex_Energy", "America/New_York"),
    ("WTI", "pandas_market_calendars", "CMEGlobex_Energy", "America/New_York"),
    ("XAG/USD", "pandas_market_calendars", "CMEGlobex_Metals", "America/New_York"),
    ("CORN", "pandas_market_calendars", "CMEGlobex_Grains", "America/Chicago"),
    ("WHEAT", "pandas_market_calendars", "CMEGlobex_Grains", "America/Chicago"),
    ("COFFEE", "pandas_market_calendars", "ICEUS", "America/New_York"),
    ("SUGAR", "pandas_market_calendars", "ICEUS", "America/New_York"),
)

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


def seed_inline_calendar_config(connection: Connection) -> None:
    for symbol, calendar_source, calendar_name, calendar_timezone in INLINE_CALENDAR_CONFIGS:
        connection.execute(
            supported_symbols.update()
            .where(supported_symbols.c.symbol == symbol)
            .values(
                calendar_source=calendar_source,
                calendar_name=calendar_name,
                calendar_timezone=calendar_timezone,
                updated_at=sa.func.now(),
            )
        )


def seed_market_calendars(connection: Connection) -> None:
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
    op.add_column("supported_symbols", sa.Column("calendar_source", sa.Text(), nullable=True))
    op.add_column("supported_symbols", sa.Column("calendar_name", sa.Text(), nullable=True))
    op.add_column("supported_symbols", sa.Column("calendar_timezone", sa.Text(), nullable=True))
    seed_inline_calendar_config(op.get_bind())
    op.drop_index(
        "ix_market_calendar_sessions_calendar_time",
        table_name="market_calendar_sessions",
    )
    op.drop_table("market_calendar_sessions")
    op.drop_constraint(
        "fk_supported_symbols_calendar_code",
        "supported_symbols",
        type_="foreignkey",
    )
    op.drop_column("supported_symbols", "calendar_code")
    op.drop_table("market_calendars")


def downgrade() -> None:
    op.create_table(
        "market_calendars",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_calendar", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("generated_from", sa.Date(), nullable=True),
        sa.Column("generated_to", sa.Date(), nullable=True),
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
        sa.PrimaryKeyConstraint("code"),
    )
    op.add_column("supported_symbols", sa.Column("calendar_code", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_supported_symbols_calendar_code",
        "supported_symbols",
        "market_calendars",
        ["calendar_code"],
        ["code"],
    )
    op.create_table(
        "market_calendar_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("calendar_code", sa.Text(), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("break_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("break_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("open_time < close_time", name="ck_market_calendar_sessions_time_order"),
        sa.CheckConstraint(
            """
            (break_start IS NULL AND break_end IS NULL)
            OR (
                break_start IS NOT NULL
                AND break_end IS NOT NULL
                AND open_time < break_start
                AND break_start < break_end
                AND break_end < close_time
            )
            """,
            name="ck_market_calendar_sessions_break_order",
        ),
        sa.ForeignKeyConstraint(
            ["calendar_code"],
            ["market_calendars.code"],
            name="fk_market_calendar_sessions_calendar_code",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "calendar_code",
            "session_date",
            name="uq_market_calendar_sessions_calendar_date",
        ),
    )
    op.create_index(
        "ix_market_calendar_sessions_calendar_time",
        "market_calendar_sessions",
        ["calendar_code", "open_time", "close_time"],
    )
    connection = op.get_bind()
    seed_market_calendars(connection)
    seed_symbol_calendar_mappings(connection)
    op.drop_column("supported_symbols", "calendar_timezone")
    op.drop_column("supported_symbols", "calendar_name")
    op.drop_column("supported_symbols", "calendar_source")
