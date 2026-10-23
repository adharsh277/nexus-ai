from app.services.documents.chunker import (
    chunk_document_sections,
    chunk_text,
)
from app.services.documents.extractor import ExtractedSection


def test_chunk_small_text_single_chunk():
    text = "Short introductory text."
    chunks = chunk_text(text, chunk_size=500, chunk_overlap=100, page_number=1)
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].page_number == 1
    assert chunks[0].content == text


def test_chunk_empty_text():
    assert chunk_text("", chunk_size=500) == []
    assert chunk_text("   \n\t  ", chunk_size=500) == []


def test_chunking_with_overlap_and_sentence_preservation():
    sentences = [
        "Artificial intelligence is transforming software engineering across many disciplines.",
        "Nexus AI provides local-first autonomy combined with cloud reasoning capabilities.",
        "Vector databases allow high-dimensional semantic search over unstructured knowledge bases.",
        "Overlapping chunking prevents loss of semantic context between adjacent text fragments.",
        "Docker ensures reproducible container environments for backend and database services.",
    ]
    full_text = " ".join(sentences)

    chunk_size = 180
    chunk_overlap = 60
    chunks = chunk_text(full_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap, page_number=2)

    assert len(chunks) > 1

    # Check indices are sequential
    for idx, c in enumerate(chunks):
        assert c.chunk_index == idx
        assert c.page_number == 2
        assert len(c.content) > 0

    # Verify overlap exists between consecutive chunks
    for i in range(len(chunks) - 1):
        c1 = chunks[i].content
        c2 = chunks[i + 1].content

        words1 = set(c1.split())
        words2 = set(c2.split())
        shared_words = words1.intersection(words2)
        # There should be shared words due to chunk overlap
        assert len(shared_words) > 0, f"Expected overlap between chunk {i} and {i+1}"


def test_chunk_document_sections_preserves_page_numbers():
    sections = [
        ExtractedSection(page_number=1, text="Page 1 introduction to machine learning principles."),
        ExtractedSection(page_number=2, text="Page 2 deep dive into transformer architectures and attention."),
        ExtractedSection(page_number=3, text="Page 3 evaluation metrics including recall, precision, and F1."),
    ]

    chunks = chunk_document_sections(sections, chunk_size=200, chunk_overlap=50)
    assert len(chunks) == 3

    assert chunks[0].chunk_index == 0
    assert chunks[0].page_number == 1
    assert "Page 1" in chunks[0].content

    assert chunks[1].chunk_index == 1
    assert chunks[1].page_number == 2
    assert "Page 2" in chunks[1].content

    assert chunks[2].chunk_index == 2
    assert chunks[2].page_number == 3
    assert "Page 3" in chunks[2].content


def test_chunking_handles_unusually_long_sentences():
    # Test very long sentence without punctuation
    words = [f"word{i}" for i in range(100)]
    long_text = " ".join(words)

    chunks = chunk_text(long_text, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    # Check all chunks have bounded size
    for c in chunks:
        assert len(c.content) <= 120
