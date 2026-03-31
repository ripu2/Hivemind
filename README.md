# Text QA API

A production-ready **Retrieval-Augmented Generation (RAG)** API that crawls websites, embeds content into a vector store, and answers questions conversationally with full chat memory.

---

## How it works

```
User submits URL
      │
      ▼
Crawl website (BFS) → extract structured text
      │
      ▼
Chunk (1000 chars, 200 overlap) → embed via OpenAI → store in Pinecone namespace
      │
      ▼
Register in Supabase (url → namespace mapping)
      │
      ▼
User asks question  ──►  embed question  ──►  similarity search in Pinecone
                                                        │
                                                        ▼
                                            Top-5 chunks + chat history
                                                        │
                                                        ▼
                                               GPT-4o-mini generates answer
                                                        │
                                                        ▼
                                         Persist turn to conversation history
```

Every 10 questions, FAQs are automatically regenerated in the background by analysing the most common queries.

---

## Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.135, Python 3.13 |
| LLM | OpenAI GPT-4o-mini |
| Embeddings | OpenAI text-embedding (1536 dims) |
| Vector store | Pinecone (serverless, cosine similarity) |
| Relational DB | PostgreSQL via Supabase |
| RAG framework | LangChain + LangChain-Pinecone |
| Web scraping | BeautifulSoup4, requests |
| Server | Uvicorn with uvloop |

---

## Setup

### 1. Install dependencies

```bash
uv sync
```

Or with pip:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in all values:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `PINECONE_API_KEY` | Yes | Pinecone API key |
| `PINECONE_INDEX_NAME` | No | Pinecone index name (default: `text-qa`) |
| `DB_HOST` | Yes | PostgreSQL / Supabase host |
| `DB_PORT` | No | Port (default: `5432`) |
| `DB_NAME` | No | Database name (default: `postgres`) |
| `DB_USER` | No | Database user (default: `postgres`) |
| `DB_PASSWORD` | Yes | Database password |
| `DB_SSLMODE` | No | SSL mode (default: `require`) |
| `DB_CONNECT_TIMEOUT` | No | Timeout in seconds (default: `10`) |

### 3. Start the server

```bash
make runserver
```

On first boot the server will:
- Connect to Supabase and auto-create all required tables
- Connect to Pinecone and create the index if it does not exist
- Log `Connected to Supabase` and `Connected to Pinecone index 'text-qa'`

---

## Makefile commands

```bash
make runserver   # Activate venv and start uvicorn with --reload
make install     # Install / sync dependencies via uv
make freeze      # Regenerate requirements.txt from uv lockfile
```

---

## API overview

| Method | Path | Description | Status |
|---|---|---|---|
| GET | `/` | Welcome message | 200 |
| GET | `/health` | Deep health check (DB + Pinecone + OpenAI) | 200 / 503 |
| POST | `/api/v1/crawl` | Submit URL for crawling and indexing | 202 |
| POST | `/api/v1/query` | Ask a question with optional conversation memory | 200 |
| GET | `/api/v1/faqs` | Retrieve auto-generated FAQs | 200 |

Interactive docs available at `http://localhost:8000/docs` (Swagger UI).

---

## Usage examples

### Crawl a website

```bash
curl -X POST http://localhost:8000/api/v1/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "https://docs.example.com"}'
```

Response `202 Accepted`:
```json
{
  "message": "Crawl accepted",
  "url": "https://docs.example.com",
  "response": "Crawling, embedding, and indexing will complete in the background."
}
```

### Ask a question

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I add a schedule?"}'
```

Response `200 OK`:
```json
{
  "answer": "## Prerequisites\n...\n## Steps\n1. ...",
  "sources": ["https://docs.example.com/schedules"],
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "namespace": "docs_example_com"
}
```

### Continue a conversation

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What permissions do I need for that?",
    "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

The model sees the full prior conversation history on every turn.

### Filter to a specific site

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How do I set up alerts?",
    "url": "https://docs.example.com"
  }'
```

### Get FAQs

```bash
curl http://localhost:8000/api/v1/faqs
```

---

## Project structure

