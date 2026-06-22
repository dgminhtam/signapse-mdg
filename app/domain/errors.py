class DatabaseUnavailableError(Exception):
    """Raised when a database-backed capability cannot be served."""


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


class ProviderUnavailableError(Exception):
    """Raised when an upstream provider request cannot be completed."""


class StreamRequestError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
