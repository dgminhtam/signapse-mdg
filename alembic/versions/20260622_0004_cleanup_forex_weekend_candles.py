"""Remove Forex candles outside the Signapse weekly quote session.

Revision ID: 20260622_0004
Revises: 20260622_0003
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260622_0004"
down_revision: str | None = "20260622_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM market_data_candles
            WHERE asset_class = 'FOREX'
              AND (
                (
                  timeframe = '1d'
                  AND EXTRACT(
                    ISODOW FROM open_time AT TIME ZONE 'UTC'
                  ) IN (6, 7)
                )
                OR
                (
                  timeframe <> '1d'
                  AND (
                    EXTRACT(
                      ISODOW FROM open_time AT TIME ZONE 'America/New_York'
                    ) = 6
                    OR (
                      EXTRACT(
                        ISODOW FROM open_time AT TIME ZONE 'America/New_York'
                      ) = 5
                      AND (
                        open_time AT TIME ZONE 'America/New_York'
                      )::time >= TIME '17:00:00'
                    )
                    OR (
                      EXTRACT(
                        ISODOW FROM open_time AT TIME ZONE 'America/New_York'
                      ) = 7
                      AND (
                        open_time AT TIME ZONE 'America/New_York'
                      )::time < TIME '17:00:00'
                    )
                  )
                )
              )
            """
        )
    )


def downgrade() -> None:
    # Deleted provider candles cannot be reconstructed safely.
    pass
