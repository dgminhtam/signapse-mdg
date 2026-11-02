"""Activate the accepted 22 MT5 mappings; dev cutover requires an explicit database guard."""

import argparse
import asyncio

from sqlalchemy import select, update

from app.core.config import get_settings
from app.db.models import SupportedSymbolModel, SymbolProviderMappingModel
from app.db.session import build_session_factory
from app.providers.mt5 import PROVIDER

MAPPINGS = {
    "EUR/USD": "EURUSD",
    "GBP/USD": "GBPUSD",
    "USD/JPY": "USDJPY",
    "AUD/USD": "AUDUSD",
    "XAU/USD": "XAUUSD",
    "XAG/USD": "XAGUSD",
    "AAPL": "AAPL",
    "TSLA": "TSLA",
    "NVDA": "NVIDIA",
    "MSFT": "MSFT",
    "BTC/USD": "BTCUSD",
    "ETH/USD": "ETHUSD",
    "SPY": "SPY",
    "QQQ": "QQQ",
    "WTI": "USOUSD",
    "BRENT": "UKOUSD",
    "NATGAS": "NG-Cr",
    "COFFEE": "Coffee-Cr",
    "SUGAR": "Sugar-Cr",
    "WHEAT": "Wheat-Cr",
    "SPX": "SP500.r",
    "NDX": "NAS100.r",
}


async def main(expected_database: str = "mdg_mt5_local") -> None:
    settings = get_settings()
    if not settings.database_url or settings.database_url.rsplit("/", 1)[-1] != expected_database:
        raise ValueError("Refusing to change an unexpected database")
    database = build_session_factory(settings)
    assert database is not None
    try:
        async with database[1].begin() as session:
            rows = list(await session.scalars(select(SupportedSymbolModel)))
            if not set(MAPPINGS).issubset({r.symbol for r in rows}):
                raise ValueError("Run Alembic migrations first")
            await session.execute(update(SupportedSymbolModel).values(enabled=False))
            await session.execute(update(SymbolProviderMappingModel).values(is_active=False))
            existing = list(await session.scalars(select(SymbolProviderMappingModel)))
            for row in rows:
                if row.symbol not in MAPPINGS:
                    continue
                row.enabled = True
                mapping = next(
                    (
                        m
                        for m in existing
                        if m.supported_symbol_id == row.id and m.provider == PROVIDER
                    ),
                    None,
                )
                if mapping is None:
                    session.add(
                        SymbolProviderMappingModel(
                            supported_symbol_id=row.id,
                            provider=PROVIDER,
                            provider_symbol=MAPPINGS[row.symbol],
                            is_active=True,
                        )
                    )
                else:
                    mapping.provider_symbol = MAPPINGS[row.symbol]
                    mapping.is_active = True
        print(f"Activated {len(MAPPINGS)} MT5 mappings in {expected_database}")
    finally:
        await database[0].dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", choices=["mdg_mt5_local", "dev-signapse-mdg"], default="mdg_mt5_local"
    )
    asyncio.run(main(parser.parse_args().database))
