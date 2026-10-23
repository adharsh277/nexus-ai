import io
import uuid
from pathlib import Path

import docx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.user import User
from app.services.documents.service import process_document
from app.services.embeddings import MockEmbeddingProvider, override_embedding_provider
from tests.conftest import act_as


def _make_pdf(text: str = "Nexus AI Document Content") -> bytes:
    stream_content = f"BT\n/F1 12 Tf\n100 700 Td\n({text}) Tj\nET\n".encode("latin-1")
    stream_len = len(stream_content)
    header = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    )
    body = (
        f"5 0 obj\n<< /Length {stream_len} >>\nstream\n".encode("latin-1")
        + stream_content
        + b"\nendstream\nendobj\n"
    )
    trailer = (
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000244 00000 n \n"
        b"0000000318 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
        b"startxref\n450\n%%EOF\n"
    )
    return header + body + trailer



def test_upload_valid_text_document(client: TestClient, user: User, db):
    file_content = b"Nexus AI is an autonomous, local-first artificial intelligence assistant."
    resp = client.post(
        "/api/documents/upload?background=false",
        files={"file": ("guide.txt", file_content, "text/plain")},
    )
    assert resp.status_code == 201
    data = resp.json()

    assert data["id"] is not None
    assert data["original_filename"] == "guide.txt"
    assert data["mime_type"] == "text/plain"
    assert data["file_size"] == len(file_content)
    assert data["status"] == "processed"

    # Verify physical file exists and uses UUID
    storage_filename = data["filename"]
    assert storage_filename != "guide.txt"
    assert storage_filename.endswith(".txt")
    storage_path = settings.get_storage_path() / storage_filename
    assert storage_path.exists()
    assert storage_path.read_bytes() == file_content

    # Clean up storage file
    if storage_path.exists():
        storage_path.unlink()


def test_upload_size_limit_rejection(client: TestClient, monkeypatch):
    # Set limit to 500 bytes for test
    monkeypatch.setattr(settings, "document_max_file_size_bytes", 500)
    large_content = b"x" * 600

    resp = client.post(
        "/api/documents/upload",
        files={"file": ("large.txt", large_content, "text/plain")},
    )
    assert resp.status_code == 413


def test_upload_invalid_extension(client: TestClient):
    resp = client.post(
        "/api/documents/upload",
        files={"file": ("script.py", b"print('hello')", "text/x-python")},
    )
    assert resp.status_code == 400
    assert "Unsupported file extension" in resp.json()["error"]["message"]


def test_upload_corrupted_pdf(client: TestClient):
    resp = client.post(
        "/api/documents/upload",
        files={"file": ("corrupt.pdf", b"Not a real PDF", "application/pdf")},
    )
    assert resp.status_code == 400
    assert "Missing %PDF-" in resp.json()["error"]["message"]


