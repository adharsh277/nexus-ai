import logging
import math
import re
import uuid
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.schemas.document import DocumentSearchResult
from app.services.documents.chunker import chunk_document_sections
from app.services.documents.extractor import (
    DocumentExtractionError,
    DocumentValidationError,
    extract_document_text,
    validate_file_content,
)
from app.services.embeddings import (
    EmbeddingDimensionMismatchError,
    EmbeddingError,
    get_embedding_provider,
)

logger = logging.getLogger("nexus.documents.service")


def compute_cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two numeric vectors."""
    if len(v1) != len(v2) or not v1:
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


def sanitize_filename(filename: str) -> str:
    """Sanitize raw filename to prevent path traversal or unsafe characters."""
    base = Path(filename).name
    # Remove control characters and traversal markers
    clean = re.sub(r'[\x00-\x1f\\/:\*\?"<>|]', "_", base)
    return clean or "document"


def save_and_create_document(
    file_bytes: bytes,
    original_filename: str,
    user_id: uuid.UUID,
    db: Session,
) -> Document:
    """Validate content, save file to persistent storage, and create DB Document record."""
    clean_filename = sanitize_filename(original_filename)
    mime_type = validate_file_content(
        filename=clean_filename,
        content=file_bytes,
        max_size_bytes=settings.document_max_file_size_bytes,
    )

    storage_dir = settings.get_storage_path()
    ext = Path(clean_filename).suffix.lower()
    storage_filename = f"{uuid.uuid4()}{ext}"
    target_path = storage_dir / storage_filename

    # Save to storage
    target_path.write_bytes(file_bytes)

    # Create document record
    doc = Document(
        user_id=user_id,
        filename=storage_filename,
        original_filename=clean_filename,
        mime_type=mime_type,
        file_size=len(file_bytes),
        status=DocumentStatus.uploaded,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def process_document(document_id: uuid.UUID, db: Session) -> Document:
    """Synchronously or asynchronously process document: extract, chunk, embed, and store."""
    doc = db.get(Document, document_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found")

    storage_dir = settings.get_storage_path()
    file_path = storage_dir / doc.filename

    doc.status = DocumentStatus.processing
    doc.error_message = None
    db.commit()
    db.refresh(doc)

    try:
        if not file_path.exists():
            raise DocumentExtractionError(f"Stored document file not found at {file_path}")

        # 1. Extraction
        sections = extract_document_text(file_path, doc.mime_type)

        # 2. Chunking
        chunks_data = chunk_document_sections(
            sections=sections,
            chunk_size=settings.document_chunk_size,
            chunk_overlap=settings.document_chunk_overlap,
        )

        # 3. Embeddings
        provider = get_embedding_provider()
        texts = [c.content for c in chunks_data]

        embeddings: list[list[float]] = []
        if texts:
            embeddings = provider.embed_batch(texts)

        # 4. Storage of chunks
        # Remove any previous chunks for this document
        db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()

        for c_data, vector in zip(chunks_data, embeddings):
            # Check dimension against provider configuration
            if len(vector) != provider.dimensions:
                raise EmbeddingDimensionMismatchError(expected=provider.dimensions, actual=len(vector))

            chunk_record = DocumentChunk(
                document_id=doc.id,
                user_id=doc.user_id,
                chunk_index=c_data.chunk_index,
                page_number=c_data.page_number,
                content=c_data.content,
                embedding=vector,
            )
            db.add(chunk_record)

        doc.status = DocumentStatus.processed
        doc.error_message = None
        db.commit()
        db.refresh(doc)
        logger.info("Successfully processed document %s (%d chunks)", doc.id, len(chunks_data))
        return doc

    except Exception as exc:
        logger.exception("Failed to process document %s: %s", doc.id, exc)
        doc.status = DocumentStatus.failed
        doc.error_message = str(exc)
        db.commit()
        db.refresh(doc)
        return doc


def list_user_documents(user_id: uuid.UUID, db: Session) -> list[Document]:
    """Retrieve all documents belonging to a user."""
    stmt = (
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def get_user_document(document_id: uuid.UUID, user_id: uuid.UUID, db: Session) -> Document | None:
    """Retrieve a single document owned by user."""
    stmt = select(Document).where(Document.id == document_id, Document.user_id == user_id)
    return db.scalar(stmt)


def delete_user_document(document_id: uuid.UUID, user_id: uuid.UUID, db: Session) -> bool:
    """Delete document owned by user, its DB chunks (via cascade), and file on disk."""
    doc = get_user_document(document_id, user_id, db)
    if not doc:
        return False

    storage_dir = settings.get_storage_path()
    file_path = storage_dir / doc.filename
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception as exc:
            logger.warning("Could not delete file %s from disk: %s", file_path, exc)

    db.delete(doc)
    db.commit()
    return True


def search_user_documents(
    query: str,
    user_id: uuid.UUID,
    db: Session,
    top_k: int = 5,
    document_id: uuid.UUID | None = None,
) -> list[DocumentSearchResult]:
    """Search processed chunks belonging to user using vector cosine similarity.
    
    Supports PostgreSQL with pgvector natively, and falls back to in-memory cosine
    similarity for SQLite or Postgres instances without vector extension.
    Always enforces strict user ownership and validates vector dimensions.
    """
    clean_query = query.strip()
    if not clean_query:
        return []

    provider = get_embedding_provider()
    query_vector = provider.embed_text(clean_query)

    if len(query_vector) != provider.dimensions:
        raise EmbeddingDimensionMismatchError(expected=provider.dimensions, actual=len(query_vector))

    is_postgres = db.bind is not None and db.bind.dialect.name == "postgresql"
    use_pgvector = False

    if is_postgres and provider.dimensions == 768:
        try:
            ext_check = db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar()
            use_pgvector = bool(ext_check)
        except Exception:
            use_pgvector = False

    if use_pgvector:
        # PostgreSQL pgvector query
        stmt = (
            select(
                DocumentChunk,
                Document.original_filename,
                DocumentChunk.embedding.cosine_distance(query_vector).label("distance"),
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                DocumentChunk.user_id == user_id,
                Document.status == DocumentStatus.processed,
                DocumentChunk.embedding.is_not(None),
            )
        )
        if document_id:
            stmt = stmt.where(DocumentChunk.document_id == document_id)

        stmt = stmt.order_by("distance").limit(top_k)
        rows = db.execute(stmt).all()

        results: list[DocumentSearchResult] = []
        for chunk, doc_name, distance in rows:
            # Cosine distance ranges [0, 2], similarity is 1 - distance
            sim_score = max(0.0, 1.0 - float(distance or 0.0))
            results.append(
                DocumentSearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_name=doc_name,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    similarity_score=round(sim_score, 4),
                )
            )
        return results

    # SQLite or fallback in-memory cosine similarity
    stmt = (
        select(DocumentChunk, Document.original_filename)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(
            DocumentChunk.user_id == user_id,
            Document.status == DocumentStatus.processed,
            DocumentChunk.embedding.is_not(None),
        )
    )
    if document_id:
        stmt = stmt.where(DocumentChunk.document_id == document_id)

    rows = db.execute(stmt).all()

    scored: list[tuple[float, DocumentChunk, str]] = []
    for chunk, doc_name in rows:
        embedding = chunk.embedding
        if not embedding or not isinstance(embedding, list):
            continue

        if len(embedding) != len(query_vector):
            # Incompatible vector dimensions; prevent silent mixing
            logger.warning(
                "Chunk %s has embedding dimension %d, expected %d; skipping incompatible vector",
                chunk.id,
                len(embedding),
                len(query_vector),
            )
            continue

        sim = compute_cosine_similarity(query_vector, embedding)
        scored.append((sim, chunk, doc_name))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_candidates = scored[:top_k]

    return [
        DocumentSearchResult(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_name=doc_name,
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            similarity_score=round(sim, 4),
        )
        for sim, chunk, doc_name in top_candidates
    ]
