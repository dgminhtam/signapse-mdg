from types import SimpleNamespace

import pytest

import app.providers.crawl4ai_markdown as provider_module
from app.providers.crawl4ai_markdown import (
    Crawl4AIError,
    Crawl4AIMarkdownProvider,
    CrawlMarkdownResult,
)


class FakeCrawler:
    def __init__(
        self,
        *,
        results: list[object] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.results = results or []
        self.error = error
        self.browser_config: object = None
        self.crawler_strategy: object = None
        self.run_config: object = None
        self.urls: list[str] | None = None
        self.closed = False

    async def __aenter__(self) -> FakeCrawler:
        return self

    async def __aexit__(self, *args: object) -> None:
        self.closed = True

    async def arun_many(self, *, urls: list[str], config: object) -> list[object]:
        self.urls = urls
        self.run_config = config
        if self.error is not None:
            raise self.error
        return self.results


def _install_fake(monkeypatch: pytest.MonkeyPatch, crawler: FakeCrawler) -> None:
    def build_crawler(*, config: object, crawler_strategy: object) -> FakeCrawler:
        crawler.browser_config = config
        crawler.crawler_strategy = crawler_strategy
        return crawler

    monkeypatch.setattr(provider_module, "AsyncWebCrawler", build_crawler)


async def test_crawl_provider_returns_batch_with_anti_bot_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    crawler = FakeCrawler(
        results=[
            SimpleNamespace(
                url="https://two.example/",
                success=True,
                markdown=SimpleNamespace(fit_markdown="# Two"),
            ),
            SimpleNamespace(
                url="https://one.example/",
                success=True,
                markdown=SimpleNamespace(fit_markdown="# One"),
            ),
        ]
    )
    _install_fake(monkeypatch, crawler)

    result = await Crawl4AIMarkdownProvider(
        proxy_url="http://user:secret@proxy.example:8080"
    ).crawl_fit_markdown(["https://one.example/", "https://two.example/"])

    assert result == [
        CrawlMarkdownResult(url="https://two.example/", content="# Two"),
        CrawlMarkdownResult(url="https://one.example/", content="# One"),
    ]
    assert crawler.urls == ["https://one.example/", "https://two.example/"]
    assert isinstance(crawler.browser_config, provider_module.BrowserConfig)
    assert isinstance(crawler.run_config, provider_module.CrawlerRunConfig)
    assert isinstance(
        crawler.run_config.markdown_generator,
        provider_module.DefaultMarkdownGenerator,
    )
    assert isinstance(
        crawler.run_config.markdown_generator.content_filter,
        provider_module.PruningContentFilter,
    )
    assert crawler.run_config.magic is True
    assert crawler.run_config.wait_until == "load"
    assert crawler.run_config.delay_before_return_html == 2.0
    assert crawler.run_config.max_retries == 0
    assert crawler.run_config.proxy_config.server == "http://proxy.example:8080"
    assert crawler.run_config.proxy_config.username == "user"
    assert crawler.browser_config.enable_stealth is True
    assert isinstance(
        crawler.crawler_strategy,
        provider_module.AsyncPlaywrightCrawlerStrategy,
    )
    assert isinstance(
        crawler.crawler_strategy.adapter,
        provider_module.UndetectedAdapter,
    )
    assert crawler.closed is True


async def test_crawl_provider_contains_unsuccessful_or_missing_content_per_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    crawler = FakeCrawler(
        results=[
            SimpleNamespace(
                url="https://ok.example/",
                success=True,
                markdown=SimpleNamespace(fit_markdown="# OK"),
            ),
            SimpleNamespace(
                url="https://failed.example/",
                success=False,
                markdown=None,
            ),
            SimpleNamespace(
                url="https://missing.example/",
                success=True,
                markdown=SimpleNamespace(fit_markdown=None),
            ),
        ]
    )
    _install_fake(monkeypatch, crawler)

    result = await Crawl4AIMarkdownProvider().crawl_fit_markdown(
        [
            "https://ok.example/",
            "https://failed.example/",
            "https://missing.example/",
        ]
    )

    assert result == [
        CrawlMarkdownResult(url="https://ok.example/", content="# OK"),
        CrawlMarkdownResult(url="https://failed.example/", content=None),
        CrawlMarkdownResult(url="https://missing.example/", content=None),
    ]
    assert crawler.closed is True


async def test_crawl_provider_returns_all_item_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    crawler = FakeCrawler(
        results=[
            SimpleNamespace(url="https://one.example/", success=False, markdown=None),
            SimpleNamespace(url="https://two.example/", success=False, markdown=None),
        ]
    )
    _install_fake(monkeypatch, crawler)

    result = await Crawl4AIMarkdownProvider().crawl_fit_markdown(
        ["https://one.example/", "https://two.example/"]
    )

    assert result == [
        CrawlMarkdownResult(url="https://one.example/", content=None),
        CrawlMarkdownResult(url="https://two.example/", content=None),
    ]


async def test_crawl_provider_maps_batch_error_and_closes_crawler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    crawler = FakeCrawler(error=RuntimeError("browser path and upstream body"))
    _install_fake(monkeypatch, crawler)

    with pytest.raises(Crawl4AIError):
        await Crawl4AIMarkdownProvider().crawl_fit_markdown(["https://example.com"])

    assert crawler.closed is True
