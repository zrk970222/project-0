from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class ClassifyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class ClassifyResponse(BaseModel):
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    model: str
    text_preview: str
