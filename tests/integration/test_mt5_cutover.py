from sqlalchemy import func, select

from app.db.models import SupportedSymbolModel, SymbolProviderMappingModel
from app.providers.mt5 import PROVIDER
from scripts.seed_mt5_local import MAPPINGS, main


async def test_cutover_retains_old_mappings_and_is_idempotent(database_engine):
    async with database_engine.connect() as connection:
        before = await connection.scalar(
            select(func.count()).select_from(SymbolProviderMappingModel)
        )
    # The isolated fixture sets DATABASE_URL; this is never run against shared dev.
    expected_database = str(database_engine.url.database)
    await main(expected_database)
    await main(expected_database)
    async with database_engine.connect() as connection:
        assert await connection.scalar(
            select(func.count()).select_from(SymbolProviderMappingModel)
        ) == before + len(MAPPINGS)
        active = (
            await connection.execute(
                select(SupportedSymbolModel.symbol, SymbolProviderMappingModel.provider_symbol)
                .join(SymbolProviderMappingModel)
                .where(
                    SupportedSymbolModel.enabled,
                    SymbolProviderMappingModel.is_active,
                    SymbolProviderMappingModel.provider == PROVIDER,
                )
            )
        ).all()
        assert dict(active) == MAPPINGS
        crypto = (
            await connection.execute(
                select(
                    SupportedSymbolModel.symbol,
                    SymbolProviderMappingModel.provider,
                    SymbolProviderMappingModel.provider_symbol,
                )
                .join(SymbolProviderMappingModel)
                .where(
                    SupportedSymbolModel.symbol.in_(("BTC/USDT", "ETH/USDT")),
                    SymbolProviderMappingModel.is_active,
                )
            )
        ).all()
        assert set(crypto) == {
            ("BTC/USDT", "BINANCE_SPOT", "BTCUSDT"),
            ("ETH/USDT", "BINANCE_SPOT", "ETHUSDT"),
        }
        assert (
            await connection.scalar(
                select(func.count())
                .select_from(SupportedSymbolModel)
                .where(SupportedSymbolModel.enabled)
            )
            == 22
        )
        # Disabled assets retain their previous defaults for rollback/legacy reconstruction.
        assert (
            await connection.scalar(
                select(func.count())
                .select_from(SymbolProviderMappingModel)
                .where(SymbolProviderMappingModel.is_active)
            )
            == 24
        )
