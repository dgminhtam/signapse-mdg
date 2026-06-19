class DatabaseUnavailableError(Exception):
    """Raised when a database-backed capability cannot be served."""


class QuoteRequestError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ProviderUnavailableError(Exception):
    """Raised when an upstream provider request cannot be completed."""
