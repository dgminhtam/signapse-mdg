"""Seed Twelve Data XAU/USD symbol.

Revision ID: 20260622_0005
Revises: 20260622_0004
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "20260622_0005"
down_revision: str | None = "20260622_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

supported_symbols = sa.table(
    "supported_symbols",
    sa.column("symbol", sa.Text()),
    sa.column("asset_class", sa.Text()),
    sa.column("provider", sa.Text()),
    sa.column("provider_symbol", sa.Text()),
    sa.column("enabled", sa.Boolean()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

XAU_USD_SYMBOL = {
    "symbol": "XAU/USD",
    "asset_class": "COMMODITY",
    "provider": "TWELVE_DATA",
    "provider_symbol": "XAU/USD",
    "enabled": True,
}


def seed_xau_usd_symbol(connection: Connection) -> None:
    statement = insert(supported_symbols).values(**XAU_USD_SYMBOL)
    connection.execute(
        statement.on_conflict_do_update(
            index_elements=[supported_symbols.c.symbol],
            set_={
                "asset_class": statement.excluded.asset_class,
                "provider": statement.excluded.provider,
                "provider_symbol": statement.excluded.provider_symbol,
                "enabled": statement.excluded.enabled,
                "updated_at": sa.func.now(),
            },
        )
    )


def upgrade() -> None:
    seed_xau_usd_symbol(op.get_bind())


def downgrade() -> None:
    op.get_bind().execute(
        supported_symbols.delete().where(
            sa.and_(
                supported_symbols.c.symbol == XAU_USD_SYMBOL["symbol"],
                supported_symbols.c.asset_class == XAU_USD_SYMBOL["asset_class"],
                supported_symbols.c.provider == XAU_USD_SYMBOL["provider"],
                supported_symbols.c.provider_symbol == XAU_USD_SYMBOL["provider_symbol"],
            )
        )
    )
