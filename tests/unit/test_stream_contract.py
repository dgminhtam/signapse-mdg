from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.api.routes_stream import stream_event_payload
from app.core.config import Settings
from app.domain.candles import Candle
from app.domain.errors import StreamRequestError
from app.domain.quotes import Quote
from app.domain.streams import StatusEvent, StreamCandle, StreamQuote
from app.services.stream_manager import parse_stream_request

NOW = datetime(2026, 6, 19, 10, 30, tzinfo=UTC)


def test_parse_stream_request_deduplicates_symbols_and_accepts_supported_timeframe() -> None:
    request = parse_stream_request(" ETH/USD, BTC/USD,ETH/USD ", "1m", 10)

    assert request.symbols == ("ETH/USD", "BTC/USD")
    assert request.timeframe == "1m"


@pytest.mark.parametrize(
    ("symbols", "timeframe", "max_symbols", "code"),
    [
        (None, "1m", 10, "INVALID_SYMBOLS"),
        (" , ", "1m", 10, "INVALID_SYMBOLS"),
        ("BTC/USD,ETH/USD", "1m", 1, "TOO_MANY_SYMBOLS"),
        ("BTC/USD", None, 10, "UNSUPPORTED_TIMEFRAME"),
        ("BTC/USD", "2m", 10, "UNSUPPORTED_TIMEFRAME"),
        ("BTC/USD", "1w", 10, "UNSUPPORTED_TIMEFRAME"),
        ("BTC/USD", "1mo", 10, "UNSUPPORTED_TIMEFRAME"),
    ],
)
def test_parse_stream_request_rejects_invalid_contract(
    symbols: str | None,
    timeframe: str | None,
    max_symbols: int,
    code: str,
) -> None:
    with pytest.raises(StreamRequestError) as exc_info:
        parse_stream_request(symbols, timeframe, max_symbols)

    assert exc_info.value.code == code


def test_stream_settings_have_valid_defaults_and_constraints() -> None:
    settings = Settings()

    assert settings.binance_ws_base_url == "wss://stream.binance.com:9443"
    assert settings.provider_ws_reconnect_delay_seconds == 5
    assert settings.stream_client_queue_capacity == 256
    assert settings.stream_provider_queue_capacity == 1024
    assert settings.stream_persistence_queue_capacity == 256
    assert settings.stream_idle_grace_seconds == 5
    assert settings.stream_freshness_check_seconds == 1

    with pytest.raises(ValueError):
        Settings(stream_client_queue_capacity=0)
    with pytest.raises(ValueError):
        Settings(stream_freshness_check_seconds=0)


def test_stream_quote_payload_is_minimal_and_fixed_point() -> None:
    quote = Quote(
        "BTC/USD",
        "CRYPTO",
        "TWELVE_DATA",
        "BTC/USD",
        Decimal("1E-8"),
        None,
        None,
        NOW,
    )

    payload = stream_event_payload(StreamQuote(quote))

    assert payload == {
        "type": "quote",
        "symbol": "BTC/USD",
        "price": "0.00000001",
        "receivedAt": "2026-06-19T10:30:00Z",
    }


def test_stream_candle_payload_is_minimal_and_fixed_point() -> None:
    candle = Candle(
        "BTC/USD",
        "CRYPTO",
        "TWELVE_DATA",
        "BTC/USD",
        "1m",
        NOW,
        NOW + timedelta(minutes=1) - timedelta(milliseconds=1),
        Decimal("10.00"),
        Decimal("11.00"),
        Decimal("9.00"),
        Decimal("10.50"),
        Decimal("0E-8"),
        False,
    )

    payload = stream_event_payload(StreamCandle(candle, NOW + timedelta(seconds=1)))

    assert set(payload) == {
        "type",
        "symbol",
        "timeframe",
        "openTime",
        "closeTime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "complete",
        "receivedAt",
    }
    assert "provider" not in payload
    assert payload["volume"] == "0.00000000"
    assert payload["receivedAt"] == "2026-06-19T10:30:01Z"


def test_status_event_payload_includes_error_fields_only_for_error() -> None:
    subscribed = stream_event_payload(
        StatusEvent("SUBSCRIBED", ("BTC/USD",), ("quote", "candle"), NOW)
    )
    market_closed = stream_event_payload(
        StatusEvent("MARKET_CLOSED", ("EUR/USD",), ("candle",), NOW)
    )
    error = stream_event_payload(
        StatusEvent(
            "ERROR",
            ("BTC/USD",),
            ("quote",),
            NOW,
            "PROVIDER_UNAVAILABLE",
            "Provider unavailable.",
        )
    )

    assert subscribed == {
        "type": "status",
        "state": "SUBSCRIBED",
        "symbols": ["BTC/USD"],
        "channels": ["quote", "candle"],
        "observedAt": "2026-06-19T10:30:00Z",
    }
    assert market_closed == {
        "type": "status",
        "state": "MARKET_CLOSED",
        "symbols": ["EUR/USD"],
        "channels": ["candle"],
        "observedAt": "2026-06-19T10:30:00Z",
    }
    assert error["code"] == "PROVIDER_UNAVAILABLE"
    assert error["message"] == "Provider unavailable."
