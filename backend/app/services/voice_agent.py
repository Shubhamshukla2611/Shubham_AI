"""
Voice Agent service — orchestrates Vapi integration for phone-based AI interviews.

This service:
  - Manages the voice agent personality (system prompt, tools, behavior)
  - Exposes tools for the agent to call: profile info, availability, booking
  - Handles tool execution and formatting responses for voice synthesis
  - Tracks conversation state and booking confirmations
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.calendar import get_calendar_manager

logger = get_logger(__name__)


class VoiceAgent:
    """Orchestrates the AI persona voice agent for phone interviews."""

    def __init__(self):
        self.settings = get_settings()
        self.calendar = get_calendar_manager()

    def get_system_prompt(self) -> str:
        """Return the system prompt for the voice agent."""
        return """You are Shubham Shukla's AI representative. You are intelligent, personable, and professional.

Your role:
1. Introduce yourself as Shubham's AI voice agent
2. Provide information about Shubham's background, skills, and experience when asked
3. Engage naturally in conversation—no rigid Q&A trees
4. If asked about something you don't know, say so honestly (e.g., "I'm not sure about that specific detail, but Shubham can cover it in our meeting")
5. Help the caller understand Shubham's fit for the role or opportunity
6. When the caller is ready, propose available meeting times from Shubham's calendar
7. Confirm the meeting and send them a calendar invite automatically

Key information about Shubham:
- Full-stack AI engineer with expertise in LLMs, RAG, embeddings, and voice AI
- Strong background in Python, TypeScript, FastAPI, and React
- Experienced with production ML pipelines, real-time systems, and scalable architectures
- Passionate about building human-centered AI products
- Located in India, flexible with timezone coordination
- Available for immediate engagements

Tone: Warm, professional, confident but not arrogant. Remember: you represent Shubham, so be helpful and genuine.