def test_document_listing_and_detail(client: TestClient, user: User, db):
    pdf_bytes = _make_pdf("Doc 1")
    resp1 = client.post(
        "/api/documents/upload?background=false",
        files={"file": ("doc1.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp1.status_code == 201
    doc_id = resp1.json()["id"]

    # List documents
    list_resp = client.get("/api/documents")
    assert list_resp.status_code == 200
    docs = list_resp.json()
    assert len(docs) >= 1
    assert any(d["id"] == doc_id for d in docs)

    # Get single document
    detail_resp = client.get(f"/api/documents/{doc_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == doc_id

    # Get document chunks
    chunks_resp = client.get(f"/api/documents/{doc_id}/chunks")
    assert chunks_resp.status_code == 200
    chunks = chunks_resp.json()
    assert len(chunks) >= 1
    assert chunks[0]["page_number"] == 1


def test_ownership_isolation(client: TestClient, user: User, other_user: User, db):
    # Upload document as User A
    resp_a = client.post(
        "/api/documents/upload?background=false",
        files={"file": ("secret_a.txt", b"User A confidential information", "text/plain")},
    )
    assert resp_a.status_code == 201
    doc_a_id = resp_a.json()["id"]

    # Switch identity to User B (other_user)
    act_as(other_user)

    # User B listing should NOT include User A's document
    list_resp_b = client.get("/api/documents")
    assert list_resp_b.status_code == 200
    assert not any(d["id"] == doc_a_id for d in list_resp_b.json())

    # User B direct access should return 404
    assert client.get(f"/api/documents/{doc_a_id}").status_code == 404
    assert client.get(f"/api/documents/{doc_a_id}/chunks").status_code == 404
    assert client.delete(f"/api/documents/{doc_a_id}").status_code == 404

    # User B search should not return User A's chunks
    search_resp = client.post(
        "/api/documents/search",
        json={"query": "confidential", "top_k": 5},
    )
    assert search_resp.status_code == 200
    assert len(search_resp.json()["results"]) == 0

    # User B searching scoped to doc_a_id should return 404
    scoped_resp = client.post(
        "/api/documents/search",
        json={"query": "confidential", "document_id": doc_a_id},
    )
    assert scoped_resp.status_code == 404

    # Switch back to User A
    act_as(user)


def test_document_deletion_and_cascade(client: TestClient, user: User, db):
    file_bytes = b"Temporary doc content for deletion test."
    resp = client.post(
        "/api/documents/upload?background=false",
        files={"file": ("temp.txt", file_bytes, "text/plain")},
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]
    storage_filename = resp.json()["filename"]
    storage_path = settings.get_storage_path() / storage_filename
    assert storage_path.exists()

    # Delete document
    del_resp = client.delete(f"/api/documents/{doc_id}")
    assert del_resp.status_code == 204

    # Ensure document and chunks are deleted from DB
    assert db.scalar(select(Document).where(Document.id == uuid.UUID(doc_id))) is None
    chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(doc_id))).all()
    assert len(chunks) == 0

    # Ensure file is removed from disk
    assert not storage_path.exists()


def test_processing_failure_updates_state_safely(client: TestClient, user: User, db):
    # Upload document
    resp = client.post(
        "/api/documents/upload?background=false",
        files={"file": ("failing.txt", b"Some content", "text/plain")},
    )
    doc_id = uuid.UUID(resp.json()["id"])

    # Simulate embedding failure during processing
    failing_provider = MockEmbeddingProvider(simulate_error="rate_limit")
    override_embedding_provider(failing_provider)

    try:
        updated_doc = process_document(doc_id, db)
        assert updated_doc.status == DocumentStatus.failed
        assert updated_doc.error_message is not None
        assert "rate limit" in updated_doc.error_message.lower()

        # Re-query DB to verify persistence of failed status
        db.refresh(updated_doc)
        assert updated_doc.status == DocumentStatus.failed
    finally:
        override_embedding_provider(None)


def test_semantic_vector_search(client: TestClient, user: User, db):
    content_k8s = "Kubernetes is a container orchestration system for automating application deployment."
    content_docker = "Docker provides containerization software to build and ship container images."
    content_python = "Python is a high-level programming language emphasizing code readability."

    # Upload and process documents
    client.post(
        "/api/documents/upload?background=false",
        files={"file": ("k8s.txt", content_k8s.encode(), "text/plain")},
    )
    client.post(
        "/api/documents/upload?background=false",
        files={"file": ("docker.txt", content_docker.encode(), "text/plain")},
    )
    client.post(
        "/api/documents/upload?background=false",
        files={"file": ("python.txt", content_python.encode(), "text/plain")},
    )

    # Perform search
    search_resp = client.post(
        "/api/documents/search",
        json={"query": "container orchestration deployment", "top_k": 2},
    )
    assert search_resp.status_code == 200
    data = search_resp.json()
    assert data["query"] == "container orchestration deployment"
    results = data["results"]
    assert len(results) <= 2
    assert len(results) > 0

    # Top result should have source metadata and high similarity
    top = results[0]
    assert "chunk_id" in top
    assert "document_id" in top
    assert "document_name" in top
    assert "page_number" in top
    assert "similarity_score" in top
    assert top["similarity_score"] >= 0.0


def test_search_handles_dimension_mismatch_without_silent_corruption(client: TestClient, user: User, db):
    # Insert a document and chunk with a dummy 384-dimensional vector into DB
    doc = Document(
        user_id=user.id,
        filename="custom.txt",
        original_filename="custom.txt",
        mime_type="text/plain",
        file_size=10,
        status=DocumentStatus.processed,
    )
    db.add(doc)
    db.commit()

    chunk = DocumentChunk(
        document_id=doc.id,
        user_id=user.id,
        chunk_index=0,
        page_number=1,
        content="Incompatible vector chunk",
        embedding=[0.01] * 384,  # 384 dimensions, while mock provider produces 768
    )
    db.add(chunk)
    db.commit()

    # Search with standard 768-dim provider
    # It should safely skip the 384-dim chunk instead of crashing or silently producing corrupt scores
    search_resp = client.post(
        "/api/documents/search",
        json={"query": "test query", "top_k": 5},
    )
    assert search_resp.status_code == 200
    results = search_resp.json()["results"]
    assert not any(r["chunk_id"] == str(chunk.id) for r in results)
