from fastapi import FastAPI

from app.api.errors import database_unavailable_handler, quote_request_error_handler
from app.api.routes_health import router as health_router
from app.api.routes_quotes import router as quotes_router
from app.api.routes_symbols import router as symbols_router
from app.domain.errors import DatabaseUnavailableError, QuoteRequestError


def create_app() -> FastAPI:
    application = FastAPI(
        title="Signapse Market Data Gateway",
        version="0.1.0",
    )
    application.add_exception_handler(
        DatabaseUnavailableError,
        database_unavailable_handler,
    )
    application.add_exception_handler(QuoteRequestError, quote_request_error_handler)
    application.include_router(health_router)
    application.include_router(symbols_router)
    application.include_router(quotes_router)
    return application


app = create_app()
