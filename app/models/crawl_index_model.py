from dataclasses import dataclass
from datetime import datetime


@dataclass
class CrawlIndex:
    id: int
    url: str
    pinecone_namespace: str
    chunk_count: int
    scraped_at: datetime
