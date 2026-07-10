from dataclasses import dataclass

from crawl4ai import (  # type: ignore[import-untyped]
    AsyncWebCrawler,
    BrowserConfig,
    CrawlerRunConfig,
    UndetectedAdapter,
)
from crawl4ai.async_crawler_strategy import (  # type: ignore[import-untyped]
    AsyncPlaywrightCrawlerStrategy,
)
from crawl4ai.content_filter_strategy import (  # type: ignore[import-untyped]
    PruningContentFilter,
)
from crawl4ai.markdown_generation_strategy import (  # type: ignore[import-untyped]
    DefaultMarkdownGenerator,
)


class Crawl4AIError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CrawlMarkdownResult:
    url: str
    content: str | None


class Crawl4AIMarkdownProvider:
    async def crawl_fit_markdown(self, urls: list[str]) -> list[CrawlMarkdownResult]:
        run_config = CrawlerRunConfig(
            markdown_generator=DefaultMarkdownGenerator(
                content_filter=PruningContentFilter()
            ),
            magic=True,
            wait_until="load",
            delay_before_return_html=2.0,
        )
        try:
            browser_config = BrowserConfig(enable_stealth=True)
            async with AsyncWebCrawler(
                config=browser_config,
                crawler_strategy=AsyncPlaywrightCrawlerStrategy(
                    browser_config=browser_config,
                    browser_adapter=UndetectedAdapter(),
                ),
            ) as crawler:
                results = await crawler.arun_many(urls=urls, config=run_config)

            normalized = []
            for result in results:
                fit_markdown = getattr(
                    getattr(result, "markdown", None), "fit_markdown", None
                )
                normalized.append(
                    CrawlMarkdownResult(
                        url=str(result.url),
                        content=fit_markdown
                        if result.success and isinstance(fit_markdown, str)
                        else None,
                    )
                )
            return normalized
        except Exception as exc:
            raise Crawl4AIError from exc


__all__ = ["Crawl4AIError", "Crawl4AIMarkdownProvider", "CrawlMarkdownResult"]
