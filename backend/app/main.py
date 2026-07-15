"""
FastAPI application entrypoint.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.chat import _get_rag_pipeline, router as chat_router
from app.api.voice import router as voice_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.services.vector_store import VectorStore


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__)

    logger.info("=" * 60)
    logger.info("  AI Persona Chatbot — starting up")
    logger.info("  env:               %s", settings.app_env)
    logger.info("  log level:         %s", settings.log_level)
    logger.info(
        "  Groq API key:      %s",
        "configured" if settings.is_api_key_configured else "MISSING (AI endpoints will fail)",
    )
    logger.info("  Groq model:        %s", settings.groq_model)
    logger.info("  Embedding model:   %s", settings.embedding_model)
    logger.info("  Embedding dim:     %d", settings.embedding_dim)
    logger.info("  Min score:         %.2f", settings.min_score)
    logger.info("  Retrieval top-k:   %d", settings.retrieval_top_k)
    logger.info("  CORS:              %s", settings.allowed_origins_list)
    logger.info("=" * 60)

    try:
        _get_rag_pipeline()
        logger.info("RAG pipeline initialized successfully")
    except Exception as e:
        # Most common cause on a fresh Render deploy: the persistent disk
        # is empty so the Chroma index has not been built yet. Try to
        # build it from /app/backend/data/raw on the fly.
        logger.warning("RAG pipeline init failed: %s", e)
        try:
            _auto_ingest_if_needed(logger)
            _get_rag_pipeline()
            logger.info("RAG pipeline initialized after auto-ingest")
        except Exception as inner:
            logger.exception("Auto-ingest failed: %s", inner)

    yield

    logger.info("AI Persona Chatbot — shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    logger = get_logger(__name__)

    app = FastAPI(
        title="AI Persona Chatbot",
        version="0.1.0",
        description="RAG-powered persona chatbot for Shubham Shukla.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(
        _request: Request, exc: ValidationError
    ) -> JSONResponse:
        logger.warning("Validation error: %s", exc.errors())
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "message": "Request payload failed validation.",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(
        _request: Request, exc: ValueError
    ) -> JSONResponse:
        logger.warning("ValueError: %s", exc)
        return JSONResponse(
            status_code=400,
            content={"error": "bad_request", "message": str(exc)},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred. Please try again.",
            },
        )

    @app.get("/api", tags=["meta"])
    async def api_info() -> dict:
        return {
            "name": "AI Persona Chatbot",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/health",
            "api_key_configured": settings.is_api_key_configured,
            "endpoints": {
                "chat": "POST /api/chat",
                "voice_phone_number": "GET /api/voice/phone-number",
                "voice_tool_execute": "POST /api/voice/tool-execute",
                "voice_webhook": "POST /api/voice/webhook",
            },
        }

    @app.get("/health", tags=["meta"])
    async def healthcheck() -> dict:
        return {
            "status": "ok",
            "env": settings.app_env,
            "api_key_configured": settings.is_api_key_configured,
        }

    app.include_router(chat_router)
    app.include_router(voice_router)

    logger.info("Application created | routes registered")
    return app


def _auto_ingest_if_needed(logger) -> None:
    """Build the Chroma index from data/raw if one is not yet on disk.

    Triggered on first deploy to a fresh Render persistent disk. Mirrors
    the logic in scripts/ingest.py but invoked in-process so the app can
    recover without a manual `python scripts/ingest.py` step.
    """
    settings = get_settings()
    backend_root = Path(__file__).resolve().parent.parent
    raw_dir = backend_root / "data" / "raw"
    index_dir = backend_root / "data" / "index"

    # Fallback for /app working dir layouts.
    if not raw_dir.exists():
        alt_raw = Path("/app/backend/data/raw")
        if alt_raw.exists():
            raw_dir = alt_raw
    if not index_dir.exists():
        alt_idx = Path("/app/backend/data/index")
        if alt_idx.parent.exists():
            index_dir = alt_idx

    logger.info(
        "Auto-ingest probe | raw_dir=%s exists=%s index_dir=%s exists=%s",
        raw_dir, raw_dir.exists(), index_dir, index_dir.exists(),
    )

    raw_files = (
        list(raw_dir.glob("*.md")) + list(raw_dir.glob("*.pdf"))
        if raw_dir.exists() else []
    )
    if not raw_files:
        logger.error("No source documents in %s — cannot auto-ingest", raw_dir)
        raise RuntimeError(f"No source documents in {raw_dir}")

    logger.info("Auto-ingest: %d source files found | %s", len(raw_files), [p.name for p in raw_files])

    index_dir.mkdir(parents=True, exist_ok=True)
    probe = VectorStore(index_dir=index_dir, embedding_dim=settings.embedding_dim)
    if probe.is_built:
        logger.info("Chroma index already present on disk — skipping auto-ingest")
        return

    logger.info("Auto-ingest: building Chroma index from %s", raw_dir)

    # Import here so the function is optional and avoids pulling the
    # ingestion pipeline into the request path on every cold start.
    from app.services.chunker import chunk_documents
    from app.services.document_loader import load_documents
    from app.services.embeddings import EmbeddingsClient

    documents = load_documents(raw_dir)
    if not documents:
        raise RuntimeError(f"No documents loaded from {raw_dir}")

    chunks = chunk_documents(
        documents,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    if not chunks:
        raise RuntimeError("Chunker produced 0 chunks")

    logger.info("Auto-ingest: chunked into %d chunks", len(chunks))

    embeddings_client = EmbeddingsClient(
        model=settings.embedding_model,
        dim=settings.embedding_dim,
    )
    embeddings_client.warmup()  # ensures model is loaded before batch encode

    vectors: list[list[float]] = []
    batch_size = EmbeddingsClient.DEFAULT_BATCH_SIZE
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        vectors.extend(embeddings_client.embed_texts([c.text for c in batch]))

    store = VectorStore(index_dir=index_dir, embedding_dim=settings.embedding_dim)
    store.build(chunks=chunks, embeddings=vectors)
    logger.info("Auto-ingest complete | chunks=%d", len(chunks))


app = create_app()