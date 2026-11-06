from asyncio import to_thread
from datetime import UTC, datetime, timedelta

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from alembic import command
from app.db.repositories import PostgresCandleRepository
from app.main import app

pytestmark = pytest.mark.integration


async def test_crypto_cutover_preserves_other_assets_and_recorded_candle_identity(
    database_engine: AsyncEngine,
) -> None:
    config = Config("alembic.ini")
    await to_thread(command.downgrade, config, "20260727_0020")
    async with database_engine.begin() as connection:
        before = (
            await connection.execute(
                text("SELECT * FROM supported_symbols WHERE asset_class <> 'CRYPTO' ORDER BY id")
            )
        ).all()
        mappings_before = (
            await connection.execute(
                text("""SELECT m.* FROM symbol_provider_mappings m JOIN supported_symbols s
                ON s.id = m.supported_symbol_id WHERE s.asset_class <> 'CRYPTO' ORDER BY m.id""")
            )
        ).all()
        opened = datetime(2026, 1, 1, tzinfo=UTC)
        await connection.execute(
            text("""INSERT INTO market_data_candles
            (symbol, asset_class, provider, provider_symbol, timeframe, open_time, close_time,
             open, high, low, close, volume, complete)
            VALUES ('BTC/USD', 'CRYPTO', 'BINANCE_SPOT', 'BTCUSD', '1h', :opened, :closed,
                    1, 1, 1, 1, 0, true)"""),
            {"opened": opened, "closed": opened + timedelta(hours=1)},
        )
    await to_thread(command.upgrade, config, "head")
    await to_thread(command.upgrade, config, "head")
    async with database_engine.connect() as connection:
        after = (
            await connection.execute(
                text("SELECT * FROM supported_symbols WHERE asset_class <> 'CRYPTO' ORDER BY id")
            )
        ).all()
        mappings_after = (
            await connection.execute(
                text("""SELECT m.* FROM symbol_provider_mappings m JOIN supported_symbols s
                ON s.id = m.supported_symbol_id WHERE s.asset_class <> 'CRYPTO' ORDER BY m.id""")
            )
        ).all()
        recorded = (
            await connection.execute(
                text("SELECT symbol, provider_symbol FROM market_data_candles")
            )
        ).all()
    assert after == before
    assert mappings_after == mappings_before
    assert recorded == [("BTC/USD", "BTCUSD")]
    repository = PostgresCandleRepository(async_sessionmaker(database_engine))
    assert await repository.get_enabled_symbol("BTC/USD") is None
    assert await repository.get_enabled_symbol("ETH/USD") is None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/symbols")
    assert response.status_code == 200
    crypto = [s for s in response.json()["symbols"] if s["assetClass"] == "CRYPTO"]
    assert [(s["symbol"], s["provider"], s["providerSymbol"]) for s in crypto] == [
        ("BTC/USDT", "BINANCE_SPOT", "BTCUSDT"),
        ("ETH/USDT", "BINANCE_SPOT", "ETHUSDT"),
    ]
    assert all(s["priceDisplayDecimals"] == 2 and len(s["providerMappings"]) == 1 for s in crypto)
