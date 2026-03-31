# API Reference

Base URL: `http://localhost:8000`

All request bodies must use `Content-Type: application/json`.
All error responses follow `{"success": false, "error": "..."}`.

---

## Table of contents

- [Health](#health)
- [Crawl](#crawl)
- [Query](#query)
- [FAQs](#faqs)
- [Status codes](#status-codes)
- [Error format](#error-format)

---

## Health

### `GET /`

Welcome message. Confirms the server is running.

**Response `200`**
```json
{
  "success": true,
  "message": "Text QA API is running"
}
```

---

### `GET /health`

Deep health check. Probes every external dependency.

**Response `200` — all healthy**
```json
{
  "success": true,
  "status": "healthy",
  "checks": {
    "database": "ok",
    "pinecone": "ok",
    "openai": "configured"
  }
}
```

**Response `503` — one or more checks failed**
```json
{
  "success": false,
  "status": "degraded",
  "checks": {
    "database": "error: could not connect to server",
    "pinecone": "ok",
    "openai": "configured"
  }
}
```

| Check | What is probed |
|---|---|
| `database` | `SELECT 1` against Supabase |
| `pinecone` | `list_indexes()` against Pinecone |
| `openai` | Presence of `OPENAI_API_KEY` env var |

---

## Crawl

### `POST /api/v1/crawl`

Submit a public URL for crawling, embedding, and indexing. Processing runs in the background — the response is returned immediately.

**Request body**

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `url` | string (URL) | Yes | Valid HTTP/HTTPS URL, max 2048 chars | The starting URL to crawl |

```json
{
  "url": "https://docs.example.com"
}
```

**Response `202 Accepted`**

Crawl job accepted and running in the background.

```json
{
  "message": "Crawl accepted",
  "url": "https://docs.example.com",
  "response": "Crawling, embedding, and indexing will complete in the background."
}
```

**Error responses**

| Code | When | Example detail |
|---|---|---|
| `400` | URL hostname cannot be resolved | `"Could not resolve hostname: docs.example.com"` |
| `400` | URL resolves to private/loopback IP (SSRF guard) | `"URL resolves to a non-public address (192.168.1.1)"` |
| `409` | URL has already been indexed | `"URL already indexed (namespace=docs_example_com, chunks=312)"` |
| `422` | Request body is invalid (not a valid URL, etc.) | `"url: URL scheme should be 'http' or 'https'"` |

**What happens in the background**

1. BFS crawl of all pages under the same domain
2. Each page: nav/header/footer stripped → structured text extracted
3. Documents chunked (1000 chars, 200 overlap) and embedded via OpenAI
4. Vectors upserted to Pinecone under a namespace derived from the domain (e.g. `docs_example_com`)
5. Entry written to `crawl_index` table in Supabase
6. Every crawled URL saved to `crawled_pages` — if the same site is submitted again, the crawl resumes without re-visiting already-scraped pages

---

## Query

### `POST /api/v1/query`

Ask a question about indexed content. Supports multi-turn conversations via `conversation_id`.

**Request body**

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `question` | string | Yes | 1–1000 chars | The question to answer |
| `url` | string (URL) | No | Valid HTTP/HTTPS URL | Scope the search to a specific indexed site |
| `conversation_id` | string (UUID) | No | Valid UUID from a prior response | Continue an existing conversation |

```json
{
  "question": "How do I add a schedule?",
  "url": "https://docs.example.com",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response `200 OK`**

| Field | Type | Description |
|---|---|---|
| `answer` | string | LLM-generated answer in structured markdown |
| `sources` | array of strings | Unique source URLs the answer was built from |
| `conversation_id` | string (UUID) | Pass this back on the next request to continue the conversation |
| `namespace` | string \| null | Pinecone namespace that was searched (null = all namespaces) |

```json
{
  "answer": "## Prerequisites\n- Admin access to the dashboard\n\n## Steps\n1. Navigate to **Settings → Schedules**\n2. Click **Add Schedule**\n3. ...",
  "sources": [
    "https://docs.example.com/schedules/create",
    "https://docs.example.com/permissions"
  ],
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "namespace": "docs_example_com"
}
```

**Error responses**

| Code | When |
|---|---|
| `404` | `url` provided but that URL has not been indexed yet |
| `404` | No `url` provided and no documents have been indexed at all |
| `422` | `question` is empty or exceeds 1000 characters |

**Conversation memory**

- **Start a new conversation:** omit `conversation_id`. A new UUID is created and returned.
- **Continue a conversation:** pass the `conversation_id` from any previous response.
- The full conversation history is sent to the LLM on every turn.
- Conversations are persisted in Supabase and survive server restarts.

**How answers are structured**

The LLM is instructed to:
- Open with a one-sentence summary
- List prerequisites under `## Prerequisites` (if any)
- List steps in order under `## Steps` (numbered, nothing skipped)
- Use exact field names, button labels, and code from the source documents
- Surface warnings/gotchas under `## Notes`
- Only use information from the retrieved context (never hallucinate)

**Searching without a `url`**

When no `url` is given, all indexed namespaces are searched in parallel. Results are merged and re-ranked by similarity score before being passed to the LLM.

---

## FAQs

### `GET /api/v1/faqs`

Returns the current auto-generated FAQs (maximum 5), ordered by frequency (most common questions first).

FAQs are generated automatically — there is no manual trigger. On every 10th question asked via `POST /api/v1/query`, a background job analyses the last 200 questions, identifies the top 5 most common topics, and regenerates the FAQ list.

**Response `200 OK`**

| Field | Type | Description |
|---|---|---|
| `faqs` | array | Up to 5 FAQ items |
| `total` | integer | Number of FAQs returned |

Each FAQ item:

| Field | Type | Description |
|---|---|---|
| `id` | integer | FAQ identifier |
| `question` | string | Auto-generated question representing the topic |
| `answer` | string | RAG-generated answer to the question |
| `frequency` | integer | Estimated number of queries related to this topic |
| `generated_at` | string (ISO 8601) | When this FAQ was last generated |

```json
{
  "faqs": [
    {
      "id": 1,
      "question": "How do I set up on-call schedules?",
      "answer": "## Prerequisites\n...\n## Steps\n1. ...",
      "frequency": 24,
      "generated_at": "2026-03-31T18:00:00.000Z"
    },
    {
      "id": 2,
      "question": "What are the notification rules?",
      "answer": "...",
      "frequency": 18,
      "generated_at": "2026-03-31T18:00:00.000Z"
    }
  ],
  "total": 2
}
```

Returns an empty list if no questions have been asked yet or not enough data exists to generate FAQs.

---

## Status codes

| Code | Meaning |
|---|---|
| `200` | Success |
| `202` | Accepted — job queued for background processing |
| `400` | Bad request (invalid URL, SSRF guard triggered) |
| `404` | Resource not found |
| `409` | Conflict (e.g. URL already indexed) |
| `422` | Request validation failed |
| `503` | Service degraded (dependency down) |
| `500` | Internal server error |

---

## Error format

All errors return a consistent JSON body:

```json
{
  "success": false,
  "error": "Human-readable description of what went wrong"
}
```

Validation errors (`422`) include field-level detail:

```json
{
  "success": false,
  "error": "Validation failed",
  "details": [
    "body.question: String should have at least 1 character",
    "body.url: URL scheme should be 'http' or 'https'"
  ]
}
```
