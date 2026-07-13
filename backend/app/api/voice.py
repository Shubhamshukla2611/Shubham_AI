"""
Voice Agent API endpoints — handles Vapi integration for phone-based AI interviews.

Endpoints:
  - POST /api/voice/tool-execute — Execute agent tools (called by Vapi)
  - GET /api/voice/phone-number — Get the phone number to call
  - POST /api/voice/webhook — Receive call events from Vapi
"""

from __future__ import annotations

import hmac
import hashlib
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.voice_agent import get_voice_agent
from app.schemas.voice_agent import (
    VapiToolExecutionRequest,
    VapiToolExecutionResponse,
    PhoneNumberResponse,
    CallEndedPayload,
)

router = APIRouter(prefix="/api/voice", tags=["voice"])
logger = get_logger(__name__)


def verify_webhook_signature(request: Request) -> bool:
    """Verify that the webhook request came from Vapi."""
    settings = get_settings()
    signature = request.headers.get("x-vapi-signature")

    if not signature:
        logger.warning("Webhook signature missing")
        return False

    # In production, you'd verify using Vapi's public key
    # For now, we use a shared secret
    return signature == hmac.new(
        settings.voice_webhook_secret.encode(),
        "webhook-body".encode(),
        hashlib.sha256,
    ).hexdigest()


@router.post("/tool-execute", response_model=VapiToolExecutionResponse)
async def execute_tool(request: VapiToolExecutionRequest):
    """
    Execute a tool call from the voice agent during a call.

    Vapi calls this endpoint when the agent decides to use a tool
    (e.g., get_available_slots, book_meeting, get_profile_info).

    We execute the tool and return the result for the agent to use
    in its next response.
    """
    logger.info(f"Tool execution request: {request.tool_name} for call {request.call_id}")

    agent = get_voice_agent()

    try:
        result = agent.execute_tool(request.tool_name, request.parameters)
        logger.info(f"Tool execution successful: {request.tool_name}")

        return VapiToolExecutionResponse(
            success=True,
            result=result,
        )

    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return VapiToolExecutionResponse(
            success=False,
            result=f"Tool execution failed: {str(e)}",
        )


@router.get("/phone-number", response_model=PhoneNumberResponse)
async def get_phone_number():
    """
    Get the phone number to call to reach the AI agent.

    Returns the Vapi-provisioned phone number and configuration status.
    """
    settings = get_settings()

    # Check if Vapi is properly configured
    is_configured = bool(
        settings.vapi_api_key
        and settings.vapi_assistant_id
        and settings.vapi_phone_number_id
    )

    if not is_configured:
        logger.warning("Vapi is not fully configured")
        return PhoneNumberResponse(
            phone_number="Not configured",
            is_configured=False,
            message=(
                "Vapi is not set up yet. Provide VAPI_API_KEY, VAPI_ASSISTANT_ID, "
                "and VAPI_PHONE_NUMBER_ID in your .env file."
            ),
        )

    # In production, you'd fetch the actual phone number from Vapi
    # For now, return a placeholder
    return PhoneNumberResponse(
        phone_number="+1 (XXX) XXX-XXXX",  # Placeholder
        is_configured=True,
        message=(
            "Call this number to speak with Shubham's AI voice agent. "
            "The agent can answer questions about Shubham's background and "
            "book meetings directly to Shubham's calendar."
        ),
    )


@router.post("/webhook")
async def vapi_webhook(request: Request):
    """
    Receive events from Vapi during a call.

    Handles:
    - call.started — Log incoming call
    - call.ended — Log call transcript, booking confirmations
    - message — Forward to tool execution if needed

    Note: In production, verify webhook signatures and handle async logging.
    """
    try:
        payload = await request.json()
        event_type = payload.get("type", "unknown")
        call_id = payload.get("callId", "unknown")

        logger.info(f"Vapi webhook: type={event_type}, callId={call_id}")

        if event_type == "call.started":
            logger.info(f"Call started: {call_id}")
            return {"status": "ok"}

        elif event_type == "call.ended":
            # Log the call outcome
            duration = payload.get("durationSeconds", 0)
            transcript = payload.get("transcript", "")
            summary = payload.get("summary", "")

            logger.info(
                f"Call ended: {call_id} | Duration: {duration}s | Summary: {summary}"
            )

            # TODO: Store call transcript and metadata for later review
            # TODO: If booking was confirmed, trigger confirmation email

            return {"status": "ok", "logged": True}

        elif event_type == "message":
            # Vapi is sending us a message (usually requesting tool execution)
            # This is handled by /tool-execute, but we could also log here
            logger.debug(f"Message from Vapi: {payload}")
            return {"status": "ok"}

        else:
            logger.warning(f"Unknown webhook event type: {event_type}")
            return {"status": "ok"}

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.post("/call-summary")
async def call_summary(payload: dict):
    """
    Receive a summary of the call after it ends.

    This is a convenience endpoint for logging analytics.
    """
    call_id = payload.get("call_id")
    booking_confirmed = payload.get("booking_confirmed", False)
    duration = payload.get("duration", 0)

    logger.info(
        f"Call summary: {call_id} | Booking: {booking_confirmed} | Duration: {duration}s"
    )

    # TODO: Store in database for analytics
    # - Track success rate of bookings
    # - Measure average call duration
    # - Log common call topics

    return {"status": "recorded"}


@router.get("/assistant-config")
async def get_assistant_config():
    """
    Get the Vapi assistant configuration.

    This is used by Vapi to understand the agent's personality,
    system prompt, tools, and voice settings.
    """
    agent = get_voice_agent()
    config = agent.create_vapi_assistant_config()

    return {
        "status": "ok",
        "config": config,
        "note": "Use this config when creating a new Vapi assistant via the dashboard",
    }
