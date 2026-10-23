import re
from dataclasses import dataclass
from typing import Sequence

from app.services.documents.extractor import ExtractedSection


@dataclass
class DocumentChunkData:
    chunk_index: int
    page_number: int | None
    content: str


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences, preserving punctuation."""
    # Split after sentence-ending punctuation followed by whitespace
    raw_sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in raw_sentences if s.strip()]
    return sentences if sentences else [text.strip()]


def _split_paragraph(paragraph: str, max_chars: int) -> list[str]:
    """Break a paragraph into pieces that are each <= max_chars where possible."""
    if len(paragraph) <= max_chars:
        return [paragraph]

    sentences = _split_into_sentences(paragraph)
    pieces: list[str] = []
    current_piece: list[str] = []
    current_len = 0

    for sent in sentences:
        if len(sent) > max_chars:
            # Word-level fallback for unusually long single sentences (e.g. unpunctuated text or logs)
            if current_piece:
                pieces.append(" ".join(current_piece))
                current_piece = []
                current_len = 0

            words = sent.split()
            word_piece: list[str] = []
            word_len = 0
            for w in words:
                if word_len + len(w) + 1 > max_chars and word_piece:
                    pieces.append(" ".join(word_piece))
                    word_piece = [w]
                    word_len = len(w)
                else:
                    word_piece.append(w)
                    word_len += len(w) + 1
            if word_piece:
                pieces.append(" ".join(word_piece))
        elif current_len + len(sent) + 1 > max_chars:
            if current_piece:
                pieces.append(" ".join(current_piece))
            current_piece = [sent]
            current_len = len(sent)
        else:
            current_piece.append(sent)
            current_len += len(sent) + 1

    if current_piece:
        pieces.append(" ".join(current_piece))

    return pieces


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    page_number: int | None = None,
    start_index: int = 0,
) -> list[DocumentChunkData]:
    """Split a single text string into overlapping chunks honoring sentence and paragraph boundaries."""
    text = text.strip()
    if not text:
        return []

    if len(text) <= chunk_size:
        return [DocumentChunkData(chunk_index=start_index, page_number=page_number, content=text)]

    # Split into paragraphs
    raw_paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not raw_paragraphs:
        raw_paragraphs = [text]

    # Break paragraphs into atomic sentence units (or word units for oversized sentences)
    atomic_units: list[str] = []
    for p in raw_paragraphs:
        for sent in _split_into_sentences(p):
            if len(sent) > chunk_size:
                words = sent.split()
                buf: list[str] = []
                curr_l = 0
                for w in words:
                    if curr_l + len(w) + 1 > chunk_size and buf:
                        atomic_units.append(" ".join(buf))
                        buf = [w]
                        curr_l = len(w)
                    else:
                        buf.append(w)
                        curr_l += len(w) + 1
                if buf:
                    atomic_units.append(" ".join(buf))
            else:
                atomic_units.append(sent)


    chunks: list[DocumentChunkData] = []
    chunk_index = start_index
    start_idx = 0

    while start_idx < len(atomic_units):
        curr_units: list[str] = []
        curr_len = 0
        end_idx = start_idx

        while end_idx < len(atomic_units):
            unit = atomic_units[end_idx]
            add_len = len(unit) + (1 if curr_units else 0)
            if curr_len + add_len <= chunk_size or not curr_units:
                curr_units.append(unit)
                curr_len += add_len
                end_idx += 1
            else:
                break

        chunk_content = " ".join(curr_units).strip()
        if chunk_content:
            chunks.append(
                DocumentChunkData(
                    chunk_index=chunk_index,
                    page_number=page_number,
                    content=chunk_content,
                )
            )
            chunk_index += 1

        if end_idx >= len(atomic_units):
            break

        # Calculate next start_idx based on chunk_overlap
        next_start_idx = end_idx
        overlap_len = 0
        while next_start_idx > start_idx + 1:
            prev_len = len(atomic_units[next_start_idx - 1]) + 1
            if overlap_len + prev_len <= chunk_overlap or next_start_idx == end_idx:
                overlap_len += prev_len
                next_start_idx -= 1
            else:
                break

        if next_start_idx <= start_idx:
            next_start_idx = start_idx + 1

        start_idx = next_start_idx

    return chunks



def chunk_document_sections(
    sections: Sequence[ExtractedSection],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[DocumentChunkData]:
    """Chunk all sections from a document while maintaining sequential chunk indices and page numbers."""
    all_chunks: list[DocumentChunkData] = []
    current_index = 0

    for section in sections:
        if not section.text or not section.text.strip():
            continue
        section_chunks = chunk_text(
            text=section.text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            page_number=section.page_number,
            start_index=current_index,
        )
        all_chunks.extend(section_chunks)
        current_index += len(section_chunks)

    return all_chunks
