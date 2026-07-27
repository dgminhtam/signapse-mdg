"""Seed approved provider mappings for the 24-asset catalog.

Revision ID: 20260727_0019
Revises: 20260727_0018
Create Date: 2026-07-27
"""

from collections.abc import Mapping, Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "20260727_0019"
down_revision: str | None = "20260727_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ProviderMapping = tuple[str, str]

PREVIOUS_DEFAULTS: Mapping[str, ProviderMapping] = {
    "AAPL": ("TWELVE_DATA", "AAPL"),
    "AUD/USD": ("TWELVE_DATA", "AUD/USD"),
    "BRENT": ("YFINANCE", "BZ=F"),
    "BTC/USD": ("TWELVE_DATA", "BTC/USD"),
    "COFFEE": ("YFINANCE", "KC=F"),
    "CORN": ("YFINANCE", "ZC=F"),
    "DJI": ("YFINANCE", "^DJI"),
    "ETH/USD": ("TWELVE_DATA", "ETH/USD"),
    "EUR/USD": ("TWELVE_DATA", "EUR/USD"),
    "GBP/USD": ("TWELVE_DATA", "GBP/USD"),
    "MSFT": ("TWELVE_DATA", "MSFT"),
    "NATGAS": ("YFINANCE", "NG=F"),
    "NDX": ("YFINANCE", "^NDX"),
    "NVDA": ("TWELVE_DATA", "NVDA"),
    "QQQ": ("TWELVE_DATA", "QQQ"),
    "SPX": ("YFINANCE", "^GSPC"),
    "SPY": ("TWELVE_DATA", "SPY"),
    "SUGAR": ("YFINANCE", "SB=F"),
    "TSLA": ("TWELVE_DATA", "TSLA"),
    "USD/JPY": ("TWELVE_DATA", "USD/JPY"),
    "WHEAT": ("YFINANCE", "ZW=F"),
    "WTI": ("TWELVE_DATA", "WTI"),
    "XAG/USD": ("YFINANCE", "SI=F"),
    "XAU/USD": ("TWELVE_DATA", "XAU/USD"),
}

TARGET_DEFAULTS: Mapping[str, ProviderMapping] = {
    "AAPL": ("TWELVE_DATA", "AAPL"),
    "AUD/USD": ("YFINANCE", "AUDUSD=X"),
    "BRENT": ("YFINANCE", "BZ=F"),
    "BTC/USD": ("TWELVE_DATA", "BTC/USD"),
    "COFFEE": ("YFINANCE", "KC=F"),
    "CORN": ("YFINANCE", "ZC=F"),
    "DJI": ("YFINANCE", "^DJI"),
    "ETH/USD": ("BINANCE_SPOT", "ETHUSD"),
    "EUR/USD": ("TWELVE_DATA", "EUR/USD"),
    "GBP/USD": ("YFINANCE", "GBPUSD=X"),
    "MSFT": ("YFINANCE", "MSFT"),
    "NATGAS": ("YFINANCE", "NG=F"),
    "NDX": ("YFINANCE", "^NDX"),
    "NVDA": ("YFINANCE", "NVDA"),
    "QQQ": ("TWELVE_DATA", "QQQ"),
    "SPX": ("YFINANCE", "^GSPC"),
    "SPY": ("YFINANCE", "SPY"),
    "SUGAR": ("YFINANCE", "SB=F"),
    "TSLA": ("YFINANCE", "TSLA"),
    "USD/JPY": ("YFINANCE", "JPY=X"),
    "WHEAT": ("YFINANCE", "ZW=F"),
    "WTI": ("YFINANCE", "CL=F"),
    "XAG/USD": ("YFINANCE", "SI=F"),
    "XAU/USD": ("TWELVE_DATA", "XAU/USD"),
}

TARGET_ALTERNATIVES: Mapping[str, ProviderMapping] = {
    "AAPL": ("YFINANCE", "AAPL"),
    "BTC/USD": ("YFINANCE", "BTC-USD"),
    "ETH/USD": ("YFINANCE", "ETH-USD"),
    "EUR/USD": ("YFINANCE", "EURUSD=X"),
    "QQQ": ("YFINANCE", "QQQ"),
}

