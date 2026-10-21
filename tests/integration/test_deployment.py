import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from scripts.verify_deployment import check_migrations

pytestmark = pytest.mark.integration


async def test_deployment_checks_the_actual_database_revision(
    database_engine: AsyncEngine,
) -> None:
    await check_migrations()
    async with database_engine.begin() as connection:
        original = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        await connection.execute(text("UPDATE alembic_version SET version_num = 'wrong-head'"))
    try:
        with pytest.raises(ValueError, match="migration revision"):
            await check_migrations()
    finally:
        async with database_engine.begin() as connection:
            await connection.execute(
                text("UPDATE alembic_version SET version_num = :version"),
                {"version": original},
            )
