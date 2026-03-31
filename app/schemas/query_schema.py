from pydantic import BaseModel, Field, HttpUrl
from typing import Optional


class QueryPayload(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    url: Optional[HttpUrl] = None          # filter to a specific indexed site
    conversation_id: Optional[str] = None  # omit to start a new conversation


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    conversation_id: str   # always returned — pass this back on next turn
    namespace: Optional[str] = None
