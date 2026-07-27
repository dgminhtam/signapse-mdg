"""Remove legacy provider columns from supported symbols.

Revision ID: 20260727_0020
Revises: 20260727_0019
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260727_0020"
down_revision: str | None = "20260727_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _invalid_active_mapping_count(connection: sa.Connection) -> int:
    return int(
        connection.scalar(
            sa.text(
                """
                SELECT count(*)
                FROM (
                    SELECT supported_symbols.id
                    FROM supported_symbols
                    LEFT JOIN symbol_provider_mappings
                      ON symbol_provider_mappings.supported_symbol_id = supported_symbols.id
                     AND symbol_provider_mappings.is_active
                    GROUP BY supported_symbols.id
                    HAVING count(symbol_provider_mappings.id) <> 1
                ) AS invalid_symbols
                """
            )
        )
        or 0
    )


def upgrade() -> None:
    connection = op.get_bind()
    if _invalid_active_mapping_count(connection):
        raise RuntimeError("Every supported symbol must have exactly one active provider mapping.")

    op.drop_constraint(
        "uq_supported_symbols_provider_symbol",
        "supported_symbols",
        type_="unique",
    )
    op.drop_column("supported_symbols", "provider_symbol")
    op.drop_column("supported_symbols", "provider")


def downgrade() -> None:
    connection = op.get_bind()
    if _invalid_active_mapping_count(connection):
        raise RuntimeError(
            "Cannot reconstruct legacy columns without one active mapping per symbol."
        )

    op.add_column("supported_symbols", sa.Column("provider", sa.Text(), nullable=True))
    op.add_column("supported_symbols", sa.Column("provider_symbol", sa.Text(), nullable=True))
    connection.execute(
        sa.text(
            """
            UPDATE supported_symbols AS symbols
            SET provider = mappings.provider,
                provider_symbol = mappings.provider_symbol
            FROM symbol_provider_mappings AS mappings
            WHERE mappings.supported_symbol_id = symbols.id
              AND mappings.is_active
            """
        )
    )

    incomplete = int(
        connection.scalar(
            sa.text(
                """
                SELECT count(*)
                FROM supported_symbols
                WHERE provider IS NULL OR provider_symbol IS NULL
                """
            )
        )
        or 0
    )
    duplicates = int(
        connection.scalar(
            sa.text(
                """
                SELECT count(*)
                FROM (
                    SELECT provider, provider_symbol
                    FROM supported_symbols
                    GROUP BY provider, provider_symbol
                    HAVING count(*) > 1
                ) AS duplicate_mappings
                """
            )
        )
        or 0
    )
    if incomplete or duplicates:
        raise RuntimeError("Active provider mappings cannot reconstruct valid legacy columns.")

    op.alter_column("supported_symbols", "provider", nullable=False)
    op.alter_column("supported_symbols", "provider_symbol", nullable=False)
    op.create_unique_constraint(
        "uq_supported_symbols_provider_symbol",
        "supported_symbols",
        ["provider", "provider_symbol"],
    )
