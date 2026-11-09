from typing import Annotated, Any

from fastapi import FastAPI
from pydantic import Field

from app.api.errors import ErrorResponse
from app.core.config import Settings
from app.core.observability import REQUEST_ID_HEADER

UtcTimestamp = Annotated[str, Field(json_schema_extra={"format": "date-time"})]
DecimalString = Annotated[
    str,
    Field(json_schema_extra={"pattern": r"^-?[0-9]+(?:\.[0-9]+)?$"}),
]
PRICE_DESCRIPTION = (
    "Fixed-point decimal string, rounded ROUND_HALF_UP and padded to the symbol's "
    "priceDisplayDecimals. Never a JSON number."
)
UTC_QUERY_SCHEMA = {"type": "string", "format": "date-time"}
UTC_QUERY_DESCRIPTION = "UTC timestamp ending in Z or +00:00; surrounding whitespace is trimmed."
RAW_QUERY_DESCRIPTION = (
    "For repeated query parameters the last value is used, except provider, which must occur "
    "at most once. Unknown query parameters are ignored unless explicitly rejected below. "
    "Custom parsing errors use HTTP 400, not FastAPI's 422 validation envelope. "
    "Dependency failures can return 503 before query parsing."
)


def query_parameter(
    name: str,
    description: str,
    schema: dict[str, Any],
    *,
    required: bool = False,
    example: Any,
) -> dict[str, Any]:
    return {
        "name": name,
        "in": "query",
        "required": required,
        "description": description,
        "schema": schema,
        "example": example,
        **({"style": "form", "explode": False} if schema.get("type") == "array" else {}),
    }


SYMBOL_PARAMETER = query_parameter(
    "symbol",
    "Case-sensitive canonical symbol from /v1/symbols. Trimmed; missing, blank, unknown or "
    "disabled symbols produce UNSUPPORTED_SYMBOL.",
    {"type": "string", "minLength": 1},
    required=True,
    example="BTC/USDT",
)
PROVIDER_PARAMETER = query_parameter(
    "provider",
    "Optional request-wide, case-sensitive Provider Identifier from the symbol's providerMappings. "
    "Omission selects its Default Provider. Empty/whitespace-only or repeated values return "
    "400 INVALID_PROVIDER. Nonblank values are matched exactly, without trimming or case folding. "
    "An unmapped value produces UNSUPPORTED_PROVIDER (per-symbol in a quotes 200 response, "
    "otherwise HTTP 400). The selected provider never changes automatically on failure.",
    {"type": "string", "minLength": 1},
    example="YFINANCE",
)


def error_response(description: str, code: str, message: str) -> dict[str, Any]:
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {
            "application/json": {
                "example": {"error": {"code": code, "message": message, "details": None}}
            }
        },
    }


DATABASE_UNAVAILABLE_RESPONSE = error_response(
    "DATABASE_UNAVAILABLE: required registry/persistence access is unavailable or inconsistent.",
    "DATABASE_UNAVAILABLE",
    "The requested database-backed capability is temporarily unavailable.",
)
MARKET_DATA_UNAVAILABLE_RESPONSE = error_response(
    "DATABASE_UNAVAILABLE for persistence/registry failure, or PROVIDER_UNAVAILABLE for "
    "upstream timeout, rate limit, configuration, transport or normalization failure. "
    "No automatic cross-provider fallback; these failures are not empty successful results.",
    "PROVIDER_UNAVAILABLE",
    "The market data provider is temporarily unavailable.",
)
INTERNAL_ERROR_RESPONSE = error_response(
    "INTERNAL_ERROR: unexpected failure, with a sanitized message and no provider/DB secrets.",
    "INTERNAL_ERROR",
    "The gateway encountered an unexpected error.",
)


def configure_openapi(application: FastAPI, settings: Settings) -> None:
    original_openapi = application.openapi

    def openapi() -> dict[str, Any]:
        if application.openapi_schema is not None:
            return application.openapi_schema
        schema = original_openapi()
        schema["x-build-revision"] = settings.source_revision.strip() or "unknown"
        for item in schema["paths"].values():
            for method, operation in item.items():
                if method not in {
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "head",
                    "options",
                    "trace",
                }:
                    continue
                operation["security"] = []
                operation.setdefault("parameters", []).append(
                    {
                        "name": REQUEST_ID_HEADER,
                        "in": "header",
                        "required": False,
                        "description": "Optional correlation ID. The first header value is used. "
                        "ASCII letters/digits and . _ - of length 1..128 are echoed; missing or "
                        "unsafe values are replaced with a generated UUID, not rejected.",
                        "schema": {"type": "string"},
                        "example": "trace-123",
                    }
                )
                for response in operation["responses"].values():
                    example = response.get("content", {}).get("application/json", {}).get("example")
                    # FastAPI omits None in route metadata; the error serializer emits this key.
                    if isinstance(example, dict) and "error" in example:
                        example["error"].setdefault("details", None)
                    response.setdefault("headers", {})[REQUEST_ID_HEADER] = {
                        "description": "Accepted client correlation ID or a generated UUID.",
                        "schema": {"type": "string", "pattern": r"^[A-Za-z0-9._-]{1,128}$"},
                        "example": "trace-123",
                    }

        # These limits depend on the producer's configuration, not import-time defaults.
        quotes = schema["paths"]["/v1/quotes"]["get"]
        quotes["description"] += (
            f" This instance accepts at most {settings.max_quote_symbols} distinct symbols. "
            f"Cached quotes are reused up to {settings.quote_cache_ttl_seconds:g} seconds; "
            f"on refresh failure they may be served up to {settings.quote_stale_after_seconds:g} "
            "seconds old. receivedAt is gateway receipt time, not exchange trade time."
        )
        candles = schema["paths"]["/v1/candles"]["get"]
        for parameter in candles["parameters"]:
            if parameter["name"] in {"limit", "count"}:
                parameter["schema"]["maximum"] = settings.max_candles_per_request
        candles["description"] += (
            f" This instance allows at most {settings.max_candles_per_request} slots "
            "per range/limit "
            "request or snapshots per count request. Range size uses a conservative slot count "
            "before session filtering. "
            f"Forming snapshots have a {settings.candle_forming_cache_ttl_seconds:g}-second cache "
            "TTL and expire no later than closeTime; failed refresh returns 503 rather than "
            "an expired snapshot."
        )
        return schema

    application.openapi = openapi  # type: ignore[method-assign]
