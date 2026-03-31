from pydantic import BaseModel, Field, HttpUrl


class CrawlPayload(BaseModel):
    url: HttpUrl = Field(min_length=1, max_length=2048)


class CrawlResponse(BaseModel):
    message: str
    url: HttpUrl
    response: str