When the caller wants to schedule:
1. Ask what duration they need (typically 30 or 60 minutes)
2. Call get_available_slots() to fetch times
3. Present 3-5 options conversationally ("How about Tuesday at 10 AM? Or if that doesn't work...")
4. Once confirmed, call book_meeting() with their email
5. Confirm the booking verbally and let them know they'll get a calendar invite
"""

    def get_tools(self) -> list[dict]:
        """Return the list of tools the agent can call."""
        return [
            {
                "name": "get_available_slots",
                "description": (
                    "Fetch available meeting slots from Shubham's calendar. "
                    "Returns a list of proposed times. Call this when the caller wants to schedule."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Meeting duration in minutes (default 30)",
                            "default": 30,
                        },
                        "days_ahead": {
                            "type": "integer",
                            "description": "How many days forward to look (default 7)",
                            "default": 7,
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "book_meeting",
                "description": (
                    "Book a confirmed meeting slot on Shubham's calendar. "
                    "The caller must have agreed to the time. Sends a calendar invite automatically."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_time": {
                            "type": "string",
                            "description": "Start time in ISO format (e.g., 2026-07-15T10:00:00+00:00)",
                        },
                        "end_time": {
                            "type": "string",
                            "description": "End time in ISO format",
                        },
                        "attendee_email": {
                            "type": "string",
                            "description": "Email of the person being interviewed",
                        },
                        "attendee_name": {
                            "type": "string",
                            "description": "Name of the person being interviewed",
                        },
                    },
                    "required": ["start_time", "end_time", "attendee_email"],
                },
            },
            {
                "name": "get_profile_info",
                "description": (
                    "Retrieve information about Shubham's background, skills, and experience. "
                    "Use this when the caller asks questions about qualifications."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": (
                                "Topic to retrieve (e.g., 'background', 'skills', 'experience', 'projects'). "
                                "If not specified, returns a brief summary."
                            ),
                        },
                    },
                    "required": [],
                },
            },
        ]

    def execute_tool(self, tool_name: str, parameters: dict) -> str:
        """
        Execute a tool call from the voice agent and return a formatted response.

        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters

        Returns:
            Formatted response string for the voice agent to read aloud
        """
        logger.info(f"Executing tool: {tool_name} with params: {parameters}")

        try:
            if tool_name == "get_available_slots":
                return self._handle_get_available_slots(parameters)
            elif tool_name == "book_meeting":
                return self._handle_book_meeting(parameters)
            elif tool_name == "get_profile_info":
                return self._handle_get_profile_info(parameters)
            else:
                return f"I'm not sure how to handle that request. Can you try again?"

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return f"I encountered an issue processing that. Let me check with Shubham and we can try again."

    def _handle_get_available_slots(self, parameters: dict) -> str:
        """Fetch available slots and format them for voice."""
        duration = parameters.get("duration_minutes", 30)
        days = parameters.get("days_ahead", 7)

        slots = self.calendar.get_available_slots(
            duration_minutes=duration,
            days_ahead=days,
        )

        if not slots:
            return (
                "I'm not finding availability in the next week. "
                "Let me check with Shubham directly—can I get your email so he can reach out to coordinate?"
            )

        # Format slots for voice readout
        options = []
        for i, slot in enumerate(slots[:3], 1):
            options.append(slot.get("display", slot["start"]))

        if len(slots) == 1:
            response = f"I have one slot available: {options[0]}. Does that work for you?"
        else:
            response = f"Here are a few times that work: {', '.join(options)}. What's best for your schedule?"

        # Store slots in memory for booking confirmation later
        return response

    def _handle_book_meeting(self, parameters: dict) -> str:
        """Book a confirmed meeting and send calendar invite."""
        start_time = parameters.get("start_time")
        end_time = parameters.get("end_time")
        attendee_email = parameters.get("attendee_email")
        attendee_name = parameters.get("attendee_name", "Guest")

        if not all([start_time, end_time, attendee_email]):
            return "I need a confirmed time, email, and name to book. Can you provide those details?"

        # Format the meeting title
        title = f"Chat with {attendee_name} - Shubham Shukla AI Interview"

        event_id = self.calendar.book_meeting(
            title=title,
            start_time=start_time,
            end_time=end_time,
            attendee_email=attendee_email,
            description=(
                f"Virtual meeting between Shubham Shukla and {attendee_name}. "
                f"Calendar invite sent to {attendee_email}. "
                f"Google Meet link included."
            ),
        )

        if event_id:
            logger.info(f"Successfully booked meeting: {event_id}")
            return (
                f"Perfect! I've confirmed your meeting with Shubham on {start_time}. "
                f"You'll receive a calendar invite at {attendee_email} shortly with a Google Meet link. "
                f"Looking forward to speaking with you then!"
            )
        else:
            return (
                "I had trouble booking that time. "
                "Can I get your email so Shubham can reach out to coordinate directly?"
            )

    def _handle_get_profile_info(self, parameters: dict) -> str:
        """Retrieve profile information from RAG or fallback."""
        topic = parameters.get("topic", "").lower()

        # This would normally query the RAG system for rich profile data
        # For now, return a curated summary

        summaries = {
            "background": (
                "Shubham is a full-stack AI engineer with 3+ years of experience "
                "building production machine learning systems and voice AI products. "
                "He specializes in LLMs, retrieval-augmented generation, and real-time systems."
            ),
            "skills": (
                "His core skills include Python, TypeScript, FastAPI, React, LLM orchestration, "
                "vector databases, embeddings, speech-to-text, and deployment at scale. "
                "He's proficient with tools like Groq, ChromaDB, Vapi, and AWS."
            ),
            "experience": (
                "Shubham has led projects ranging from RAG chatbots to voice agents to real-time "
                "search systems. He's experienced with both early-stage startups and scaling systems for production."
            ),
            "projects": (
                "Recent projects include this AI persona voice agent system, a RAG-powered knowledge "
                "base platform, and several real-time ML inference pipelines."
            ),
        }

        return summaries.get(topic, summaries.get("background"))

    def create_vapi_assistant_config(self) -> dict:
        """Generate the Vapi assistant configuration."""
        return {
            "name": "Shubham's AI Voice Agent",
            "model": {
                "provider": "groq",
                "model": self.settings.groq_model,
                "temperature": 0.7,
                "messages": [
                    {
                        "role": "system",
                        "content": self.get_system_prompt(),
                    }
                ],
            },
            "voice": {
                "provider": "11labs",
                "voiceId": "burt",  # Warm, confident male voice
            },
            "tools": self.get_tools(),
            "analysisPlan": {
                "successEvaluationPlan": (
                    "Check if the call resulted in a confirmed meeting booking with valid email and time."
                ),
                "summaryPrompt": (
                    "Summarize the call: Was a meeting booked? If so, who will attend and when? "
                    "What were the caller's main questions?"
                ),
            },
        }


# Singleton instance
_voice_agent: Optional[VoiceAgent] = None


def get_voice_agent() -> VoiceAgent:
    """Get or create the singleton voice agent."""
    global _voice_agent
    if _voice_agent is None:
        _voice_agent = VoiceAgent()
    return _voice_agent
