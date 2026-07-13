"""
Text chunker: splits long documents into overlapping chunks.

The chunker uses a recursive character splitter that tries to break
on natural boundaries (paragraphs, then sentences, then words) before
falling back to hard character cuts. This preserves semantic meaning
within each chunk — critical for good retrieval quality.

Overlap is essential: without it, a sentence that spans a chunk
boundary would be lost to the retriever. With overlap, the same
sentence appears in two adjacent chunks so any query that touches it
can find relevant context.

Each chunk carries:
  - chunk_id: globally unique (doc_id + index) used by FAISS
  - text: the chunk content
  - source: filename for citation in the UI
  - doc_id: which document it came from
  - metadata: char indices into the original document (for source
    highlighting in Phase 3+)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from app.core.logging import get_logger
from app.services.document_loader import LoadedDocument

logger = get_logger(__name__)


# ─── Separator hierarchy ────────────────────────────────────────────────────
# We try these in order, picking the first that appears in the text.
# Newlines and double-newlines come first because they almost always
# mark paragraph boundaries in well-structured documents.
SEPARATORS: tuple[str, ...] = (
    "\n\n",   # paragraph break
    "\n",     # line break
    ". ",     # sentence end
    "? ",     # question
    "! ",     # exclamation
    "; ",     # semicolon
    ", ",     # clause
    " ",      # word
    "",       # hard character cut (last resort)
)


@dataclass
class Chunk:
    """A single chunk of text ready for embedding."""

    chunk_id: str
    doc_id: str
    source: str
    text: str
    index: int  # position of this chunk within its document
    metadata: dict = field(default_factory=dict)


# ─── Core recursive splitter ───────────────────────────────────────────────


def _merge_small_pieces(pieces: list[str], chunk_size: int) -> list[str]:
    """Greedily merge small pieces into chunks that fit chunk_size.

    Walks the pieces left-to-right, accumulating characters into a
    buffer until adding the next piece would exceed chunk_size. The
    buffer is then emitted as a chunk and a new buffer starts. This
    is simpler and more predictable than the classic LangChain
    recursive approach and is fast enough for our scale (<100k chars).
    """
    if not pieces:
        return []

    chunks: list[str] = []
    buffer = pieces[0]

    for piece in pieces[1:]:
        # +1 for the separator we will insert between pieces.
        if len(buffer) + len(piece) + 1 <= chunk_size:
            buffer = f"{buffer} {piece}".strip()
        else:
            if buffer:
                chunks.append(buffer)
            buffer = piece

    if buffer:
        chunks.append(buffer)

    return chunks


def _split_with_separator(text: str, separator: str, chunk_size: int) -> list[str]:
    """Split text on a separator, then merge pieces back into chunks.

    If the separator is the empty string we hard-cut the text into
    chunk_size slices — this is the last-resort fallback that
    guarantees progress on adversarial inputs (e.g. a single 50k-char
    run with no whitespace).
    """
    if separator == "":
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    # Split but keep the separator out of the resulting pieces; the
    # merge step inserts single spaces between pieces anyway.
    raw_pieces = text.split(separator)
    # Filter empty pieces (consecutive separators) and strip.
    pieces = [p.strip() for p in raw_pieces if p and p.strip()]
    return _merge_small_pieces(pieces, chunk_size)


def _recursive_split(text: str, chunk_size: int, separators: Iterable[str]) -> list[str]:
    """Recursively split text using the first separator that appears.

    For each candidate separator we check whether it occurs in the
    text. The first one that does is used to split, and we recurse
    on any resulting piece that is still too large.
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    for sep in separators:
        if sep and sep in text:
            chunks = _split_with_separator(text, sep, chunk_size)
            # Recurse on any oversized chunk with the next separators.
            refined: list[str] = []
            next_seps = separators  # same tuple — recursion is bounded by chunk_size
            for chunk in chunks:
                if len(chunk) > chunk_size:
                    refined.extend(_recursive_split(chunk, chunk_size, next_seps))
                else:
                    refined.append(chunk)
            return refined

    # No separator matched (extremely rare) — hard cut.
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
    """Prepend the tail of the previous chunk to each subsequent chunk.

    The first chunk is emitted unchanged. This is intentionally simple:
    character-based overlap rather than token-based, which keeps the
    implementation dependency-free. The overlap is capped to half the
    chunk length to avoid pathological cases where overlap >= chunk.
    """
    if overlap <= 0 or len(chunks) <= 1:
        return chunks

    out: list[str] = [chunks[0]]
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        effective_overlap = min(overlap, max(1, len(prev) // 2))
        tail = prev[-effective_overlap:].strip()
        if tail:
            out.append(f"{tail} {chunks[i]}".strip())
        else:
            out.append(chunks[i])
    return out


# ─── Public API ────────────────────────────────────────────────────────────


def chunk_document(
    document: LoadedDocument,
    chunk_size: int = 2000,
    chunk_overlap: int = 400,
) -> list[Chunk]:
    """Split a single document into overlapping chunks.

    Args:
        document: A loaded document from the document loader.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Target overlap between consecutive chunks.

    Returns:
        List of `Chunk` objects with stable ids and source metadata.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be >= 0")
    if chunk_overlap >= chunk_size:
        logger.warning(
            "chunk_overlap (%d) >= chunk_size (%d) — overlap will be capped",
            chunk_overlap,
            chunk_size,
        )

    text = document.text.strip()
    if not text:
        return []

    base_chunks = _recursive_split(text, chunk_size, SEPARATORS)
    final_chunks = _apply_overlap(base_chunks, chunk_overlap)

    # Trim each chunk and drop any that became empty after stripping.
    trimmed: list[str] = [c.strip() for c in final_chunks if c and c.strip()]

    chunks: list[Chunk] = []
    for idx, chunk_text in enumerate(trimmed):
        chunks.append(
            Chunk(
                chunk_id=f"{document.doc_id}::{idx:04d}",
                doc_id=document.doc_id,
                source=document.source,
                text=chunk_text,
                index=idx,
                metadata={
                    "format": document.format,
                    "char_count": len(chunk_text),
                    "word_count": len(chunk_text.split()),
                    **document.metadata,
                },
            )
        )

    logger.info(
        "Chunked %s | input_chars=%d chunks=%d avg_chunk=%d",
        document.source,
        len(text),
        len(chunks),
        len(text) // max(1, len(chunks)),
    )
    return chunks


def chunk_documents(
    documents: list[LoadedDocument],
    chunk_size: int = 2000,
    chunk_overlap: int = 400,
) -> list[Chunk]:
    """Chunk every document and concatenate the results.

    Chunk ids are globally unique because they embed the source
    doc_id, so downstream code (FAISS, retriever) never has to worry
    about collisions across documents.
    """
    all_chunks: list[Chunk] = []
    for doc in documents:
        all_chunks.extend(chunk_document(doc, chunk_size=chunk_size, chunk_overlap=chunk_overlap))

    logger.info(
        "Chunked %d document(s) | total_chunks=%d total_chars=%d",
        len(documents),
        len(all_chunks),
        sum(len(c.text) for c in all_chunks),
    )
    return all_chunks
