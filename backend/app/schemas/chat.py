"""
Pydantic models for the chat API.

Full chat history support and streaming response are added in
later steps. This is the minimal contract for Step 1.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's question or message.",
    )
    conversation_id: str | None = Field(
        default=None,
        description="Optional conversation ID for multi-turn memory (Phase 2+).",
    )


class Source(BaseModel):
    """A retrieved source chunk returned with the answer."""

    source: str = Field(..., description="Source filename or identifier.")
    content: str = Field(..., description="The retrieved chunk text.")
    score: float = Field(..., description="Similarity score (0-1, higher is better).")


class ChatResponse(BaseModel):
    """Response body for POST /api/chat."""

    answer: str = Field(..., description="The generated answer.")
    sources: list[Source] = Field(
        default_factory=list,
        description="Retrieved source chunks that grounded the answer.",
    )
    booking_url: str | None = Field(
        default=None,
        description="Optional public booking URL for calendar scheduling flows.",
    )
    meeting_url: str | None = Field(
        default=None,
        description="Optional Google Meet URL for the interview invite.",
    )
    owner_email: str | None = Field(
        default=None,
        description="Primary owner email to include on booking invites.",
    )
    interviewer_email: str | None = Field(
        default=None,
        description="Optional interviewer email to copy on booking confirmations.",
    )
