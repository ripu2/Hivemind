from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import config, database, vector_store
from app.logger import get_logger
from app.controllers.item_controller import router as item_router
from app.controllers.crawl_controller import router as crawl_router
from app.controllers.query_controller import router as query_router
from app.controllers.faq_controller import router as faq_router

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.connect()
    vector_store.connect()
    yield
    database.disconnect()
    vector_store.disconnect()


app = FastAPI(
    title="Text QA API",
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(item_router, prefix="/api/v1")
app.include_router(crawl_router, prefix="/api/v1")
app.include_router(query_router, prefix="/api/v1")
app.include_router(faq_router, prefix="/api/v1")


# ── Standardised error handlers ───────────────────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(status_code=404, content={"success": False, "error": "Resource not found"})


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    log.error("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"success": False, "error": "Internal server error"})


from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = [f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}" for e in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={"success": False, "error": "Validation failed", "details": errors},
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"success": True, "message": "Text QA API is running"}


@app.get("/health")
async def health_check():
    checks: dict[str, str] = {}
    healthy = True

    # Database
    try:
        conn = database.get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        database.put_conn(conn)
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        healthy = False

    # Pinecone
    try:
        pc = vector_store.get_client()
        pc.list_indexes()
        checks["pinecone"] = "ok"
    except Exception as e:
        checks["pinecone"] = f"error: {e}"
        healthy = False

    # OpenAI key presence
    checks["openai"] = "configured" if config.OPENAI_API_KEY else "not configured"
    if not config.OPENAI_API_KEY:
        healthy = False

    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "success": healthy,
            "status": "healthy" if healthy else "degraded",
            "checks": checks,
        },
    )
