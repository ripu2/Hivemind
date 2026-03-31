from pydantic import BaseModel
from datetime import datetime


class FaqItem(BaseModel):
    id: int
    question: str
    answer: str
    frequency: int
    generated_at: datetime


class FaqListResponse(BaseModel):
    faqs: list[FaqItem]
    total: int
