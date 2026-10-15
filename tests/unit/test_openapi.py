from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pytest import MonkeyPatch

from app.core.config import Settings, get_settings
from app.main import create_app


@pytest.fixture
def application() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(application: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.parametrize(
    ("path", "query_names", "required", "statuses"),
    [
        ("/health", set(), set(), {"200", "500"}),
        ("/ready", set(), set(), {"200", "503", "500"}),
        ("/v1/symbols", set(), set(), {"200", "503", "500"}),
        ("/v1/quotes", {"symbols", "provider"}, {"symbols"}, {"200", "400", "503", "500"}),
        (
            "/v1/candles",
            {"symbol", "timeframe", "from", "to", "limit", "count", "provider"},
            {"symbol", "timeframe"},
            {"200", "400", "503", "500"},
        ),
        (
            "/v1/historical-price",
            {"symbol", "at", "provider"},
            {"symbol", "at"},
            {"200", "400", "404", "503", "500"},
        ),
        (
            "/v1/economic-calendar",
            {"from", "to", "types", "currencies", "impact", "limit"},
            {"from", "to"},
            {"200", "400", "503", "500"},
        ),
    ],
)
async def test_openapi_describes_each_http_operation(
    client: AsyncClient, path: str, query_names: set[str], required: set[str], statuses: set[str]
) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    contract = response.json()
    assert contract["openapi"] == "3.1.0"
    operation = contract["paths"][path]["get"]
    assert operation["description"]
    assert operation["summary"]
    assert operation["tags"]
    assert operation["security"] == []
    parameters = operation["parameters"]
    query = {p["name"]: p for p in parameters if p["in"] == "query"}
    assert set(query) == query_names
    assert {name for name, p in query.items() if p["required"]} == required
    assert all(p["description"] and p["schema"] for p in query.values())
    assert any(p["in"] == "header" and p["name"] == "X-Request-ID" for p in parameters)
    assert set(operation["responses"]) == statuses
    for result in operation["responses"].values():
        assert result["description"]
        assert result["headers"]["X-Request-ID"]["schema"]["type"] == "string"
        assert result["content"]["application/json"]["schema"]


async def test_openapi_distinguishes_optional_output_from_required_nullable(
    client: AsyncClient,
) -> None:
    schemas = (await client.get("/openapi.json")).json()["components"]["schemas"]
    symbol = schemas["SymbolResponse"]
    assert "providerMappings" not in symbol["required"]
    mappings = symbol["properties"]["providerMappings"]
    assert mappings["type"] == "array"
    assert "anyOf" not in mappings
    event = schemas["EconomicCalendarEventResponse"]
    assert "currency" in event["required"]
    assert {branch["type"] for branch in event["properties"]["currency"]["anyOf"]} == {
        "string",
        "null",
    }
    assert "details" in schemas["ErrorDetail"]["required"]
    assert "null" in {
        branch["type"] for branch in schemas["ErrorDetail"]["properties"]["details"]["anyOf"]
    }
    for model, names in {
        "CandleResponse": ("openTime", "closeTime"),
        "QuoteResponse": ("receivedAt",),
        "HistoricalPriceResponse": ("pricedAt",),
        "EconomicCalendarEventResponse": (
            "scheduledAt",
            "firstSeenAt",
            "lastSeenAt",
            "lastChangedAt",
        ),
    }.items():
        for name in names:
            assert schemas[model]["properties"][name]["format"] == "date-time"
    for model, names in {
        "CandleResponse": ("open", "high", "low", "close", "volume"),
        "QuoteResponse": ("price",),
        "HistoricalPriceResponse": ("price",),
    }.items():
        for name in names:
            assert schemas[model]["properties"][name]["type"] == "string"


async def test_openapi_limits_and_revision_match_application_settings(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_CANDLES_PER_REQUEST", "17")
    monkeypatch.setenv("MAX_QUOTE_SYMBOLS", "3")
    monkeypatch.setenv("SOURCE_REVISION", "test-build-123")
    get_settings.cache_clear()
    try:
        application = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            contract = (await client.get("/openapi.json")).json()
            assert contract["x-build-revision"] == "test-build-123"
            assert (
                "at most 3 distinct symbols"
                in contract["paths"]["/v1/quotes"]["get"]["description"]
            )
            parameters = contract["paths"]["/v1/candles"]["get"]["parameters"]
            for parameter in parameters:
                if parameter["name"] in {"count", "limit"}:
                    assert parameter["schema"]["maximum"] == 17
            assert (await client.get("/openapi.json")).json() == contract
    finally:
        get_settings.cache_clear()


async def test_readiness_failure_matches_documented_body_and_headers(
    application: FastAPI, client: AsyncClient
) -> None:
    application.dependency_overrides.clear()
    # Readiness reads settings directly rather than through a dependency.
    from unittest.mock import patch

    with patch("app.api.routes_health.get_settings", return_value=Settings(database_url=None)):
        response = await client.get("/ready", headers={"X-Request-ID": "contract-test"})
    assert response.status_code == 503
    assert response.json()["status"] == "NOT_READY"
    assert "error" not in response.json()
    assert response.headers["X-Request-ID"] == "contract-test"
    contract = (await client.get("/openapi.json")).json()
    schema = contract["paths"]["/ready"]["get"]["responses"]["503"]["content"]["application/json"][
        "schema"
    ]
    assert schema["$ref"].endswith("/ReadyResponse")


async def test_calendar_csv_is_encoded_as_one_parameter(client: AsyncClient) -> None:
    operation = (await client.get("/openapi.json")).json()["paths"]["/v1/economic-calendar"]["get"]
    for parameter in operation["parameters"]:
        if parameter["name"] in {"types", "currencies", "impact"}:
            assert parameter["style"] == "form"
            assert parameter["explode"] is False


async def test_openapi_error_examples_keep_required_nullable_details(client: AsyncClient) -> None:
    contract = (await client.get("/openapi.json")).json()
    for item in contract["paths"].values():
        for response in item["get"]["responses"].values():
            example = response["content"]["application/json"].get("example", {})
            if "error" in example:
                assert "details" in example["error"]
                assert example["error"]["details"] is None