```
app/
├── main.py                  # FastAPI app, lifespan, global error handlers
├── config.py                # Environment variable loading
├── database.py              # Supabase connection pool + table creation
├── vector_store.py          # Pinecone client + index management
├── logger.py                # Centralised logging setup
│
├── controllers/             # HTTP routing only — no business logic
│   ├── crawl_controller.py  # POST /api/v1/crawl (SSRF guard, 202/409)
│   ├── query_controller.py  # POST /api/v1/query (FAQ trigger, 200/404)
│   └── faq_controller.py    # GET  /api/v1/faqs
│
├── services/                # Business logic
│   ├── crawl_service.py     # BFS web crawler → embed → register
│   ├── embedding_service.py # Chunk, embed via OpenAI, upsert to Pinecone
│   ├── query_service.py     # Parallel vector search + LLM chain + history
│   └── faq_service.py       # Query log analysis → FAQ generation
│
├── repositories/            # All database access
│   ├── crawl_index_repository.py    # crawl_index + crawled_pages tables
│   ├── conversation_repository.py   # conversations + conversation_messages
│   └── faq_repository.py            # faqs + query_logs tables
│
├── models/                  # Internal Python dataclasses
│   ├── crawl_index_model.py
│   ├── conversation_model.py
│   └── faq_model.py
│
└── schemas/                 # Pydantic request/response models
    ├── crawl_schema.py
    ├── query_schema.py
    ├── faq_schema.py
    └── response.py          # Generic ApiResponse[T] + ErrorResponse
```

---

## Database schema

All tables are created automatically on server boot.

```sql
-- Tracks which websites have been crawled and indexed
crawl_index (
  id                SERIAL PRIMARY KEY,
  url               TEXT UNIQUE NOT NULL,
  pinecone_namespace TEXT NOT NULL,
  chunk_count       INTEGER DEFAULT 0,
  scraped_at        TIMESTAMPTZ DEFAULT NOW()
)

-- Tracks individual pages to prevent re-crawling
crawled_pages (
  url        TEXT PRIMARY KEY,
  crawled_at TIMESTAMPTZ DEFAULT NOW()
)

-- Conversation sessions
conversations (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Individual messages within a conversation
conversation_messages (
  id              SERIAL PRIMARY KEY,
  conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
  role            TEXT CHECK (role IN ('human', 'ai')),
  content         TEXT NOT NULL,
  created_at      TIMESTAMPTZ DEFAULT NOW()
)

-- Every question asked by every user
query_logs (
  id              SERIAL PRIMARY KEY,
  question        TEXT NOT NULL,
  conversation_id TEXT,
  asked_at        TIMESTAMPTZ DEFAULT NOW()
)

-- Auto-generated FAQs (max 5 rows)
faqs (
  id           SERIAL PRIMARY KEY,
  question     TEXT NOT NULL,
  answer       TEXT NOT NULL,
  frequency    INTEGER DEFAULT 1,
  generated_at TIMESTAMPTZ DEFAULT NOW()
)
```

---

## Error responses

All errors follow a consistent format:

```json
{
  "success": false,
  "error": "Human-readable description"
}
```

| Code | Meaning |
|---|---|
| 400 | Invalid request (e.g. URL resolves to private IP) |
| 404 | Resource not found (URL not indexed, no documents indexed) |
| 409 | Conflict (URL already indexed) |
| 422 | Validation error with field-level details |
| 503 | Service degraded (health check) |
| 500 | Internal server error |

---

## Crawler behaviour

- Follows same-domain links only (no cross-origin crawl)
- Skips binary files: `.png .jpg .pdf .zip .css .js`
- Removes nav, header, footer, script, style, aside elements before extracting text
- Extracts: headings (h1–h6), paragraphs, lists, code blocks, blockquotes
- Strips noise tokens (navigation labels, emoji, special chars)
- Respects a 0.8 s delay between page requests
- Persists every visited URL so re-submitted sites pick up exactly where they left off
- SSRF guard: rejects URLs that resolve to private/loopback/link-local IPs

---

## FAQ auto-generation

FAQs are never manually triggered. The cycle is:

1. Every question asked is logged to `query_logs`
2. On every 10th question, a background thread starts
3. The last 200 questions are sent to GPT-4o-mini to identify the 5 most common topics
4. For each topic, a full RAG query is run to generate the answer
5. The `faqs` table is atomically replaced (old FAQs stay visible until the new ones are ready)
6. `GET /api/v1/faqs` always returns the current top-5

---

## Conversation memory

- First call: omit `conversation_id` — a new UUID is created and returned
- Subsequent calls: pass back the `conversation_id` from the previous response
- Each turn (human question + AI answer) is persisted in Supabase
- Conversations survive server restarts
- There is no maximum conversation length enforced
