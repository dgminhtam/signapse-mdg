from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import app.main as main_module
from app.api.routes_crawl import get_crawl_provider, router
from app.providers.crawl4ai_markdown import Crawl4AIError, CrawlMarkdownResult


class StubCrawlProvider:
    def __init__(
        self,
        results: list[CrawlMarkdownResult] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.results = results or []
        self.error = error
        self.urls: list[str] | None = None

    async def crawl_fit_markdown(self, urls: list[str]) -> list[CrawlMarkdownResult]:
        self.urls = urls
        if self.error is not None:
            raise self.error
        return self.results


@pytest.fixture
def application() -> FastAPI:
    application = FastAPI()
    application.include_router(router)
    return application


@pytest.fixture
async def client(application: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    application.dependency_overrides.clear()


async def test_crawl_api_returns_correlated_success_and_failure_results(
    application: FastAPI,
    client: AsyncClient,
) -> None:
    provider = StubCrawlProvider(
        results=[
            CrawlMarkdownResult(url="https://two.example/", content=None),
            CrawlMarkdownResult(url="https://one.example/", content="# One"),
        ]
    )
    application.dependency_overrides[get_crawl_provider] = lambda: provider

    response = await client.post(
        "/crawl",
        json={"urls": ["https://one.example", "https://two.example"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {
                "url": "https://two.example/",
                "content": None,
                "error": "Crawl failed.",
            },
            {
                "url": "https://one.example/",
                "content": "# One",
                "error": None,
            },
        ]
    }
    assert provider.urls == ["https://one.example/", "https://two.example/"]


async def test_crawl_api_returns_http_200_when_all_urls_fail(
    application: FastAPI,
    client: AsyncClient,
) -> None:
    provider = StubCrawlProvider(
        results=[
            CrawlMarkdownResult(url="https://one.example/", content=None),
            CrawlMarkdownResult(url="https://two.example/", content=None),
        ]
    )
    application.dependency_overrides[get_crawl_provider] = lambda: provider

    response = await client.post(
        "/crawl",
        json={"urls": ["https://one.example", "https://two.example"]},
    )

    assert response.status_code == 200
    assert all(item["error"] == "Crawl failed." for item in response.json()["results"])
    assert all(item["content"] is None for item in response.json()["results"])


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"urls": []},
        {"urls": [f"https://{index}.example.com" for index in range(11)]},
        {"urls": ["file:///tmp/page.html"]},
        {"urls": ["not-a-url"]},
        {"url": "https://example.com"},
        {"urls": ["https://example.com"], "threshold": 0.4},
    ],
)
async def test_crawl_api_rejects_invalid_or_configurable_requests(
    client: AsyncClient,
    body: dict[str, object],
) -> None:
    response = await client.post("/crawl", json=body)

    assert response.status_code == 422


async def test_crawl_api_sanitizes_request_wide_provider_failure(
    application: FastAPI,
    client: AsyncClient,
) -> None:
    provider = StubCrawlProvider(error=Crawl4AIError("browser path and upstream body"))
    application.dependency_overrides[get_crawl_provider] = lambda: provider

    response = await client.post("/crawl", json={"urls": ["https://example.com"]})

    assert response.status_code == 502
    assert response.json() == {"detail": "Crawl failed."}
    assert "browser path" not in response.text
    assert "upstream body" not in response.text


def test_crawl_route_is_always_registered() -> None:
    application = main_module.create_app()

    assert "/crawl" in application.openapi()["paths"]
    assert "/internal/crawl" not in application.openapi()["paths"]
