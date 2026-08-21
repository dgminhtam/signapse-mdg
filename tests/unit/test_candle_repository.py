from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.db.repositories import PostgresCandleRepository
from app.domain.candles import Candle
from app.domain.symbols import SupportedSymbol

BTC = SupportedSymbol("BTC/USD", "CRYPTO", "TWELVE_DATA", "BTC/USD", True, 2)
START = datetime(2026, 6, 19, tzinfo=UTC)


def make_complete_candle(open_time: datetime) -> Candle:
    return Candle(
        symbol=BTC.symbol,
        asset_class=BTC.asset_class,
        provider=BTC.provider,
        provider_symbol=BTC.provider_symbol,
        timeframe="1m",
        open_time=open_time,
        close_time=open_time + timedelta(minutes=1) - timedelta(milliseconds=1),
        open=Decimal("10"),
        high=Decimal("11"),
        low=Decimal("9"),
        close=Decimal("10.5"),
        volume=Decimal("12"),
        complete=True,
    )


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[object] = []

    async def execute(self, statement: object) -> None:
        self.statements.append(statement)


class FakeTransaction:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> FakeSession:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        return None


class FakeSessionFactory:
    def __init__(self) -> None:
        self.session = FakeSession()

    def begin(self) -> FakeTransaction:
        return FakeTransaction(self.session)


@pytest.mark.asyncio
async def test_repository_upsert_complete_executes_one_bulk_statement() -> None:
    factory = FakeSessionFactory()
    repository = PostgresCandleRepository(factory)  # type: ignore[arg-type]

    await repository.upsert_complete(
        [
            make_complete_candle(START),
            make_complete_candle(START + timedelta(minutes=1)),
        ]
    )

    assert len(factory.session.statements) == 1
