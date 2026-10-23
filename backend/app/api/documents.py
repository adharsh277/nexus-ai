import logging
import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal, get_db
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.user import User
from app.schemas.document import (
    DocumentChunkRead,
    DocumentRead,
    DocumentSearchRequest,
    DocumentSearchResponse,
)
from app.security import get_current_user
from app.services.documents.extractor import (
    DocumentExtractionError,
    DocumentValidationError,
)
from app.services.documents.service import (
    delete_user_document,
    get_user_document,
    list_user_documents,
    process_document,
    save_and_create_document,
    search_user_documents,
)
from app.services.embeddings import EmbeddingError

logger = logging.getLogger("nexus.api.documents")

router = APIRouter(prefix="/documents", tags=["documents"])


def _run_background_processing(document_id: uuid.UUID) -> None:
    """Worker function for async document processing."""
    from app.main import app

    # Check for test dependency override first
    db_gen = app.dependency_overrides.get(get_db)
    if db_gen:
        db = db_gen()
        try:
            process_document(document_id, db)
        except Exception as exc:
            logger.exception("Background processing error for document %s: %s", document_id, exc)
        return

    # In production, create standalone session
    db = SessionLocal()
    try:
        process_document(document_id, db)
    except Exception as exc:
        logger.exception("Background processing error for document %s: %s", document_id, exc)
    finally:
        db.close()


@router.post(
    "/upload",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document for text extraction and vector embedding",
)
async def upload_document(
    file: UploadFile = File(...),
    background: bool = Query(True, description="Whether to process document asynchronously in background"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload PDF, DOCX, TXT, or Markdown documents.
    
    Validates file extension, magic bytes, and file size (default 20MB max).
    Saves the file securely on disk and enqueues text extraction & embedding.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File upload must include a filename",
        )

    # Read content safely checking size limit
    max_size = settings.document_max_file_size_bytes
    contents = await file.read(max_size + 1024)

    if len(contents) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {max_size // (1024 * 1024)} MB",
        )

    try:
        doc = save_and_create_document(
            file_bytes=contents,
            original_filename=file.filename,
            user_id=user.id,
            db=db,
        )
    except DocumentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error saving document: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded document",
        ) from exc

    if background:
        background_tasks.add_task(_run_background_processing, doc.id)
    else:
        # Synchronous processing requested
        doc = process_document(doc.id, db)

    return doc


@router.get("", response_model=list[DocumentRead], summary="List all documents owned by user")
def list_documents(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return list_user_documents(user.id, db)


@router.get("/{document_id}", response_model=DocumentRead, summary="Get document details by ID")
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = get_user_document(document_id, user.id, db)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied",
        )
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a document and its chunks")
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    success = delete_user_document(document_id, user.id, db)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied",
        )


@router.post("/{document_id}/process", response_model=DocumentRead, summary="Trigger processing for a document")
def trigger_processing(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = get_user_document(document_id, user.id, db)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied",
        )
    return process_document(document_id, db)


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkRead], summary="List chunks for a document")
def get_document_chunks(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = get_user_document(document_id, user.id, db)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied",
        )

    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id, DocumentChunk.user_id == user.id)
        .order_by(DocumentChunk.chunk_index)
    )
    return list(db.scalars(stmt).all())


@router.post("/search", response_model=DocumentSearchResponse, summary="Search documents using semantic vector similarity")
def search_documents(
    req: DocumentSearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Semantic cosine similarity search across the user's processed documents."""
    if req.document_id:
        # Validate that document exists and belongs to this user
        doc = get_user_document(req.document_id, user.id, db)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specified document not found or access denied",
            )

    try:
        results = search_user_documents(
            query=req.query,
            user_id=user.id,
            db=db,
            top_k=req.top_k,
            document_id=req.document_id,
        )
        return DocumentSearchResponse(query=req.query, results=results)
    except EmbeddingError as exc:
        logger.warning("Embedding service error during document search: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding provider error: {exc.message}",
        ) from exc
