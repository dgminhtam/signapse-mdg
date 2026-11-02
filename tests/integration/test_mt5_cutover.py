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
        assert (
            await connection.scalar(select(func.count()).select_from(SymbolProviderMappingModel))
            == before + 22
        )
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
