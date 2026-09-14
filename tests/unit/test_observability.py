import json
import logging
import socket
import ssl
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import routes_health
from app.core.observability import (
    JsonFormatter,
    WarningLimiter,
    classify_failure,
    failure_metadata,
    log_failure,
)
from app.domain.errors import ProviderUnavailableError
from app.main import app, create_app
from app.providers.twelvedata_keys import TwelveDataKeyUnavailableError


@pytest.mark.asyncio
async def test_request_id_is_preserved_and_echoed() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health", headers={"X-Request-ID": "trace-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "trace-123"


@pytest.mark.asyncio
async def test_unsafe_request_id_is_replaced() -> None:
    inbound = "x" * 129
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health", headers={"X-Request-ID": inbound})

    request_id = response.headers["X-Request-ID"]
    assert response.status_code == 200
    assert request_id != inbound
    assert len(request_id) == 36


def test_json_log_redacts_unknown_sensitive_fields_and_traceback() -> None:
    logger = logging.getLogger("test.observability")
    try:
        raise RuntimeError("postgresql://user:secret@database:5432/app")
    except RuntimeError as exc:
        log_failure(
            logger,
            "provider_request_failed",
            exc,
            provider="YFINANCE",
            api_key="secret-key",
        )

    record = logging.LogRecord(
        name="test.observability",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="provider_request_failed",
        args=(),
        exc_info=None,
    )
    record.event = "provider_request_failed"
    record.diagnostic_fields = {"provider": "YFINANCE", "api_key": "secret-key"}
    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "provider_request_failed"
    assert payload["provider"] == "YFINANCE"
    assert "api_key" not in payload
    assert "secret-key" not in json.dumps(payload)


def test_timeout_failure_is_retryable() -> None:
    try:
        raise TimeoutError
    except TimeoutError as cause:
        try:
            raise ProviderUnavailableError from cause
        except ProviderUnavailableError as error:
            assert classify_failure(cause) == ("TIMEOUT", True)
            assert failure_metadata(error)["failure_reason"] == "TIMEOUT"
            assert failure_metadata(error)["retryable"] is True


def test_transport_failure_taxonomy_is_specific() -> None:
    error = ssl.SSLError("SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING]'))")
    assert classify_failure(error) == (
        "TLS_HANDSHAKE_FAILED",
        True,
    )
    metadata = failure_metadata(error)
    assert metadata["root_exception_type"] == "SSLEOFError"
    assert metadata["root_error_code"] == "UNEXPECTED_EOF_WHILE_READING"
    assert classify_failure(socket.gaierror(-2, "Name or service not known")) == (
        "DNS_RESOLUTION_FAILED",
        True,
    )


def test_known_failure_can_omit_traceback() -> None:
    records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger("test.observability.compact")
    handler = CaptureHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    try:
        log_failure(
            logger,
            "provider_request_failed",
            ssl.SSLError("[SSL: UNEXPECTED_EOF_WHILE_READING]"),
            include_traceback=False,
        )
    finally:
        logger.removeHandler(handler)

    assert len(records) == 1
    payload = json.loads(JsonFormatter().format(records[0]))
    assert payload["failure_reason"] == "TLS_HANDSHAKE_FAILED"
    assert "traceback" not in payload


def test_upstream_rate_limit_keeps_status_and_taxonomy() -> None:
    metadata = failure_metadata(TwelveDataKeyUnavailableError(status_code=429))

    assert metadata["failure_reason"] == "RATE_LIMITED"
    assert metadata["retryable"] is True
    assert metadata["upstream_status"] == 429


def test_warning_limiter_reports_suppressed_events() -> None:
    limiter = WarningLimiter(window_seconds=60)

    assert limiter.allow("queue", now=10) == (True, 0)
    assert limiter.allow("queue", now=11) == (False, 0)
    assert limiter.allow("queue", now=12) == (False, 0)
    assert limiter.allow("queue", now=70) == (True, 2)


class _ReadySession:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def __aenter__(self) -> _ReadySession:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, _statement: object) -> None:
        if self.error is not None:
            raise self.error


class _ReadySessionFactory:
    def __init__(self, session: _ReadySession) -> None:
        self.session = session

    def __call__(self) -> _ReadySession:
        return self.session


@pytest.mark.asyncio
async def test_ready_returns_not_ready_without_database_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import Settings

    monkeypatch.setattr(routes_health, "get_settings", lambda: Settings(database_url=None))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "NOT_READY"


@pytest.mark.asyncio
async def test_ready_returns_ready_after_database_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import Settings

    monkeypatch.setattr(
        routes_health,
        "get_settings",
        lambda: Settings(database_url="postgresql+asyncpg://user:password@db/app"),
    )
    monkeypatch.setattr(
        routes_health,
        "build_session_factory",
        lambda _settings: (object(), _ReadySessionFactory(_ReadySession())),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "READY"
    ready_time = datetime.fromisoformat(response.json()["time"])
    assert ready_time.utcoffset() == UTC.utcoffset(ready_time)


@pytest.mark.asyncio
async def test_ready_returns_not_ready_when_database_probe_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import Settings

    monkeypatch.setattr(
        routes_health,
        "get_settings",
        lambda: Settings(database_url="postgresql+asyncpg://user:password@db/app"),
    )
    monkeypatch.setattr(
        routes_health,
        "build_session_factory",
        lambda _settings: (
            object(),
            _ReadySessionFactory(_ReadySession(ConnectionError("database unavailable"))),
        ),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "NOT_READY"
    assert "database unavailable" not in response.text


@pytest.mark.asyncio
async def test_unexpected_http_error_is_sanitized_and_correlated() -> None:
    test_app = create_app()

    async def fail() -> None:
        raise RuntimeError("secret upstream payload")

    test_app.add_api_route("/test/internal-error", fail)
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test/internal-error", headers={"X-Request-ID": "trace-500"})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret upstream payload" not in response.text
    assert response.headers["X-Request-ID"] == "trace-500"
