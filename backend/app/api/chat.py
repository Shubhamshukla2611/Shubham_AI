"""
Chat API endpoint — main entry point for the RAG chatbot.

Wires the retriever, generator, and RAG pipeline to handle incoming chat
requests. The vector store and embeddings client are initialized once at
startup and reused for every request.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.chat import ChatRequest, ChatResponse, Source
from app.services.embeddings import EmbeddingsClient
from app.services.generator import Generator
from app.services.rag import RAGPipeline
from app.services.retriever import Retriever
from app.services.vector_store import VectorStore

router = APIRouter(prefix="/api", tags=["chat"])
logger = get_logger(__name__)

# Global instances (initialized on first request)
_rag_pipeline: RAGPipeline | None = None
_vector_store: VectorStore | None = None


def _get_rag_pipeline() -> RAGPipeline:
    """Lazy-initialize the RAG pipeline on first use.

    This ensures the vector store is loaded and embeddings client is
    ready before any chat requests arrive. Subsequent calls reuse the
    same instances.
    """
    global _rag_pipeline, _vector_store

    if _rag_pipeline is not None:
        return _rag_pipeline

    settings = get_settings()

    # Validate API key early — embeddings are local so only the LLM key matters.
    if not settings.is_api_key_configured:
        raise RuntimeError(
            "Groq API key not configured. Set GROQ_API_KEY in backend/.env"
        )

    logger.info("Initializing RAG pipeline...")

    # 1. Initialize local embeddings client (sentence-transformers MiniLM).
    #    No API key — model is loaded on first embed.
    embeddings_client = EmbeddingsClient(
        model=settings.embedding_model,
        dim=settings.embedding_dim,
    )

    # 2. Initialize vector store and load the index (ChromaDB PersistentClient).
    index_dir = Path(__file__).resolve().parent.parent.parent / "data" / "index"
    _vector_store = VectorStore(
        index_dir=index_dir,
        embedding_dim=embeddings_client.embedding_dim,
    )

    if not _vector_store.is_built:
        raise RuntimeError(
            f"Vector store not built. Run 'python scripts/ingest.py --force' first."
        )

    _vector_store.load()
    logger.info("Vector store loaded | vectors=%d", _vector_store.size)

    # 3. Initialize retriever
    retriever = Retriever(
        vector_store=_vector_store,
        embeddings_client=embeddings_client,
        top_k=settings.retrieval_top_k,
        min_score=settings.min_score,
    )

    # 4. Initialize generator (Groq LLM)
    generator = Generator(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
    )

    # 5. Wire the RAG pipeline
    _rag_pipeline = RAGPipeline(
        retriever=retriever,
        generator=generator,
    )

    logger.info("RAG pipeline ready")
    return _rag_pipeline


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send a message to the persona chatbot",
    description=(
        "Accepts a user message, retrieves relevant context from the "
        "knowledge base, and returns a grounded answer with source citations."
    ),
)
async def chat(request: ChatRequest) -> ChatResponse:
    """Process a chat message through the full RAG pipeline."""
    logger.info("Chat request | message_len=%d", len(request.message))

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Get or initialize the RAG pipeline
    try:
        rag = _get_rag_pipeline()
    except RuntimeError as exc:
        logger.error("RAG pipeline initialization failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    # Run the RAG pipeline
    try:
        result = rag.answer(request.message)
    except Exception as exc:
        logger.exception("RAG pipeline execution failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to process your question. Please try again.",
        ) from exc

    # Convert sources to response model
    sources = [
        Source(
            source=s["source"],
            content=s["content"],
            score=s["score"],
        )
        for s in result["sources"]
    ]

    return ChatResponse(
        answer=result["answer"],
        sources=sources,
        booking_url=result.get("booking_url"),
        meeting_url=result.get("meeting_url"),
        owner_email=result.get("owner_email"),
        interviewer_email=result.get("interviewer_email"),
    )