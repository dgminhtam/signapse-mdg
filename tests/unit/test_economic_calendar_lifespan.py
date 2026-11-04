from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.core.config import Settings
from app.core.cronjob import Cronjob
from tests.unit.test_stream_lifespan import LifespanProvider


class FakeCalendar:
    def __init__(self, **kwargs):
        self.started = False
        self.closed = False

    async def start(self):
        self.started = True

    async def close(self):
        self.closed = True


class FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class FakeEconomicCalendarCronjob(Cronjob):
    def __init__(self, service: object, *, interval_seconds: float) -> None:
        del service
        super().__init__(
            name="economic-calendar-refresh",
            interval_seconds=interval_seconds,
            run_on_start=True,
        )

    async def run_once(self) -> None:
        return


def _stub_stream_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main_module,
        "build_binance_spot_stream_provider",
        lambda *args: LifespanProvider(),
    )
    monkeypatch.setattr(
        main_module,
        "build_twelvedata_market_data_stream_provider",
        lambda *args, **kwargs: LifespanProvider(),
    )
    monkeypatch.setattr(
        main_module,
        "build_yfinance_market_data_stream_provider",
        lambda *args, **kwargs: LifespanProvider(),
    )


def test_lifespan_registers_economic_calendar_cronjob_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = FakeEngine()
    _stub_stream_providers(monkeypatch)
    monkeypatch.setattr(main_module, "MT5CalendarProvider", FakeCalendar)
    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: Settings(
            database_url="postgresql+asyncpg://db",
            economic_calendar_poll_seconds=12,
            mt5_token_file=Path("synthetic"),
        ),
    )
    monkeypatch.setattr(main_module, "build_session_factory", lambda settings: (engine, object()))
    monkeypatch.setattr(main_module, "EconomicCalendarFetchCronjob", FakeEconomicCalendarCronjob)
    application = main_module.create_app()

    with TestClient(application) as client:
        assert client.get("/health").status_code == 200
        statuses = application.state.cronjob_manager.status()
        assert [(status.name, status.enabled, status.run_count) for status in statuses] == [
            ("economic-calendar-refresh", True, 1)
        ]

    assert engine.disposed is True
    assert application.state.mt5_calendar_provider.started
    assert application.state.mt5_calendar_provider.closed


def test_lifespan_skips_economic_calendar_cronjob_when_poll_seconds_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = FakeEngine()
    _stub_stream_providers(monkeypatch)
    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: Settings(database_url="postgresql+asyncpg://db", economic_calendar_poll_seconds=0),
    )
    monkeypatch.setattr(main_module, "build_session_factory", lambda settings: (engine, object()))
    application = main_module.create_app()

    with TestClient(application) as client:
        assert client.get("/health").status_code == 200
        assert application.state.cronjob_manager.status() == []


def test_lifespan_skips_economic_calendar_cronjob_without_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_stream_providers(monkeypatch)
    monkeypatch.setattr(main_module, "get_settings", lambda: Settings(database_url=None))
    monkeypatch.setattr(main_module, "build_session_factory", lambda settings: None)
    application = main_module.create_app()

    with TestClient(application) as client:
        assert client.get("/health").status_code == 200
        assert application.state.cronjob_manager.status() == []
