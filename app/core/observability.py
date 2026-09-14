import asyncio
import json
import logging
import re
import socket
import ssl
import sys
import threading
import time
from collections import Counter
from collections.abc import Mapping
from contextvars import ContextVar, Token
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_provider_selection_counts: Counter[tuple[str, str]] = Counter()

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_SCOPE_KEY = "signapse_request_id"
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_REQUEST_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar(
    "signapse_request_context",
    default=None,
)
_ALLOWED_FIELDS = {
    "request_id",
    "job_id",
    "job_name",
    "operation",
    "method",
    "path",
    "status_code",
    "provider",
    "calendar_type",
    "upstream_host",
    "upstream_hosts",
    "upstream_operation",
    "failed_operation",
    "provider_symbol",
    "symbol",
    "symbols",
    "timeframe",
    "from",
    "to",
    "error_code",
    "failure_reason",
    "retryable",
    "exception_type",
    "root_exception_type",
    "root_error_code",
    "upstream_status",
    "upstream_code",
    "latency_ms",
    "duration_ms",
    "timeout_seconds",
    "failure_phase",
    "attempt",
    "max_attempts",
    "retry_in_ms",
    "shape",
    "columns",
    "failed_row_timestamp",
    "failed_row_reason",
    "action",
    "partial",
    "skipped_count",
    "skipped_rows",
    "open",
    "high",
    "low",
    "close",
    "suppressed_count",
    "dependency",
    "state",
    "close_code",
    "queue",
    "count",
    "count_direction",
    "eligible_slots_scanned",
    "page_count",
    "provider_call_count",
    "persisted_rows",
    "provider_rows",
    "returned_rows",
    "stop_reason",
    "calendar_ms",
    "db_ms",
    "provider_ms",
    "mode",
    "client_id",
    "attempted_count",
    "succeeded_count",
    "failed_count",
    "connection_failure_count",
    "invalid_event_count",
    "failure_reasons",
    "enrichment_candidates",
    "enrichment_rows",
}
_SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|password|secret)=([^&\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+[^:/\s]+)?://)([^@\s]+)@"),
)
_ERROR_CODE_RE = re.compile(r"\[(?:SSL|TLS):\s*([A-Z0-9_]+)\]")
_EXCEPTION_NAME_RE = re.compile(r"\b([A-Z][A-Za-z0-9]*(?:Error|Exception))\(")


def _redact_text(value: str) -> str:
    redacted = value
    for pattern in _SENSITIVE_TEXT_PATTERNS:
        if pattern.pattern.startswith("(?i)(postgres"):
            redacted = pattern.sub(r"\1[REDACTED]@", redacted)
        else:
            redacted = pattern.sub(r"\1=[REDACTED]", redacted)
    return redacted


def _safe_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(key): _safe_value(item)
            for key, item in value.items()
            if str(key) in _ALLOWED_FIELDS
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_safe_value(item) for item in value]
    return type(value).__name__


def request_id_from_headers(headers: list[tuple[bytes, bytes]]) -> str:
    inbound: str | None = None
    for name, value in headers:
        if name.lower() == REQUEST_ID_HEADER.lower().encode("ascii"):
            inbound = value.decode("ascii", errors="ignore")
            break
    return inbound if inbound is not None and _REQUEST_ID_RE.fullmatch(inbound) else str(uuid4())


def bind_context(**fields: object) -> Token[dict[str, Any] | None]:
    current = dict(_REQUEST_CONTEXT.get() or {})
    current.update({key: value for key, value in fields.items() if value is not None})
    return _REQUEST_CONTEXT.set(current)


def reset_context(token: Token[dict[str, Any] | None]) -> None:
    _REQUEST_CONTEXT.reset(token)


def current_context() -> dict[str, Any]:
    return dict(_REQUEST_CONTEXT.get() or {})


def current_request_id() -> str | None:
    value = (_REQUEST_CONTEXT.get() or {}).get("request_id")
    return value if isinstance(value, str) else None


