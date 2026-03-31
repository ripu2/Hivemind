from fastapi import APIRouter, HTTPException
from app.schemas.query_schema import QueryPayload, QueryResponse
from app.services.query_service import QueryService
from app.services.faq_service import FaqService
from app.repositories.faq_repository import FaqRepository

router = APIRouter(tags=["query"])
query_service = QueryService()
faq_service = FaqService()
faq_repo = FaqRepository()


@router.post("/query", response_model=QueryResponse, status_code=200)
async def query(payload: QueryPayload) -> QueryResponse:
    result = query_service.query(
        question=payload.question,
        url=str(payload.url) if payload.url else None,
        conversation_id=payload.conversation_id,
    )

    # Surface domain errors as proper HTTP codes
    answer = result["answer"]
    if "has not been indexed yet" in answer:
        raise HTTPException(status_code=404, detail=answer)
    if "No documents have been indexed yet" in answer:
        raise HTTPException(status_code=404, detail=answer)

    # Log query and trigger FAQ regeneration if threshold hit (no circular import)
    count = faq_repo.log_query(payload.question, result["conversation_id"])
    if faq_repo.should_regenerate(count):
        faq_service.regenerate_async()

    return QueryResponse(
        answer=answer,
        sources=result["sources"],
        conversation_id=result["conversation_id"],
        namespace=result["namespace"],
    )
