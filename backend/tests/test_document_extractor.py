import io
import tempfile
from pathlib import Path

import docx
import pytest

from app.services.documents.extractor import (
    ALLOWED_EXTENSIONS,
    DocumentExtractionError,
    DocumentValidationError,
    extract_document_text,
    validate_file_content,
)


def _create_sample_pdf(text: str = "Nexus AI Architecture Document") -> bytes:
    # Minimal standard PDF with valid Helvetica font dictionary
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



def _create_sample_docx(paragraphs: list[str], table_rows: list[list[str]] | None = None) -> bytes:
    doc = docx.Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    if table_rows:
        table = doc.add_table(rows=len(table_rows), cols=len(table_rows[0]))
        for r_idx, row in enumerate(table_rows):
            for c_idx, val in enumerate(row):
                table.rows[r_idx].cells[c_idx].text = val
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_allowed_extensions_and_mime_types():
    assert ".pdf" in ALLOWED_EXTENSIONS
    assert ".docx" in ALLOWED_EXTENSIONS
    assert ".txt" in ALLOWED_EXTENSIONS
    assert ".md" in ALLOWED_EXTENSIONS


def test_validate_file_content_valid_text_and_markdown():
    txt_mime = validate_file_content("notes.txt", b"Hello Nexus AI")
    assert txt_mime == "text/plain"

    md_mime = validate_file_content("guide.md", b"# Nexus AI Guide\nDetails here")
    assert md_mime == "text/markdown"


def test_validate_file_content_valid_pdf_and_docx():
    pdf_bytes = _create_sample_pdf()
    pdf_mime = validate_file_content("sample.pdf", pdf_bytes)
    assert pdf_mime == "application/pdf"

    docx_bytes = _create_sample_docx(["Hello world"])
    docx_mime = validate_file_content("sample.docx", docx_bytes)
    assert docx_mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_validate_file_content_unsupported_extension():
    with pytest.raises(DocumentValidationError, match="Unsupported file extension"):
        validate_file_content("image.png", b"\x89PNG\r\n\x1a\n")

    with pytest.raises(DocumentValidationError, match="File has no extension"):
        validate_file_content("noextension", b"text")


def test_validate_file_content_size_limit():
    content = b"a" * 1000
    with pytest.raises(DocumentValidationError, match="exceeds the maximum allowed limit"):
        validate_file_content("doc.txt", content, max_size_bytes=500)


def test_validate_file_content_empty_file():
    with pytest.raises(DocumentValidationError, match="File is empty"):
        validate_file_content("empty.txt", b"")


def test_validate_file_content_corrupted_pdf():
    with pytest.raises(DocumentValidationError, match="Missing %PDF-"):
        validate_file_content("fake.pdf", b"Not a pdf at all")


def test_validate_file_content_corrupted_docx():
    with pytest.raises(DocumentValidationError, match="Missing standard ZIP"):
        validate_file_content("fake.docx", b"Not a docx at all")


def test_validate_file_content_binary_file_in_text():
    with pytest.raises(DocumentValidationError, match="Binary file detected"):
        validate_file_content("binary.txt", b"Binary \x00 data here")


def test_extract_text_file(tmp_path: Path):
    txt_path = tmp_path / "test.txt"
    txt_path.write_text("Line 1\nLine 2", encoding="utf-8")

    sections = extract_document_text(txt_path)
    assert len(sections) == 1
    assert sections[0].page_number == 1
    assert "Line 1\nLine 2" in sections[0].text


def test_extract_markdown_file(tmp_path: Path):
    md_path = tmp_path / "test.md"
    md_path.write_text("# Title\n\nContent paragraph.", encoding="utf-8")

    sections = extract_document_text(md_path)
    assert len(sections) == 1
    assert sections[0].page_number == 1
    assert "Title" in sections[0].text
    assert "Content paragraph." in sections[0].text


def test_extract_pdf_file(tmp_path: Path):
    pdf_bytes = _create_sample_pdf("Page 1 of Kubernetes documentation.")
    pdf_path = tmp_path / "k8s.pdf"
    pdf_path.write_bytes(pdf_bytes)

    sections = extract_document_text(pdf_path)
    assert len(sections) >= 1
    assert sections[0].page_number == 1
    assert "Kubernetes" in sections[0].text


def test_extract_docx_file(tmp_path: Path):
    docx_bytes = _create_sample_docx(
        paragraphs=["First paragraph of Nexus notes.", "Second paragraph."],
        table_rows=[["Feature", "Status"], ["Embeddings", "Complete"]],
    )
    docx_path = tmp_path / "notes.docx"
    docx_path.write_bytes(docx_bytes)

    sections = extract_document_text(docx_path)
    assert len(sections) == 1
    assert sections[0].page_number == 1
    assert "First paragraph of Nexus notes." in sections[0].text
    assert "Feature | Status" in sections[0].text
    assert "Embeddings | Complete" in sections[0].text


def test_extract_nonexistent_file(tmp_path: Path):
    with pytest.raises(DocumentExtractionError, match="File not found"):
        extract_document_text(tmp_path / "missing.pdf")
