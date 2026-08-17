from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.api.routes_stream import stream_event_payload
from app.core.config import Settings
from app.domain.errors import StreamRequestError
from app.domain.quotes import Quote
from app.domain.streams import StatusEvent, StreamQuote
from app.services.stream_manager import parse_stream_request

NOW = datetime(2026, 6, 19, 10, 30, tzinfo=UTC)


def test_parse_stream_request_deduplicates_symbols_and_accepts_provider() -> None:
    request = parse_stream_request(" ETH/USD, BTC/USD,ETH/USD ", None, 10, "YFINANCE")

    assert request.symbols == ("ETH/USD", "BTC/USD")
    assert request.provider == "YFINANCE"
    assert not hasattr(request, "timeframe")


@pytest.mark.parametrize("timeframe", ["", "1m", "1w"])
def test_parse_stream_request_rejects_any_timeframe_presence(timeframe: str) -> None:
    with pytest.raises(StreamRequestError) as exc_info:
        parse_stream_request("BTC/USD", timeframe, 10)

    assert exc_info.value.code == "TIMEFRAME_NOT_ALLOWED"


@pytest.mark.parametrize(
    ("symbols", "max_symbols", "code"),
    [
        (None, 10, "INVALID_SYMBOLS"),
        (" , ", 10, "INVALID_SYMBOLS"),
        ("BTC/USD,ETH/USD", 1, "TOO_MANY_SYMBOLS"),
    ],
)
def test_parse_stream_request_rejects_invalid_symbols(
    symbols: str | None,
    max_symbols: int,
    code: str,
) -> None:
    with pytest.raises(StreamRequestError) as exc_info:
        parse_stream_request(symbols, None, max_symbols)

    assert exc_info.value.code == code


def test_stream_settings_have_valid_defaults_and_constraints() -> None:
    settings = Settings()

    assert settings.binance_ws_base_url == "wss://stream.binance.com:9443"
    assert settings.provider_ws_reconnect_delay_seconds == 5
    assert settings.stream_client_queue_capacity == 256
    assert settings.stream_provider_queue_capacity == 1024
    assert settings.candle_forming_cache_ttl_seconds == 5
    assert settings.stream_idle_grace_seconds == 5
    assert settings.stream_freshness_check_seconds == 1

    with pytest.raises(ValueError):
        Settings(stream_client_queue_capacity=0)
    with pytest.raises(ValueError):
        Settings(stream_freshness_check_seconds=0)
    with pytest.raises(ValueError):
        Settings(candle_forming_cache_ttl_seconds=0)


def test_stream_quote_payload_is_minimal_and_display_formatted() -> None:
    quote = Quote(
        "XAU/USD",
        "COMMODITY",
        "TWELVE_DATA",
        "XAU/USD",
        Decimal("2934.5678"),
        None,
        None,
        NOW,
    )

    payload = stream_event_payload(StreamQuote(quote), {"XAU/USD": 2})

    assert payload == {
        "type": "quote",
        "symbol": "XAU/USD",
        "price": "2934.57",
        "receivedAt": "2026-06-19T10:30:00Z",
    }
    assert quote.price == Decimal("2934.5678")


def test_status_event_payload_is_quote_only_and_error_is_sanitized() -> None:
    subscribed = stream_event_payload(
        StatusEvent("SUBSCRIBED", ("BTC/USD",), ("quote",), NOW),
        {},
    )
    error = stream_event_payload(
        StatusEvent(
            "ERROR",
            ("BTC/USD",),
            ("quote",),
            NOW,
            "PROVIDER_UNAVAILABLE",
            "Provider unavailable.",
        ),
        {},
    )

    assert subscribed == {
        "type": "status",
        "state": "SUBSCRIBED",
        "symbols": ["BTC/USD"],
        "channels": ["quote"],
        "observedAt": "2026-06-19T10:30:00Z",
    }
    assert error["code"] == "PROVIDER_UNAVAILABLE"
    assert error["message"] == "Provider unavailable."
