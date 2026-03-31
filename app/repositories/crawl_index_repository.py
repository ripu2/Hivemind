from typing import Optional
from app import database
from app.models.crawl_index_model import CrawlIndex


class CrawlIndexRepository:
    def get_by_url(self, url: str) -> Optional[CrawlIndex]:
        conn = database.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, url, pinecone_namespace, chunk_count, scraped_at "
                    "FROM crawl_index WHERE url = %s",
                    (url,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return CrawlIndex(
                    id=row[0],
                    url=row[1],
                    pinecone_namespace=row[2],
                    chunk_count=row[3],
                    scraped_at=row[4],
                )
        finally:
            database.put_conn(conn)

    def create(self, url: str, pinecone_namespace: str, chunk_count: int) -> CrawlIndex:
        conn = database.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO crawl_index (url, pinecone_namespace, chunk_count) "
                    "VALUES (%s, %s, %s) "
                    "ON CONFLICT (url) DO UPDATE "
                    "SET pinecone_namespace = EXCLUDED.pinecone_namespace, "
                    "    chunk_count = EXCLUDED.chunk_count, "
                    "    scraped_at = NOW() "
                    "RETURNING id, url, pinecone_namespace, chunk_count, scraped_at",
                    (url, pinecone_namespace, chunk_count),
                )
                row = cur.fetchone()
                conn.commit()
                return CrawlIndex(
                    id=row[0],
                    url=row[1],
                    pinecone_namespace=row[2],
                    chunk_count=row[3],
                    scraped_at=row[4],
                )
        finally:
            database.put_conn(conn)

    def get_crawled_page_urls(self) -> set[str]:
        conn = database.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT url FROM crawled_pages")
                return {row[0] for row in cur.fetchall()}
        finally:
            database.put_conn(conn)

    def save_crawled_page(self, url: str) -> None:
        conn = database.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO crawled_pages (url) VALUES (%s) ON CONFLICT DO NOTHING",
                    (url,),
                )
            conn.commit()
        finally:
            database.put_conn(conn)

    def list_all(self) -> list[CrawlIndex]:
        conn = database.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, url, pinecone_namespace, chunk_count, scraped_at "
                    "FROM crawl_index ORDER BY scraped_at DESC"
                )
                return [
                    CrawlIndex(id=r[0], url=r[1], pinecone_namespace=r[2], chunk_count=r[3], scraped_at=r[4])
                    for r in cur.fetchall()
                ]
        finally:
            database.put_conn(conn)
