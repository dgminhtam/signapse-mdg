"""Simplify symbol provider selection.

Revision ID: 20260727_0018
Revises: 20260727_0017
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260727_0018"
down_revision: str | None = "20260727_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "symbol_provider_mappings",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE symbol_provider_mappings
            SET is_active = true
            WHERE enabled
              AND quote_priority = 0
              AND candle_priority = 0
              AND stream_priority = 0
            """
        )
    )

    invalid_symbol_count = connection.scalar(
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
    if invalid_symbol_count:
        raise RuntimeError(
            "Every supported symbol must have exactly one shared active provider mapping."
        )

    op.create_index(
        "ux_symbol_provider_mappings_active_symbol",
        "symbol_provider_mappings",
        ["supported_symbol_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    for constraint_name in (
        "ck_symbol_provider_mappings_equivalence_key_nonempty",
        "ck_symbol_provider_mappings_quote_priority_nonnegative",
        "ck_symbol_provider_mappings_candle_priority_nonnegative",
        "ck_symbol_provider_mappings_stream_priority_nonnegative",
        "ck_symbol_provider_mappings_has_capability",
    ):
        op.drop_constraint(
            constraint_name,
            "symbol_provider_mappings",
            type_="check",
        )
    for constraint_name in (
        "uq_symbol_provider_mappings_quote_priority",
        "uq_symbol_provider_mappings_candle_priority",
        "uq_symbol_provider_mappings_stream_priority",
    ):
        op.drop_constraint(
            constraint_name,
            "symbol_provider_mappings",
            type_="unique",
        )
    for column_name in (
        "equivalence_key",
        "quote_priority",
        "candle_priority",
        "stream_priority",
        "enabled",
    ):
        op.drop_column("symbol_provider_mappings", column_name)


def downgrade() -> None:
    op.add_column(
        "symbol_provider_mappings",
        sa.Column("equivalence_key", sa.Text(), nullable=True),
    )
    op.add_column(
        "symbol_provider_mappings",
        sa.Column("quote_priority", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "symbol_provider_mappings",
        sa.Column("candle_priority", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "symbol_provider_mappings",
        sa.Column("stream_priority", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "symbol_provider_mappings",
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    op.get_bind().execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    id,
                    (
                        row_number() OVER (
                            PARTITION BY supported_symbol_id
                            ORDER BY is_active DESC, id
                        ) - 1
                    )::smallint AS priority
                FROM symbol_provider_mappings
            )
            UPDATE symbol_provider_mappings AS mappings
            SET
                equivalence_key = 'mapping:' || mappings.id,
                quote_priority = ranked.priority,
                candle_priority = ranked.priority,
                stream_priority = ranked.priority,
                enabled = true
            FROM ranked
            WHERE mappings.id = ranked.id
            """
        )
    )
    op.alter_column(
        "symbol_provider_mappings",
        "equivalence_key",
        nullable=False,
    )

    for constraint_name, condition in (
        (
            "ck_symbol_provider_mappings_equivalence_key_nonempty",
            "btrim(equivalence_key) <> ''",
        ),
        (
            "ck_symbol_provider_mappings_quote_priority_nonnegative",
            "quote_priority IS NULL OR quote_priority >= 0",
        ),
        (
            "ck_symbol_provider_mappings_candle_priority_nonnegative",
            "candle_priority IS NULL OR candle_priority >= 0",
        ),
        (
            "ck_symbol_provider_mappings_stream_priority_nonnegative",
            "stream_priority IS NULL OR stream_priority >= 0",
        ),
        (
            "ck_symbol_provider_mappings_has_capability",
            "quote_priority IS NOT NULL "
            "OR candle_priority IS NOT NULL "
            "OR stream_priority IS NOT NULL",
        ),
    ):
        op.create_check_constraint(
            constraint_name,
            "symbol_provider_mappings",
            condition,
        )
    for constraint_name, column_name in (
        ("uq_symbol_provider_mappings_quote_priority", "quote_priority"),
        ("uq_symbol_provider_mappings_candle_priority", "candle_priority"),
        ("uq_symbol_provider_mappings_stream_priority", "stream_priority"),
    ):
        op.create_unique_constraint(
            constraint_name,
            "symbol_provider_mappings",
            ["supported_symbol_id", column_name],
        )

    op.drop_index(
        "ux_symbol_provider_mappings_active_symbol",
        table_name="symbol_provider_mappings",
    )
    op.drop_column("symbol_provider_mappings", "is_active")
