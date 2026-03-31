import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.services.crawl_service import CrawlService
from app.repositories.crawl_index_repository import CrawlIndexRepository
from app.schemas.crawl_schema import CrawlPayload, CrawlResponse

router = APIRouter(tags=["crawl"])
crawl_service = CrawlService()
crawl_index_repo = CrawlIndexRepository()


def _assert_safe_url(url: str) -> None:
    """Raises HTTPException 400 if URL resolves to a private/loopback address (SSRF guard)."""
    hostname = urlparse(url).hostname or ""
    try:
        ip = socket.gethostbyname(hostname)
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise HTTPException(status_code=400, detail=f"URL resolves to a non-public address ({ip})")
    except socket.gaierror:
        raise HTTPException(status_code=400, detail=f"Could not resolve hostname: {hostname}")


@router.post("/crawl", response_model=CrawlResponse, status_code=202)
async def crawl(payload: CrawlPayload, background_tasks: BackgroundTasks) -> CrawlResponse:
    url = str(payload.url)
    _assert_safe_url(url)

    existing = crawl_index_repo.get_by_url(url)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"URL already indexed (namespace={existing.pinecone_namespace}, chunks={existing.chunk_count}). Use POST /api/v1/query to ask questions.",
        )

    background_tasks.add_task(crawl_service.crawlWebsite, url)
    return CrawlResponse(
        message="Crawl accepted",
        url=payload.url,
        response="Crawling, embedding, and indexing will complete in the background.",
    )
