"""
Pydantic models for the voice agent API.

Handles Vapi webhook payloads for tool execution and call transcripts.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class VapiToolCall(BaseModel):
    """A tool execution request from Vapi during a call."""

    name: str = Field(..., description="Tool name to execute")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")


class VapiMessageRequest(BaseModel):
    """Message from Vapi containing tool calls or transcripts."""

    call_id: str = Field(..., alias="callId", description="Unique call ID")
    message_type: str = Field(
        ..., alias="type", description="Type of message: 'tool-call', 'transcript', 'call-ended'"
    )
    tool_calls: list[VapiToolCall] = Field(
        default_factory=list, alias="toolCalls", description="List of tool calls to execute"
    )
    transcript: Optional[str] = Field(
        default=None, description="Conversation transcript (if message_type='transcript')"
    )
    assistant_message: Optional[str] = Field(
        default=None, alias="assistantMessage", description="Last assistant message"
    )
    user_message: Optional[str] = Field(
        default=None, alias="userMessage", description="Last user message"
    )


class VapiToolResponse(BaseModel):
    """Response to a tool execution."""

    tool_name: str = Field(..., description="Name of the tool that was called")
    result: str = Field(..., description="Result or error message to return to the agent")


class VapiToolExecutionRequest(BaseModel):
    """Request to execute a tool and return the result."""

    call_id: str = Field(..., description="Call ID for context")
    tool_name: str = Field(..., description="Tool to execute")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")


class VapiToolExecutionResponse(BaseModel):
    """Response from tool execution endpoint."""

    success: bool = Field(..., description="Whether tool executed successfully")
    result: str = Field(..., description="Result to return to the voice agent")


class CallStartedPayload(BaseModel):
    """Payload when a Vapi call starts."""

    call_id: str = Field(..., alias="callId")
    customer_number: Optional[str] = Field(
        default=None, alias="customerNumber", description="Caller phone number (if available)"
    )
    assistant_id: str = Field(..., alias="assistantId")
    timestamp: str = Field(...)


class ToolResultPayload(BaseModel):
    """Vapi sending back tool execution results for further processing."""

    call_id: str = Field(..., alias="callId")
    tool_name: str = Field(..., alias="toolName")
    tool_result: str = Field(..., alias="toolResult")


class CallEndedPayload(BaseModel):
    """Payload when a Vapi call ends."""

    call_id: str = Field(..., alias="callId")
    duration_seconds: int = Field(..., alias="durationSeconds")
    transcript: Optional[str] = Field(default=None)
    summary: Optional[str] = Field(default=None)
    booking_confirmed: bool = Field(
        default=False,
        alias="bookingConfirmed",
        description="Whether a meeting was booked during this call",
    )
    booked_email: Optional[str] = Field(
        default=None, alias="bookedEmail", description="Email of the person booked"
    )


class PhoneNumberResponse(BaseModel):
    """Response containing the phone number to call."""

    phone_number: str = Field(..., description="Phone number to call the AI agent")
    is_configured: bool = Field(
        default=False, description="Whether Vapi is properly configured"
    )
    message: str = Field(..., description="Additional context or setup instructions")
