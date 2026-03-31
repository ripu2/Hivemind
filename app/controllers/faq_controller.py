from fastapi import APIRouter
from app.schemas.faq_schema import FaqItem, FaqListResponse
from app.services.faq_service import FaqService

router = APIRouter(tags=["faqs"])
faq_service = FaqService()


@router.get("/faqs", response_model=FaqListResponse, status_code=200)
async def get_faqs() -> FaqListResponse:
    faqs = faq_service.get_faqs()
    return FaqListResponse(
        faqs=[
            FaqItem(
                id=f.id,
                question=f.question,
                answer=f.answer,
                frequency=f.frequency,
                generated_at=f.generated_at,
            )
            for f in faqs
        ],
        total=len(faqs),
    )
