"""
Production ingestion script — builds the ChromaDB index from data/raw/.

Usage:
    python scripts/ingest.py
    python scripts/ingest.py --input data/raw --output data/index
    python scripts/ingest.py --force       # rebuild even if index exists
    python scripts/ingest.py --verbose     # extra logging

Pipeline stages:
    1. Load all documents from data/raw/ (PDF, MD, DOCX, TXT, JSON)
    2. Split into overlapping chunks
    3. Generate local MiniLM embeddings (sentence-transformers)
    4. Build a ChromaDB collection under data/index/chroma/
    5. Persist sidecar index_meta.json

Re-running without --force is a no-op if the index already exists
with the correct dimension. Use --force to rebuild after adding
new documents or changing the chunk size / embedding model.

On first run, the MiniLM model is downloaded (~80 MB) to the
HuggingFace cache (~/.cache/huggingface/). Subsequent runs use the
cached weights and pay only the model-load cost (~1 sec).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Make `app` importable when invoked as `python scripts/ingest.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.services.chunker import chunk_documents
from app.services.document_loader import load_documents
from app.services.embeddings import EmbeddingsClient
from app.services.vector_store import VectorStore


def _print_banner(title: str) -> None:
    """Print a section banner for readable CLI output."""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def _print_summary(docs_count: int, chunks_count: int, elapsed: float) -> None:
    """Print a final summary table."""
    print()
    print("+" + "-" * 68 + "+")
    print("|{:^68s}|".format("INGESTION COMPLETE"))
    print("+" + "-" * 22 + "+" + "-" * 22 + "+" + "-" * 22 + "+")
    print("| {:<20s} | {:<20s} | {:<20s} |".format("Stage", "Result", "Notes"))
    print("+" + "-" * 22 + "+" + "-" * 22 + "+" + "-" * 22 + "+")
    print("| {:<20s} | {:<20s} | {:<20s} |".format(
        "Documents", f"{docs_count} loaded", "PDF/MD/DOCX/TXT/JSON"
    ))
    print("| {:<20s} | {:<20s} | {:<20s} |".format(
        "Chunks", f"{chunks_count} created", "from document text"
    ))
    print("| {:<20s} | {:<20s} | {:<20s} |".format(
        "Total time", f"{elapsed:.1f}s", "end-to-end"
    ))
    print("+" + "-" * 22 + "+" + "-" * 22 + "+" + "-" * 22 + "+")


def run_ingestion(
    input_dir: Path,
    output_dir: Path,
    force: bool = False,
) -> int:
    """Execute the full ingestion pipeline.

    Args:
        input_dir: Directory containing source documents.
        output_dir: Directory where the Chroma collection will be written.
        force: If True, rebuild even if an index already exists.

    Returns:
        Process exit code (0 on success, non-zero on failure).
    """
    settings = get_settings()

    # Note: no API key check — embeddings are local.
    print("=" * 70)
    print("  AI Persona Chatbot — Ingestion Pipeline")
    print("=" * 70)
    print(f"  Input:     {input_dir}")
    print(f"  Output:    {output_dir}")
    print(f"  Model:     {settings.embedding_model} (local)")
    print(f"  Dim:       {settings.embedding_dim}")
    print(f"  Chunking:  {settings.chunk_size} chars / {settings.chunk_overlap} overlap")
    print(f"  Top-K:     {settings.retrieval_top_k}")
    print(f"  Min score: {settings.min_score}")
    print(f"  Force:     {force}")
    print()

    if not input_dir.exists():
        print(f"[ERROR] Input directory does not exist: {input_dir}")
        print("        Create it and add your resume + project files.")
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Stage 1: Load documents ──────────────────────────────────────────
    _print_banner("[1/5] Loading documents")
    docs = load_documents(input_dir)
    if not docs:
        print(f"[ERROR] No supported documents found in {input_dir}")
        print("        Supported formats: .pdf, .docx, .md, .txt, .json")
        return 1
    print(f"  [OK] Loaded {len(docs)} document(s):")
    for d in docs:
        size_kb = len(d.text) / 1024
        print(f"        - {d.source:<25s} {size_kb:>6.1f} KB  ({d.metadata.get('word_count', 0)} words)")

    # ── Stage 2: Chunk ───────────────────────────────────────────────────
    _print_banner("[2/5] Chunking documents")
    chunks = chunk_documents(
        docs,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    if not chunks:
        print("[ERROR] Chunking produced no chunks — check your documents.")
        return 1
    print(f"  [OK] Produced {len(chunks)} chunk(s)")
    by_source: dict[str, int] = {}
    for c in chunks:
        by_source[c.source] = by_source.get(c.source, 0) + 1
    for source, count in sorted(by_source.items()):
        print(f"        - {source:<25s} {count:>3d} chunk(s)")

    # ── Stage 3: Initialize embeddings client (local MiniLM) ────────────
    _print_banner("[3/5] Initializing MiniLM embeddings (local)")
    client = EmbeddingsClient(
        model=settings.embedding_model,
        dim=settings.embedding_dim,
    )
    # Pre-load the model and run a probe so the first chunk embed is fast.
    print(f"  [INFO] Warming up model: {settings.embedding_model}...")
    warmup_start = time.perf_counter()
    client.warmup()
    warmup_elapsed = time.perf_counter() - warmup_start
    print(f"  [OK] Model ready in {warmup_elapsed:.1f}s")
    print(f"        Dim:    {client.embedding_dim}")

    # ── Stage 4: Build / rebuild check ──────────────────────────────────
    store = VectorStore(index_dir=output_dir, embedding_dim=client.embedding_dim)
    if store.is_built and not force:
        print()
        print(f"  [SKIP] Index already exists at {output_dir}")
        print("         Use --force to rebuild (e.g., after adding new documents).")
        print()
        print("  Current index:")
        print(f"        Path:    {output_dir}")
        print(f"        Vectors: {store.size}")
        return 0

    if force:
        print("  [INFO] --force specified: rebuilding from scratch")

    # ── Stage 5: Embed + build index ────────────────────────────────────
    _print_banner("[4/5] Generating embeddings")
    print(f"  [INFO] Embedding {len(chunks)} chunk(s)...", flush=True)
    embed_start = time.perf_counter()
    vectors = client.embed_texts([c.text for c in chunks])
    embed_elapsed = time.perf_counter() - embed_start
    print(f"  [OK] {len(vectors)} vectors generated in {embed_elapsed:.1f}s")
    print(f"        Avg per chunk: {(embed_elapsed * 1000) / max(1, len(vectors)):.0f}ms")

    _print_banner("[5/5] Building ChromaDB collection")
    build_start = time.perf_counter()
    store.build(chunks=chunks, embeddings=vectors)
    build_elapsed = time.perf_counter() - build_start

    print(f"  [OK] Collection built in {build_elapsed * 1000:.0f}ms")
    print(f"        Vectors:  {store.size}")
    print(f"        Location: {output_dir}")
    print()
    print("  Files written:")
    for f in sorted(output_dir.rglob("*")):
        if f.is_file():
            size_kb = f.stat().st_size / 1024
            print(f"        {str(f.relative_to(output_dir)):<25s} {size_kb:>8.1f} KB")

    total_elapsed = time.perf_counter() - (embed_start - embed_elapsed)
    _print_summary(len(docs), len(chunks), total_elapsed)

    print()
    print("  Next steps:")
    print("    1. Set GROQ_API_KEY in backend/.env (get a free key at https://console.groq.com/keys)")
    print("    2. Start the backend:   cd backend && uvicorn app.main:app --reload --port 8001")
    print("    3. Start the frontend:  cd ../frontend && npm run dev")
    print("    4. Open http://localhost:5173 in your browser")
    print()
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="ingest.py",
        description="Build the ChromaDB index for the AI Persona Chatbot.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/ingest.py                  # use default paths
  python scripts/ingest.py --force          # rebuild existing index
  python scripts/ingest.py --input docs/    # custom input dir
  python scripts/ingest.py --verbose        # enable DEBUG logging
        """,
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Input directory containing source documents (default: data/raw)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory for the Chroma collection (default: data/index)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild the index even if one already exists",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = parse_args(argv)

    log_level = "DEBUG" if args.verbose else "INFO"
    configure_logging(log_level)
    logger = get_logger(__name__)

    # Resolve default paths relative to backend/ regardless of CWD.
    backend_dir = Path(__file__).resolve().parent.parent
    input_dir = (args.input or (backend_dir / "data" / "raw")).resolve()
    output_dir = (args.output or (backend_dir / "data" / "index")).resolve()

    logger.debug("Resolved input_dir=%s output_dir=%s", input_dir, output_dir)

    try:
        return run_ingestion(
            input_dir=input_dir,
            output_dir=output_dir,
            force=args.force,
        )
    except KeyboardInterrupt:
        print()
        print("[INFO] Ingestion cancelled by user.")
        return 130
    except Exception as exc:  # noqa: BLE001 — top-level safety net
        logger.exception("Ingestion failed: %s", exc)
        print(f"[ERROR] Ingestion failed: {exc}")
        print("        Run with --verbose for full traceback.")
        return 1


if __name__ == "__main__":
    sys.exit(main())