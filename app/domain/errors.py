class _DiagnosticUnavailableError(Exception):
    def __init__(
        self,
        message: str | None = None,
        *,
        failure_reason: str,
        retryable: bool = False,
        operation: str | None = None,
        provider: str | None = None,
        provider_symbol: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        request_from: object | None = None,
        request_to: object | None = None,
        failed_row_timestamp: object | None = None,
        failed_row_reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_reason = failure_reason
        self.retryable = retryable
        self.operation = operation
        self.provider = provider
        self.provider_symbol = provider_symbol
        self.symbol = symbol
        self.timeframe = timeframe
        self.request_from = request_from
        self.request_to = request_to
        self.failed_row_timestamp = failed_row_timestamp
        self.failed_row_reason = failed_row_reason


class DatabaseUnavailableError(_DiagnosticUnavailableError):
    """Raised when a database-backed capability cannot be served."""

    def __init__(
        self,
        message: str | None = None,
        *,
        failure_reason: str = "DATABASE_QUERY_FAILED",
        retryable: bool = False,
        operation: str | None = None,
    ) -> None:
        super().__init__(
            message,
            failure_reason=failure_reason,
            retryable=retryable,
            operation=operation,
        )


class QuoteRequestError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class CandleRequestError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class EconomicCalendarRequestError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class HistoricalPriceNotFoundError(Exception):
    """Raised when no candle can price the requested historical instant."""


class ProviderUnavailableError(_DiagnosticUnavailableError):
    """Raised when an upstream provider request cannot be completed."""

    def __init__(
        self,
        message: str | None = None,
        *,
        failure_reason: str = "REQUEST_FAILED",
        retryable: bool = False,
        operation: str | None = None,
        provider: str | None = None,
        provider_symbol: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        request_from: object | None = None,
        request_to: object | None = None,
        failed_row_timestamp: object | None = None,
        failed_row_reason: str | None = None,
    ) -> None:
        super().__init__(
            message,
            failure_reason=failure_reason,
            retryable=retryable,
            operation=operation,
            provider=provider,
            provider_symbol=provider_symbol,
            symbol=symbol,
            timeframe=timeframe,
            request_from=request_from,
            request_to=request_to,
            failed_row_timestamp=failed_row_timestamp,
            failed_row_reason=failed_row_reason,
        )


class ProviderSelectionError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class StreamRequestError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
