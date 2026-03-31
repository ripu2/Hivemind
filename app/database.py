import psycopg2
from psycopg2 import pool
from app import config

_pool: pool.ThreadedConnectionPool | None = None


def connect() -> None:
    global _pool
    _pool = pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        sslmode=config.DB_SSLMODE,
        connect_timeout=int(config.DB_CONNECT_TIMEOUT),
    )
    # Verify connection and create tables
    conn = _pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS crawl_index (
                    id          SERIAL PRIMARY KEY,
                    url         TEXT NOT NULL UNIQUE,
                    pinecone_namespace TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    scraped_at  TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS crawled_pages (
                    url         TEXT PRIMARY KEY,
                    crawled_at  TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id              SERIAL PRIMARY KEY,
                    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role            TEXT NOT NULL CHECK (role IN ('human', 'ai')),
                    content         TEXT NOT NULL,
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS query_logs (
                    id              SERIAL PRIMARY KEY,
                    question        TEXT NOT NULL,
                    conversation_id TEXT,
                    asked_at        TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS faqs (
                    id              SERIAL PRIMARY KEY,
                    question        TEXT NOT NULL,
                    answer          TEXT NOT NULL,
                    frequency       INTEGER NOT NULL DEFAULT 1,
                    generated_at    TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        conn.commit()
        print(f"Connected to Supabase at {config.DB_HOST}")
    finally:
        _pool.putconn(conn)


def disconnect() -> None:
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
        print("Database connection pool closed")


def get_conn() -> psycopg2.extensions.connection:
    if _pool is None:
        raise RuntimeError("Database pool is not initialised")
    return _pool.getconn()


def put_conn(conn: psycopg2.extensions.connection) -> None:
    if _pool:
        _pool.putconn(conn)