def request_id_from_scope(scope: Scope) -> str | None:
    value = scope.get(REQUEST_ID_SCOPE_KEY)
    return value if isinstance(value, str) and _REQUEST_ID_RE.fullmatch(value) else None


def current_job_id() -> str | None:
    value = (_REQUEST_CONTEXT.get() or {}).get("job_id")
    return value if isinstance(value, str) else None


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
        }
        fields = getattr(record, "diagnostic_fields", {})
        if isinstance(fields, Mapping):
            payload.update(
                {key: _safe_value(value) for key, value in fields.items() if key in _ALLOWED_FIELDS}
            )
        if record.exc_info:
            exception_type = record.exc_info[0]
            if exception_type is not None:
                payload["exception_type"] = exception_type.__name__
            payload["traceback"] = _redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


def _logging_level(value: str) -> int:
    level = logging.getLevelName(value.upper())
    return level if isinstance(level, int) else logging.INFO


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(_logging_level(level))
    if any(getattr(handler, "_signapse_json", False) for handler in root.handlers):
        return
    try:
        handler = logging.StreamHandler(sys.stdout)
        handler._signapse_json = True  # type: ignore[attr-defined]
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
    except Exception as exc:
        logging.basicConfig(stream=sys.stderr, level=_logging_level(level))
        logging.getLogger("app.observability").error(
            "structured_logging_setup_failed: %s",
            type(exc).__name__,
        )


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: object,
) -> None:
    exc_info = fields.pop("exc_info", False)
    safe_fields = current_context()
    safe_fields.update({key: value for key, value in fields.items() if key in _ALLOWED_FIELDS})
    logger.log(
        level,
        event,
        extra={
            "event": event,
            "diagnostic_fields": {
                key: _safe_value(value)
                for key, value in safe_fields.items()
                if key in _ALLOWED_FIELDS
            },
        },
        exc_info=exc_info if isinstance(exc_info, bool) else False,
    )


class WarningLimiter:
    def __init__(self, window_seconds: float = 60.0) -> None:
        self._window_seconds = window_seconds
        self._events: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        with self._lock:
            previous = self._events.get(key)
            if previous is None or current - previous[0] >= self._window_seconds:
                suppressed = 0 if previous is None else previous[1]
                self._events[key] = (current, 0)
                return True, suppressed
            self._events[key] = (previous[0], previous[1] + 1)
            return False, 0


_warning_limiter = WarningLimiter()


def log_rate_limited_warning(
    logger: logging.Logger,
    event: str,
    key: str,
    **fields: object,
) -> None:
    allowed, suppressed = _warning_limiter.allow(key)
    if not allowed:
        return
    if suppressed:
        fields["suppressed_count"] = suppressed
    log_event(logger, logging.WARNING, event, **fields)


def classify_failure(exc: BaseException) -> tuple[str, bool]:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if isinstance(exc, socket.gaierror) or "name or service not known" in text:
        return "DNS_RESOLUTION_FAILED", True
    if isinstance(exc, ssl.SSLError) or "ssl" in name or "tls" in name:
        return "TLS_HANDSHAKE_FAILED", True
    if "connecttimeout" in name or "connect timeout" in text:
        return "CONNECT_TIMEOUT", True
    if "readtimeout" in name or "read timed out" in text:
        return "READ_TIMEOUT", True
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) or "timeout" in name:
        return "TIMEOUT", True
    status = getattr(exc, "status_code", None)
    if not isinstance(status, int):
        status = getattr(exc, "status", None)
    if not isinstance(status, int):
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if status == 429:
        return "RATE_LIMITED", True
    if isinstance(status, int) and 400 <= status < 500:
        return "UPSTREAM_HTTP_ERROR", False
    if isinstance(status, int) and status >= 500:
        return "REQUEST_FAILED", True
    if isinstance(exc, ConnectionResetError) or "connection reset" in text:
        return "CONNECTION_RESET", True
    if isinstance(exc, (ConnectionError, OSError)) or any(
        marker in name for marker in ("connection", "network", "transport")
    ):
        return "CONNECTION_FAILED", True
    if any(marker in name for marker in ("auth", "credential", "apikey", "keyunavailable")):
        return "AUTH_FAILED", False
    return "REQUEST_FAILED", False


