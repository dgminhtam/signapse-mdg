import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.core.config import Settings, get_settings
from app.core.observability import log_event
from app.providers.crawl4ai_markdown import Crawl4AIError, Crawl4AIMarkdownProvider

router = APIRouter(tags=["crawl"])
logger = logging.getLogger(__name__)


class CrawlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    urls: list[HttpUrl] = Field(min_length=1, max_length=10)


class CrawlResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    content: str | None
    error: str | None


class CrawlResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[CrawlResultResponse]


def get_crawl_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Crawl4AIMarkdownProvider:
    return Crawl4AIMarkdownProvider(proxy_url=settings.crawl_proxy_url)


@router.post("/crawl", response_model=CrawlResponse)
async def crawl(
    request: CrawlRequest,
    provider: Annotated[Crawl4AIMarkdownProvider, Depends(get_crawl_provider)],
) -> CrawlResponse:
    try:
        results = await provider.crawl_fit_markdown([str(url) for url in request.urls])
    except Crawl4AIError:
        log_event(
            logger,
            logging.ERROR,
            "crawl_request_failed",
            operation="crawl.fit_markdown",
            count=len(request.urls),
        )
        raise HTTPException(status_code=502, detail="Crawl failed.") from None
    return CrawlResponse(
        results=[
            CrawlResultResponse(
                url=result.url,
                content=result.content,
                error=None if result.content is not None else "Crawl failed.",
            )
            for result in results
        ]
    )
