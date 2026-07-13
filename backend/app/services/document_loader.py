"""
Document loader: reads PDF, DOCX, MD, TXT, and JSON files.

Converts heterogeneous source documents into a uniform list of
`LoadedDocument` dictionaries. Each carries the text content, a
human-readable source label, format-specific metadata, and a stable
document id used downstream by the chunker.

The loader is intentionally tolerant: a single corrupt file is logged
and skipped rather than aborting the whole ingestion run. This matters
when ingesting dozens of files at once.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from app.core.logging import get_logger

logger = get_logger(__name__)


# File extensions we know how to handle. Anything else is skipped
# with a clear log line so the user can rename or convert it.
SUPPORTED_EXTENSIONS: set[str] = {".pdf", ".docx", ".md", ".markdown", ".txt", ".json"}


@dataclass
class LoadedDocument:
    """A single document loaded from disk, ready for chunking.

    Attributes:
        doc_id: Stable identifier (filename stem) used by the chunker
            to derive chunk ids and by the UI to label sources.
        text: Full extracted text content.
        source: Human-readable source label (filename).
        format: Lowercase file extension without the dot.
        metadata: Free-form format-specific info (page count, word
            count, JSON keys, etc.) surfaced to the UI later.
        path: Absolute path on disk — useful for debugging and for
            the ingestion script to log what was processed.
    """

    doc_id: str
    text: str
    source: str
    format: str
    metadata: dict = field(default_factory=dict)
    path: str = ""


# ─── Per-format readers ────────────────────────────────────────────────────
# Each reader returns plain text. The loader is responsible for
# orchestrating them and packaging the result into LoadedDocument.


def _read_pdf(path: Path) -> str:
    """Extract text from a PDF using pypdf.

    We iterate every page and join with double newlines so paragraph
    boundaries are preserved. Pages with no extractable text (scanned
    images) silently contribute an empty string — they are not fatal
    but they will produce no chunks downstream.
    """
    from pypdf import PdfReader  # local import: pypdf is heavy

    reader = PdfReader(str(path))
    page_count = len(reader.pages)
    parts: list[str] = []
    for idx, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 — pypdf raises many types
            logger.warning("PDF page extract failed | file=%s page=%d err=%s", path.name, idx, exc)
            text = ""
        if text.strip():
            parts.append(text)

    logger.info("PDF loaded | file=%s pages=%d non_empty=%d", path.name, page_count, len(parts))
    return "\n\n".join(parts)


def _read_docx(path: Path) -> str:
    """Extract text from a DOCX using python-docx.

    We walk the body in document order and emit one paragraph per
    block. Tables are flattened row-by-row because their semantic
    structure is rarely preserved well by the retriever anyway.
    """
    from docx import Document  # local import

    doc = Document(str(path))
    parts: list[str] = []

    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)

    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    logger.info("DOCX loaded | file=%s paragraphs=%d", path.name, len(parts))
    return "\n\n".join(parts)


def _read_markdown(path: Path) -> str:
    """Read a Markdown file as plain text.

    We deliberately do NOT strip Markdown syntax — keeping the raw
    syntax helps the retriever match technical terms that appear
    inside code fences, links, and headings.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    # Collapse runs of 3+ blank lines down to 2 — chunker handles the rest.
    text = re.sub(r"\n{3,}", "\n\n", text)
    logger.info("Markdown loaded | file=%s chars=%d", path.name, len(text))
    return text


def _read_text(path: Path) -> str:
    """Read a plain text file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"\n{3,}", "\n\n", text)
    logger.info("Text loaded | file=%s chars=%d", path.name, len(text))
    return text


def _read_json(path: Path) -> str:
    """Read a JSON file and convert it to readable text.

    Used for structured persona data (Phase 3) and any project that
    ships configuration as JSON. We pretty-print and concatenate
    string leaves so the retriever can match on actual values.
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse failed | file=%s err=%s — falling back to raw text", path.name, exc)
        return raw

    def flatten(obj: object, prefix: str = "") -> Iterator[str]:
        if isinstance(obj, dict):
            for key, value in obj.items():
                label = f"{prefix}.{key}" if prefix else key
                yield from flatten(value, label)
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                yield from flatten(item, f"{prefix}[{idx}]")
        elif isinstance(obj, str):
            yield f"{prefix}: {obj}"
        elif obj is not None:
            yield f"{prefix}: {obj}"

    text = "\n".join(flatten(data))
    logger.info("JSON loaded | file=%s chars=%d", path.name, len(text))
    return text


_READERS = {
    ".pdf": _read_pdf,
    ".docx": _read_docx,
    ".md": _read_markdown,
    ".markdown": _read_markdown,
    ".txt": _read_text,
    ".json": _read_json,
}


# ─── Public API ────────────────────────────────────────────────────────────


def _is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def _build_metadata(text: str, fmt: str, raw_path: Path) -> dict:
    """Cheap metadata used for source display and debugging."""
    word_count = len(text.split())
    char_count = len(text)
    meta: dict = {
        "char_count": char_count,
        "word_count": word_count,
        "format": fmt,
    }
    if fmt == "pdf":
        try:
            from pypdf import PdfReader

            meta["page_count"] = len(PdfReader(str(raw_path)).pages)
        except Exception:  # noqa: BLE001
            pass
    return meta


def load_document(path: Path) -> LoadedDocument | None:
    """Load a single file. Returns None if unsupported or unreadable.

    Errors are logged and swallowed so a single bad file cannot
    poison an entire ingestion run. Callers receive a clean list
    of successfully loaded documents.
    """
    if not path.is_file():
        logger.warning("Skipping non-file path: %s", path)
        return None

    ext = path.suffix.lower()
    if ext not in _READERS:
        logger.info("Skipping unsupported file: %s (extension=%s)", path.name, ext)
        return None

    reader = _READERS[ext]
    try:
        text = reader(path)
    except Exception as exc:  # noqa: BLE001 — we want to catch any reader failure
        logger.error("Failed to load %s: %s", path.name, exc)
        return None

    if not text or not text.strip():
        logger.warning("Loaded empty document: %s", path.name)
        return None

    return LoadedDocument(
        doc_id=path.stem,
        text=text,
        source=path.name,
        format=ext.lstrip("."),
        metadata=_build_metadata(text, ext.lstrip("."), path),
        path=str(path.resolve()),
    )


def load_documents(source_dir: str | Path) -> list[LoadedDocument]:
    """Load every supported file in `source_dir` (non-recursive).

    Args:
        source_dir: Directory to scan. Created if it does not exist
            so the function is safe to call during early bootstrapping.

    Returns:
        Sorted list of `LoadedDocument` objects. Empty if the directory
        has no supported files.
    """
    source_path = Path(source_dir)
    if not source_path.exists():
        logger.warning("Source directory does not exist: %s — creating it", source_path)
        source_path.mkdir(parents=True, exist_ok=True)
        return []

    candidates = sorted(p for p in source_path.iterdir() if p.is_file() and _is_supported(p))

    if not candidates:
        logger.warning("No supported files found in %s", source_path)
        return []

    logger.info("Loading %d document(s) from %s", len(candidates), source_path)

    documents: list[LoadedDocument] = []
    for path in candidates:
        doc = load_document(path)
        if doc is not None:
            documents.append(doc)

    logger.info(
        "Loaded %d/%d document(s) successfully | total_chars=%d",
        len(documents),
        len(candidates),
        sum(len(d.text) for d in documents),
    )
    return documents
