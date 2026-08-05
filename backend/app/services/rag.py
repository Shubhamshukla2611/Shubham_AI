"""
RAG orchestrator: the only service the API layer calls.

Combines retriever + generator into a single `answer()` call that:
  1. Retrieves relevant chunks from the vector store
  2. Generates a grounded answer using Gemini
  3. Returns the answer + source citations
"""

from __future__ import annotations

from typing import AsyncIterator

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.generator import Generator
from app.services.retriever import Retriever

logger = get_logger(__name__)


class RAGPipeline:
    """End-to-end RAG pipeline: retrieve → generate → cite.

    Args:
        retriever: Initialized Retriever instance.
        generator: Initialized Generator instance.
    """

    def __init__(self, retriever: Retriever, generator: Generator) -> None:
        self._retriever = retriever
        self._generator = generator
        logger.info("RAGPipeline initialized | retriever.top_k=%d", retriever.top_k)

    def answer(self, query: str) -> dict:
        """Answer a user query with sources.

        Returns:
            Dict with 'answer' (str) and 'sources' (list of dicts).
            Each source dict has: source (filename), text (chunk), score.
        """
        logger.info("RAGPipeline.answer | query_len=%d", len(query))

        # 0. Booking intent: return a calendar link if the user wants a slot.
        booking_response = self._calendar_booking_answer(query)
        if booking_response is not None:
            logger.info("Calendar booking intent detected")
            return booking_response

        # 1. Simple persona fallback for generic questions that don't need retrieval.
        fallback_answer = self._generic_persona_answer(query)
        if fallback_answer is not None:
            logger.info("Generic persona fallback used")
            return {
                "answer": fallback_answer,
                "sources": [],
                "booking_url": None,
                "meeting_url": None,
                "owner_email": None,
                "interviewer_email": None,
            }

        # 2. Retrieve relevant chunks
        try:
            retrieval_results = self._retriever.retrieve(query)
        except ValueError as exc:
            logger.warning("Retrieval failed: %s", exc)
            return {
                "answer": "Your question was too short. Please ask something more specific.",
                "sources": [],
                "booking_url": None,
                "meeting_url": None,
                "owner_email": None,
                "interviewer_email": None,
            }

        logger.info("Retrieve OK | chunks=%d", len(retrieval_results))

        # 2. Generate answer (passing retrieval results)
        try:
            answer = self._generator.generate(query, retrieval_results)
        except RuntimeError as exc:
            logger.error("Generation failed: %s", exc)
            return {
                "answer": "I encountered an error while processing your question. Please try again.",
                "sources": [],
                "booking_url": None,
                "meeting_url": None,
                "owner_email": None,
                "interviewer_email": None,
            }

        # 3. Format sources from retrieved chunks
        sources = [
            {
                "source": r.chunk.source,
                "content": r.chunk.text,
                "score": r.score,
            }
            for r in retrieval_results
        ]

        logger.info("RAGPipeline.answer OK | answer_len=%d sources=%d", len(answer), len(sources))

        return {
            "answer": answer,
            "sources": sources,
            "booking_url": None,
            "meeting_url": None,
            "owner_email": None,
            "interviewer_email": None,
        }

    async def answer_stream(self, query: str) -> AsyncIterator[dict]:
        """Stream a RAG answer event-by-event."""
        logger.info("RAGPipeline.answer_stream | query_len=%d", len(query))

        booking_response = self._calendar_booking_answer(query)
        if booking_response is not None:
            logger.info("Calendar booking intent detected")
            yield {"type": "delta", "text": booking_response["answer"]}
            yield {
                "type": "done",
                "sources": booking_response["sources"],
                "booking_url": booking_response["booking_url"],
                "meeting_url": booking_response["meeting_url"],
                "owner_email": booking_response["owner_email"],
                "interviewer_email": booking_response["interviewer_email"],
            }
            return

        fallback_answer = self._generic_persona_answer(query)
        if fallback_answer is not None:
            logger.info("Generic persona fallback used")
            yield {"type": "delta", "text": fallback_answer}
            yield {
                "type": "done",
                "sources": [],
                "booking_url": None,
                "meeting_url": None,
                "owner_email": None,
                "interviewer_email": None,
            }
            return

        try:
            retrieval_results = self._retriever.retrieve(query)
        except ValueError as exc:
            logger.warning("Retrieval failed: %s", exc)
            yield {
                "type": "done",
                "answer": "Your question was too short. Please ask something more specific.",
                "sources": [],
                "booking_url": None,
                "meeting_url": None,
                "owner_email": None,
                "interviewer_email": None,
            }
            return

        logger.info("Retrieve OK | chunks=%d", len(retrieval_results))

        try:
            async for event in self._generator.generate_stream(query, retrieval_results):
                yield event
        except RuntimeError as exc:
            logger.error("Streaming generation failed: %s", exc)
            yield {
                "type": "error",
                "message": "I encountered an error while generating the answer. Please try again.",
            }
            return

        sources = [
            {
                "source": r.chunk.source,
                "content": r.chunk.text,
                "score": r.score,
            }
            for r in retrieval_results
        ]

        yield {
            "type": "done",
            "sources": sources,
            "booking_url": None,
            "meeting_url": None,
            "owner_email": None,
            "interviewer_email": None,
        }

    @staticmethod
    def _calendar_booking_answer(query: str) -> dict | None:
        """Return a booking CTA for calendar-related queries.

        The actual availability and confirmation are handled by the
        configured Google Calendar booking page.
        """
        normalized = query.strip().lower()
        if not normalized:
            return None

        booking_keywords = [
            "book",
            "booking",
            "schedule",
            "slot",
            "meeting",
            "call",
            "appointment",
            "calendar",
            "google calendar",
        ]

        if not any(keyword in normalized for keyword in booking_keywords):
            return None

        settings = get_settings()
        booking_url = settings.google_calendar_booking_url

        if not booking_url:
            return {
                "answer": (
                    "I can book a slot through Google Calendar, but the booking link is not configured yet. "
                    "Please set GOOGLE_CALENDAR_URL in backend/.env."
                ),
                "sources": [],
                "booking_url": None,
                "meeting_url": None,
                "owner_email": None,
                "interviewer_email": None,
            }

        interviewer_email = settings.interviewer_contact_email or None
        meeting_url = settings.google_meet_booking_url or None
        owner_email = settings.owner_contact_email or None

        return {
            "answer": (
                "You can book a slot using my Google Calendar link below. After booking, fill the invite details and share the Meet link with both people."
            ),
            "sources": [],
            "booking_url": booking_url,
            "meeting_url": meeting_url,
            "owner_email": owner_email,
            "interviewer_email": interviewer_email,
        }

    @staticmethod
    def _generic_persona_answer(query: str) -> str | None:
        """Return a direct answer for simple persona questions.

        This is a limited fallback for questions such as "what is your name"
        or "who are you" that should not depend on RAG retrieval.
        """
        normalized = query.strip().lower()
        if not normalized:
            return None

        simple_answers = {
            "what is your name": "I am Shubham's AI assistant.",
            "who are you": "I am Shubham's AI assistant.",
            "what's your name": "I am Shubham's AI assistant.",
            "what are you called": "I am Shubham's AI assistant.",
            "your name": "I am Shubham's AI assistant.",
            "who is this": "I am Shubham's AI assistant.",
            "what is your role": "I represent Shubham as his AI assistant.",
            "what do you do": "I help answer questions about Shubham's projects, experience, and skills.",
            "tell me about yourself": (
                "I am Shubham Shukla, a B.Tech Information Technology student at USICT, GGSIPU. "
                "I am based in Delhi, India, and I focus on Full Stack Development, Artificial Intelligence, "
                "Generative AI, Mobile Application Development, Backend Systems, and Computer Vision."
            ),
            "introduce yourself": (
                "I am Shubham Shukla, a B.Tech Information Technology student at USICT, GGSIPU. "
                "I am based in Delhi, India, and I focus on Full Stack Development, Artificial Intelligence, "
                "Generative AI, Mobile Application Development, Backend Systems, and Computer Vision."
            ),
            "what are your strengths": (
                "My strengths are building production-ready applications, working across frontend and backend, and learning new technologies quickly."
            ),
            "what are your weaknesses": (
                "I sometimes spend extra time refining solutions so they are reliable and well-structured, and I am working on balancing speed with perfection."
            ),
            "tell me about your hobbies": (
                "I enjoy exploring new technologies, building projects, and learning more about AI and product development."
            ),
            "tell me about your projects": (
                "I have worked on projects like NavDrishti, TeraAvison, and visitor-related systems, focusing on AI, full-stack development, and practical product building."
            ),
            "why should i hire you": (
                "I bring strong interest in Full Stack Development and AI, hands-on project experience, and a willingness to learn quickly and contribute to real products."
            ),
            "which role am i targeting": (
                "I am targeting Full Stack Developer roles primarily, with interest in AI Engineer, Backend Developer, and AI-powered Product Developer roles."
            ),
            "what role am i targeting": (
                "I am targeting Full Stack Developer roles primarily, with interest in AI Engineer, Backend Developer, and AI-powered Product Developer roles."
            ),
            "what kind of roles am i targeting": (
                "I am targeting Full Stack Developer roles primarily, with interest in AI Engineer, Backend Developer, and AI-powered Product Developer roles."
            ),
        }

        # Allow simple variations with punctuation.
        normalized = normalized.rstrip("?!. ")
        if answer := simple_answers.get(normalized):
            return answer

        # Broaden matching for conversational variants like
        # "what is your name ka answer", "aapka naam kya hai", etc.
        if "name" in normalized and any(
            token in normalized for token in [
                "your",
                "aap",
                "tum",
                "apka",
                "apki",
                "naam",
                "what",
                "kya",
            ]
        ):
            return "I am Shubham's AI assistant."

        if any(token in normalized for token in ["who are you", "who you", "who is this", "aap kaun", "tum kaun"]):
            return "I am Shubham's AI assistant."

        if any(token in normalized for token in ["what do you do", "your role", "aap kya karte", "tum kya karte"]):
            return "I help answer questions about Shubham's projects, experience, and skills."

        if any(
            phrase in normalized
            for phrase in [
                "what are you thinking to do in future",
                "what are you planning to do in future",
                "future plans",
                "what is your future plan",
                "what are your goals",
            ]
        ):
            return (
                "In the future, I want to keep building strong AI and full-stack products, improve my skills in "
                "AI Engineering, RAG systems, and Computer Vision, and work on practical applications that solve real problems."
            )

        if any(token in normalized for token in ["strength", "strong point", "best at"]):
            return "My strengths are building production-ready applications, working across frontend and backend, and learning new technologies quickly."

        if any(token in normalized for token in ["weakness", "improve on", "area to improve"]):
            return "I sometimes spend extra time refining solutions so they are reliable and well-structured, and I am working on balancing speed with perfection."

        if any(token in normalized for token in ["hobby", "hobbies", "interest outside work"]):
            return "I enjoy exploring new technologies, building projects, and learning more about AI and product development."

        if any(token in normalized for token in ["project", "projects", "work on"]):
            return "I have worked on projects like NavDrishti, TeraAvison, and visitor-related systems, focusing on AI, full-stack development, and practical product building."

        if any(token in normalized for token in ["hire you", "internship", "intern", "join your team"]):
            return "I bring strong interest in Full Stack Development and AI, hands-on project experience, and a willingness to learn quickly and contribute to real products."

        if any(token in normalized for token in ["targeting", "target role", "role am i targeting", "which role"]):
            return "I am targeting Full Stack Developer roles primarily, with interest in AI Engineer, Backend Developer, and AI-powered Product Developer roles."

        return None
