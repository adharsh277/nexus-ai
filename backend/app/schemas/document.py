import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    original_filename: str
    mime_type: str
    file_size: int
    status: DocumentStatus
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    page_number: int | None = None
    content: str
    created_at: datetime


class DocumentSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query string")
    top_k: int = Field(5, ge=1, le=50, description="Maximum number of chunks to return")
    document_id: uuid.UUID | None = Field(None, description="Optional document ID to scope the search")


class DocumentSearchResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    page_number: int | None = None
    chunk_index: int
    content: str
    similarity_score: float


class DocumentSearchResponse(BaseModel):
    query: str
    results: list[DocumentSearchResult]
