"""
FastAPI application entrypoint.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.chat import router as chat_router
from app.api.voice import router as voice_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger


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


app = create_app()