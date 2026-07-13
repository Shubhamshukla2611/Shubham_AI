"""Typed application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. Values are loaded from backend/.env.

    The Groq API key is intentionally optional at startup so the server
    can boot and serve /health, /, and /docs even without a key. Services
    that actually call the Groq API check `is_api_key_configured` and
    raise a clear error if a key is missing.

    Embeddings are local via sentence-transformers and need no API key.
    """

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Groq API ────────────────────────────────────────────────────────
    groq_api_key: str = Field(
        default="",
        description=(
            "Groq API key. Get one free at https://console.groq.com/keys. "
            "Optional at startup; required to call AI endpoints."
        ),
    )
    groq_model: str = Field(
        default="llama-3.1-8b-instant",
        description="Groq chat model identifier.",
    )

    # ─── Embeddings (local) ──────────────────────────────────────────────
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description=(
            "HuggingFace sentence-transformers model id. Local — no API key. "
            "Default produces 384-dim normalized vectors."
        ),
    )
    embedding_dim: int = Field(
        default=384,
        ge=64,
        le=4096,
        description="Vector dimensionality. Must match the embedding model.",
    )

    # ─── RAG Configuration ────────────────────────────────────────────────
    retrieval_top_k: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Number of chunks to retrieve per query.",
    )
    chunk_size: int = Field(
        default=1500,
        ge=200,
        le=8000,
        description="Maximum characters per chunk.",
    )
    chunk_overlap: int = Field(
        default=300,
        ge=0,
        le=2000,
        description="Character overlap between consecutive chunks.",
    )
    min_score: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum cosine similarity score (0.0-1.0) for a chunk to be "
            "included in retrieval. Tune up for stricter grounding."
        ),
    )

    # ─── Calendar Booking ────────────────────────────────────────────────
    google_calendar_url: str = Field(
        default="",
        description=(
            "Public Google Calendar booking/appointment scheduling URL."
        ),
    )

    # Backward-compatible alias for earlier generic booking support.
    calendar_booking_url: str = Field(
        default="",
        description=(
            "Public booking URL for Calendly, Cal.com, or a Google Calendar "
            "appointment scheduling page."
        ),
    )

    google_meet_url: str = Field(
        default="https://meet.google.com/new",
        description="Google Meet URL used when generating an interview invite.",
    )

    owner_email: str = Field(
        default="shubhamshu382@gmail.com",
        description="Primary owner email that should receive booking invites automatically.",
    )

    # Optional interviewer contact to share booking confirmations with.
    interviewer_email: str = Field(
        default="",
        description="Email address of the interviewer/host who should receive the booking invite.",
    )

    # ─── Voice Agent (Vapi + Google Calendar) ────────────────────────────
    vapi_api_key: str = Field(
        default="",
        description="Vapi API key for phone voice agent. Get at https://dashboard.vapi.ai",
    )

    vapi_assistant_id: str = Field(
        default="",
        description="Vapi Assistant ID for the voice agent personality.",
    )

    vapi_phone_number_id: str = Field(
        default="",
        description="Vapi phone number ID (Twilio-managed phone number).",
    )

    twilio_auth_token: str = Field(
        default="",
        description="Twilio auth token for Vapi integration.",
    )

    google_calendar_credentials_json: str = Field(
        default="",
        description=(
            "JSON string of Google Calendar service account credentials for "
            "checking availability and auto-booking. Get from Google Cloud Console."
        ),
    )

    voice_webhook_secret: str = Field(
        default="dev-secret-change-in-production",
        description="Secret token for validating Vapi webhooks.",
    )

    # ─── CORS ──────────────────────────────────────────────────────────────
    allowed_origins: str = Field(
        default="http://localhost:5173",
        description="Comma-separated list of allowed CORS origins.",
    )

    # ─── Server ────────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = Field(default="INFO")

    @property
    def is_api_key_configured(self) -> bool:
        """True if a non-placeholder Groq API key is set."""
        key = (self.groq_api_key or "").strip()
        return bool(key) and key != "your_groq_api_key_here"

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse comma-separated origins into a list."""
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def is_calendar_booking_configured(self) -> bool:
        """True if a booking URL has been configured."""
        return bool((self.google_calendar_url or self.calendar_booking_url or "").strip())

    @property
    def google_calendar_booking_url(self) -> str:
        """Return the configured Google Calendar booking URL, falling back to the legacy generic field."""
        return (self.google_calendar_url or self.calendar_booking_url or "").strip()

    @property
    def google_meet_booking_url(self) -> str:
        """Return the configured Google Meet URL used for interview invites."""
        return (self.google_meet_url or "https://meet.google.com/new").strip()

    @property
    def interviewer_contact_email(self) -> str:
        """Return the configured interviewer email, if any."""
        return (self.interviewer_email or "").strip()

    @property
    def owner_contact_email(self) -> str:
        """Return the primary owner email used for booking invites."""
        return (self.owner_email or "shubhamshu382@gmail.com").strip()


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Reads .env once at first call."""
    return Settings()