def failure_metadata(exc: BaseException) -> dict[str, object]:
    reason = getattr(exc, "failure_reason", None)
    retryable = getattr(exc, "retryable", None)
    cause = exc.__cause__ or exc
    inferred_reason, inferred_retryable = classify_failure(cause)
    if cause is not exc and reason in {None, "REQUEST_FAILED", "DATABASE_QUERY_FAILED"}:
        reason = inferred_reason
    if cause is not exc and retryable is False and inferred_retryable:
        retryable = True
    exception_names = _EXCEPTION_NAME_RE.findall(str(cause))
    metadata: dict[str, object] = {
        "failure_reason": reason if isinstance(reason, str) else inferred_reason,
        "retryable": retryable if isinstance(retryable, bool) else inferred_retryable,
        "exception_type": type(cause).__name__,
        "root_exception_type": exception_names[-1] if exception_names else type(cause).__name__,
    }
    error_code = _ERROR_CODE_RE.search(str(cause))
    if error_code is not None:
        metadata["root_error_code"] = error_code.group(1)
    status = getattr(cause, "status_code", None)
    if not isinstance(status, int):
        status = getattr(cause, "status", None)
    if not isinstance(status, int):
        response = getattr(cause, "response", None)
        status = getattr(response, "status_code", None)
    if isinstance(status, int):
        metadata["upstream_status"] = status
    code = getattr(cause, "code", None)
    if isinstance(code, (str, int)):
        metadata["upstream_code"] = code
    for field in ("failed_row_timestamp", "failed_row_reason"):
        value = getattr(exc, field, None)
        if value is not None:
            metadata[field] = value
    details = getattr(exc, "diagnostic_fields", None)
    if isinstance(details, Mapping):
        metadata.update({key: value for key, value in details.items() if key in _ALLOWED_FIELDS})
    return metadata


def log_failure(
    logger: logging.Logger,
    event: str,
    exc: BaseException,
    **fields: object,
) -> None:
    level = fields.pop("level", logging.ERROR)
    include_traceback = fields.pop("include_traceback", True)
    if not isinstance(include_traceback, bool):
        include_traceback = True
    if not isinstance(level, int):
        level = logging.ERROR
    metadata = failure_metadata(exc)
    metadata.update(fields)
    metadata["exc_info"] = include_traceback
    log_event(logger, level, event, **metadata)


class DiagnosticContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger("app.request")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope_type = scope.get("type")
        if scope_type not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        request_id = request_id_from_headers(scope.get("headers", []))
        scope[REQUEST_ID_SCOPE_KEY] = request_id
        token = bind_context(request_id=request_id)
        started = time.perf_counter()
        status_code: int | None = None

        async def send_with_context(message: Message) -> None:
            nonlocal status_code
            message_type = message.get("type")
            if scope_type == "http" and message_type == "http.response.start":
                status_code = message.get("status")
                headers = list(message.get("headers", []))
                request_header = REQUEST_ID_HEADER.lower().encode("ascii")
                if not any(name.lower() == request_header for name, _ in headers):
                    headers.append((request_header, request_id.encode("ascii")))
                message = {**message, "headers": headers}
            elif scope_type == "websocket" and message_type == "websocket.accept":
                headers = list(message.get("headers", []))
                request_header = REQUEST_ID_HEADER.lower().encode("ascii")
                if not any(name.lower() == request_header for name, _ in headers):
                    headers.append((request_header, request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
        finally:
            log_event(
                self.logger,
                logging.INFO,
                "request_completed",
                operation="http_request" if scope_type == "http" else "websocket_lifecycle",
                method=scope.get("method"),
                path=scope.get("path"),
                status_code=status_code,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
            )
            reset_context(token)


def record_provider_selection(provider: str, mode: str) -> None:
    """Record low-cardinality provider/mode telemetry for internal diagnostics."""
    _provider_selection_counts[(provider, mode)] += 1


def provider_selection_counts() -> dict[tuple[str, str], int]:
    return dict(_provider_selection_counts)
