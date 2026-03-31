import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document

from app.services.embedding_service import EmbeddingService
from app.repositories.crawl_index_repository import CrawlIndexRepository
from app.logger import get_logger

log = get_logger(__name__)

EMBED_BATCH_SIZE = 50  # embed in batches to avoid memory pressure


def _url_to_namespace(url: str) -> str:
    netloc = urlparse(url).netloc
    return re.sub(r"[^a-z0-9]+", "_", netloc.lower()).strip("_")[:60]


class CrawlService:
    EXCLUDED_SUFFIXES = (".png", ".jpg", ".pdf", ".zip", ".css", ".js")
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
    NOISE_TOKENS = {"hashtag", "arrow-up-right", "circle-check", "circle-exclamation"}
    NOISE_PATTERNS = (
        re.compile(r"^(menu|search|home|back|next|previous)$", re.I),
        re.compile(r"^[\W_]+$"),
    )

    def __init__(self) -> None:
        self._embedding_service = EmbeddingService()
        self._crawl_index_repo = CrawlIndexRepository()

    def _is_valid_url(self, candidate_url: str, base_url: str) -> bool:
        parsed = urlparse(candidate_url)
        base = urlparse(base_url)
        return (
            parsed.netloc == base.netloc
            and parsed.scheme in ("http", "https")
            and not candidate_url.endswith(self.EXCLUDED_SUFFIXES)
        )

    def _extract_links(self, soup: BeautifulSoup, current_url: str, base_url: str) -> list[str]:
        links: set[str] = set()
        nav_areas = soup.select("nav, aside, [class*='sidebar'], [class*='nav'], [class*='menu']")
        for area in (nav_areas or [soup]):
            for anchor in area.find_all("a", href=True):
                full_url = urljoin(current_url, anchor["href"]).split("#")[0]
                if self._is_valid_url(full_url, base_url):
                    links.add(full_url)
        return list(links)

    def _clean_line(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        normalized = normalized.replace("\\", "").replace("🔹", "").strip()
        normalized = re.sub(r"^(hashtag|arrow-up-right|circle-check|circle-exclamation)\s+", "", normalized, flags=re.I)
        if normalized.lower() in self.NOISE_TOKENS:
            return ""
        for pattern in self.NOISE_PATTERNS:
            if pattern.match(normalized):
                return ""
        return normalized

    def _extract_structured_text(self, content_area: BeautifulSoup) -> str:
        blocks: list[str] = []
        for element in content_area.select("h1,h2,h3,h4,h5,h6,p,li,pre,code,blockquote"):
            if element.name == "code" and element.parent and element.parent.name == "pre":
                continue
            if element.name in {"pre", "code"}:
                cleaned = self._clean_line(element.get_text("\n", strip=True))
                if not cleaned:
                    continue
                block = f"```\n{cleaned}\n```"
            else:
                cleaned = self._clean_line(element.get_text(" ", strip=True))
                if not cleaned:
                    continue
                if element.name and element.name.startswith("h"):
                    block = f'{"#" * int(element.name[1])} {cleaned}'
                elif element.name == "li":
                    block = f"- {cleaned}"
                elif element.name == "blockquote":
                    block = f"> {cleaned}"
                else:
                    block = cleaned
            if not blocks or blocks[-1] != block:
                blocks.append(block)
        return "\n\n".join(blocks).strip()

    def _scrape_page(self, url: str) -> tuple[str, str]:
        headers = {"User-Agent": self.USER_AGENT}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        title = (
            soup.find("h1").get_text(strip=True) if soup.find("h1")
            else (soup.title.get_text(strip=True) if soup.title
                  else urlparse(url).path.strip("/").replace("/", "_") or "index")
        )
        for tag in soup(["nav", "header", "footer", "script", "style", "aside"]):
            tag.decompose()

        content_area = (
            soup.find("article")
            or soup.find("main")
            or soup.find(attrs={"class": re.compile(r"content|markdown|page|body", re.I)})
            or soup.find("body")
        )
        text = self._extract_structured_text(content_area) if content_area else ""
        return title, text, soup

    def crawlWebsite(self, url: str) -> str:
        existing = self._crawl_index_repo.get_by_url(url)
        if existing:
            log.info("Already indexed: %s (namespace=%s)", url, existing.pinecone_namespace)
            return f"Already indexed: {url}"

        namespace = _url_to_namespace(url)
        visited: set[str] = self._crawl_index_repo.get_crawled_page_urls()
        queue: deque[str] = deque([u for u in [url] if u not in visited])

        parsed_count = 0
        saved_count = 0
        failed_count = 0
        total_chunks = 0
        batch: list[Document] = []

        def _flush_batch():
            nonlocal total_chunks
            if batch:
                total_chunks += self._embedding_service.embed_and_store(batch, namespace=namespace)
                batch.clear()

        while queue:
            current_url = queue.popleft()
            if current_url in visited:
                continue
            visited.add(current_url)
            log.info("[%d/%d] Crawling: %s", parsed_count + 1, len(visited) + len(queue), current_url)

            try:
                title, content, soup = self._scrape_page(current_url)
                parsed_count += 1
                self._crawl_index_repo.save_crawled_page(current_url)

                if content.strip():
                    batch.append(Document(
                        page_content=content,
                        metadata={"source": current_url, "title": title},
                    ))
                    saved_count += 1

                    if len(batch) >= EMBED_BATCH_SIZE:
                        _flush_batch()

                for link in self._extract_links(soup, current_url, url):
                    if link not in visited and link not in queue:
                        queue.append(link)

                time.sleep(0.8)

            except requests.RequestException:
                failed_count += 1
                parsed_count += 1
                self._crawl_index_repo.save_crawled_page(current_url)
                log.warning("Failed to scrape: %s", current_url)

        _flush_batch()  # embed any remaining docs

        self._crawl_index_repo.create(url, namespace, total_chunks)
        log.info("Done: %d pages, %d chunks → namespace '%s'", parsed_count, total_chunks, namespace)

        return (
            f"Crawled {parsed_count} pages; "
            f"embedded {total_chunks} chunks into namespace '{namespace}'; "
            f"failed {failed_count}"
        )
