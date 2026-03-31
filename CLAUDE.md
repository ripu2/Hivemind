# CLAUDE.md

## Project

**text-qa** — a production-ready RAG (Retrieval-Augmented Generation) API. Pipeline: crawl website → chunk & embed → store in Pinecone → retrieve relevant chunks → answer questions via GPT-4o-mini with full conversation memory and auto-generated FAQs.

## Commands

```bash
make runserver   # activate .venv and start uvicorn --reload
make install     # uv sync
make freeze      # regenerate requirements.txt
```

## Environment variables

| Variable | Required | Default |
|---|---|---|
| `OPENAI_API_KEY` | Yes | — |
| `PINECONE_API_KEY` | Yes | — |
| `PINECONE_INDEX_NAME` | No | `text-qa` |
| `DB_HOST` | Yes | — |
| `DB_PORT` | No | `5432` |
| `DB_NAME` | No | `postgres` |
| `DB_USER` | No | `postgres` |
| `DB_PASSWORD` | Yes | — |
| `DB_SSLMODE` | No | `require` |
| `DB_CONNECT_TIMEOUT` | No | `10` |

## Architecture

MVC + Repository layering. Strict separation of concerns:

```
controllers/  →  services/  →  repositories/  →  database / external APIs
```

- **Controllers** — HTTP routing, status codes, validation. No business logic.
- **Services** — business logic. No SQL, no HTTP responses.
- **Repositories** — all DB access. Return domain models, not raw rows.
- **Models** — internal Python dataclasses (not Pydantic).
- **Schemas** — Pydantic request/response shapes only.

## Key services

| Service | Responsibility |
|---|---|
| `CrawlService` | BFS web crawler → extract structured text → embed in batches of 50 → register in Supabase |
| `EmbeddingService` | Chunk documents (1000/200 overlap) → OpenAI embeddings → upsert to Pinecone namespace |
| `QueryService` | Parallel namespace search → build LLM prompt with history → GPT-4o-mini → persist turn |
| `FaqService` | Analyse query_logs → LLM identifies top-5 topics → RAG answers → atomic DB replace |

## API endpoints

| Method | Path | Code | Notes |
|---|---|---|---|
| GET | `/` | 200 | Welcome |
| GET | `/health` | 200/503 | Probes Supabase, Pinecone, OpenAI key |
| POST | `/api/v1/crawl` | 202/400/409 | Background task; SSRF guard on URL |
| POST | `/api/v1/query` | 200/404 | Conversational; pass `conversation_id` back |
| GET | `/api/v1/faqs` | 200 | Auto-generated, max 5, no manual trigger |

## Error responses

All errors: `{"success": false, "error": "..."}`.
Validation errors add `"details": ["field: message"]`.

## Database

Tables are auto-created on boot. Never manually run migrations.

| Table | Purpose |
|---|---|
| `crawl_index` | url → pinecone_namespace mapping |
| `crawled_pages` | individual page URLs (dedup across sessions) |
| `conversations` | UUID-based chat sessions |
| `conversation_messages` | human/ai turns per conversation |
| `query_logs` | every question asked (drives FAQ generation) |
| `faqs` | max 5 rows, atomically replaced every 10 queries |

## Conventions

- Python 3.13, formatted with `black`
- Pydantic v2 for all schemas
- All `print()` is banned — use `from app.logger import get_logger`
- Repositories must always call `database.put_conn(conn)` in a `finally` block
- Controllers raise `HTTPException` for domain errors — services return plain dicts
- FAQ regeneration is always async and always fire-and-forget
- New routes: add controller → register in `app/main.py`
- Do not put DB logic in services or HTTP logic in repositories