PREVIOUS_ROWS = tuple(
    (symbol, provider, provider_symbol)
    for symbol, (provider, provider_symbol) in PREVIOUS_DEFAULTS.items()
)
TARGET_ROWS = tuple(
    (symbol, provider, provider_symbol)
    for mappings in (TARGET_DEFAULTS, TARGET_ALTERNATIVES)
    for symbol, (provider, provider_symbol) in mappings.items()
)
OBSOLETE_ROWS = tuple(row for row in PREVIOUS_ROWS if row not in TARGET_ROWS)
INTRODUCED_ROWS = tuple(row for row in TARGET_ROWS if row not in PREVIOUS_ROWS)

supported_symbols = sa.table(
    "supported_symbols",
    sa.column("id", sa.BigInteger()),
    sa.column("symbol", sa.Text()),
    sa.column("provider", sa.Text()),
    sa.column("provider_symbol", sa.Text()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

symbol_provider_mappings = sa.table(
    "symbol_provider_mappings",
    sa.column("supported_symbol_id", sa.BigInteger()),
    sa.column("provider", sa.Text()),
    sa.column("provider_symbol", sa.Text()),
    sa.column("is_active", sa.Boolean()),
)


def _symbol_ids(connection: Connection) -> dict[str, int]:
    rows = connection.execute(
        sa.select(supported_symbols.c.id, supported_symbols.c.symbol).where(
            supported_symbols.c.symbol.in_(tuple(TARGET_DEFAULTS))
        )
    ).all()
    symbol_ids = {row.symbol: row.id for row in rows}
    missing = sorted(set(TARGET_DEFAULTS) - set(symbol_ids))
    if missing:
        raise RuntimeError(f"Missing supported symbols for provider seed: {', '.join(missing)}")
    return symbol_ids


def _upsert_mappings(
    connection: Connection,
    symbol_ids: Mapping[str, int],
    mappings: Mapping[str, ProviderMapping],
) -> None:
    for symbol, (provider, provider_symbol) in mappings.items():
        statement = insert(symbol_provider_mappings).values(
            supported_symbol_id=symbol_ids[symbol],
            provider=provider,
            provider_symbol=provider_symbol,
            is_active=False,
        )
        connection.execute(
            statement.on_conflict_do_update(
                index_elements=[
                    symbol_provider_mappings.c.supported_symbol_id,
                    symbol_provider_mappings.c.provider,
                ],
                set_={
                    "provider_symbol": statement.excluded.provider_symbol,
                    "is_active": False,
                },
            )
        )


def _set_defaults(
    connection: Connection,
    symbol_ids: Mapping[str, int],
    defaults: Mapping[str, ProviderMapping],
) -> None:
    for symbol, (provider, provider_symbol) in defaults.items():
        connection.execute(
            symbol_provider_mappings.update()
            .where(
                sa.and_(
                    symbol_provider_mappings.c.supported_symbol_id == symbol_ids[symbol],
                    symbol_provider_mappings.c.provider == provider,
                    symbol_provider_mappings.c.provider_symbol == provider_symbol,
                )
            )
            .values(is_active=True)
        )
        connection.execute(
            supported_symbols.update()
            .where(
                sa.and_(
                    supported_symbols.c.id == symbol_ids[symbol],
                    sa.or_(
                        supported_symbols.c.provider.is_distinct_from(provider),
                        supported_symbols.c.provider_symbol.is_distinct_from(provider_symbol),
                    ),
                )
            )
            .values(
                provider=provider,
                provider_symbol=provider_symbol,
                updated_at=sa.func.now(),
            )
        )


def _delete_mappings(
    connection: Connection,
    symbol_ids: Mapping[str, int],
    mappings: Sequence[tuple[str, str, str]],
) -> None:
    for symbol, provider, provider_symbol in mappings:
        connection.execute(
            symbol_provider_mappings.delete().where(
                sa.and_(
                    symbol_provider_mappings.c.supported_symbol_id == symbol_ids[symbol],
                    symbol_provider_mappings.c.provider == provider,
                    symbol_provider_mappings.c.provider_symbol == provider_symbol,
                )
            )
        )


def _validate_defaults(
    connection: Connection,
    symbol_ids: Mapping[str, int],
    defaults: Mapping[str, ProviderMapping],
    expected_mappings: Sequence[tuple[str, str, str]],
) -> None:
    active_rows = connection.execute(
        sa.select(
            supported_symbols.c.symbol,
            symbol_provider_mappings.c.provider,
            symbol_provider_mappings.c.provider_symbol,
        )
        .select_from(
            supported_symbols.join(
                symbol_provider_mappings,
                supported_symbols.c.id == symbol_provider_mappings.c.supported_symbol_id,
            )
        )
        .where(
            sa.and_(
                supported_symbols.c.id.in_(tuple(symbol_ids.values())),
                symbol_provider_mappings.c.is_active,
            )
        )
    ).all()
    active = {row.symbol: (row.provider, row.provider_symbol) for row in active_rows}
    if active != dict(defaults):
        raise RuntimeError("Approved active provider mapping validation failed.")

    target_count = 0
    for symbol, provider, provider_symbol in expected_mappings:
        target_count += int(
            connection.scalar(
                sa.select(sa.func.count())
                .select_from(symbol_provider_mappings)
                .where(
                    sa.and_(
                        symbol_provider_mappings.c.supported_symbol_id == symbol_ids[symbol],
                        symbol_provider_mappings.c.provider == provider,
                        symbol_provider_mappings.c.provider_symbol == provider_symbol,
                    )
                )
            )
            or 0
        )
    if target_count != len(expected_mappings):
        raise RuntimeError("Approved provider mapping seed validation failed.")

    legacy_rows = connection.execute(
        sa.select(
            supported_symbols.c.symbol,
            supported_symbols.c.provider,
            supported_symbols.c.provider_symbol,
        ).where(supported_symbols.c.id.in_(tuple(symbol_ids.values())))
    ).all()
    legacy = {row.symbol: (row.provider, row.provider_symbol) for row in legacy_rows}
    if legacy != dict(defaults):
        raise RuntimeError("Legacy provider mirror validation failed.")


def seed_provider_mappings(connection: Connection) -> None:
    symbol_ids = _symbol_ids(connection)
    connection.execute(
        symbol_provider_mappings.update()
        .where(symbol_provider_mappings.c.supported_symbol_id.in_(tuple(symbol_ids.values())))
        .values(is_active=False)
    )
    _upsert_mappings(connection, symbol_ids, TARGET_DEFAULTS)
    _upsert_mappings(connection, symbol_ids, TARGET_ALTERNATIVES)
    _delete_mappings(connection, symbol_ids, OBSOLETE_ROWS)
    _set_defaults(connection, symbol_ids, TARGET_DEFAULTS)
    _validate_defaults(
        connection,
        symbol_ids,
        TARGET_DEFAULTS,
        TARGET_ROWS,
    )


def upgrade() -> None:
    seed_provider_mappings(op.get_bind())


def downgrade() -> None:
    connection = op.get_bind()
    symbol_ids = _symbol_ids(connection)
    connection.execute(
        symbol_provider_mappings.update()
        .where(symbol_provider_mappings.c.supported_symbol_id.in_(tuple(symbol_ids.values())))
        .values(is_active=False)
    )
    _upsert_mappings(connection, symbol_ids, PREVIOUS_DEFAULTS)
    _delete_mappings(connection, symbol_ids, INTRODUCED_ROWS)
    _set_defaults(connection, symbol_ids, PREVIOUS_DEFAULTS)
    _validate_defaults(
        connection,
        symbol_ids,
        PREVIOUS_DEFAULTS,
        PREVIOUS_ROWS,
    )
