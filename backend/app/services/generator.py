"""
Generator: builds the grounded prompt and calls Groq to produce
the final answer.

The generator receives a user query + retrieved context chunks, wraps them
in the system prompt, and calls Groq with low temperature (0.2) to ensure
faithful, grounded responses. Temperature is intentionally low to reduce
hallucination and encourage strict adherence to the system prompt.
"""

from __future__ import annotations

from typing import AsyncIterator

from groq import AsyncGroq, Groq
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

from app.core.logging import get_logger
from app.prompts.system_prompt import REFUSAL_PHRASE, SYSTEM_PROMPT

logger = get_logger(__name__)


class Generator:
    """Groq-powered answer generator with grounded prompt injection."""

    GENERATION_TEMPERATURE = 0.0
    GENERATION_MAX_TOKENS = 300

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("Groq API key is required for generator.")
        self._api_key = api_key.strip()
        self._model = model
        try:
            self._client = Groq(api_key=self._api_key)
            self._async_client = AsyncGroq(api_key=self._api_key)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialize Groq client: {exc}. "
                "Check your GROQ_API_KEY in backend/.env."
            ) from exc
        logger.info(
            "Generator initialized | model=%s temp=%.1f",
            model,
            self.GENERATION_TEMPERATURE,
        )

    def generate(self, query: str, context_chunks: list) -> str:
        """Generate a grounded answer from query and retrieved context.

        Args:
            query: The user's question.
            context_chunks: List of RetrievalResult objects with chunk + score.

        Returns:
            Generated answer grounded in the provided context. If no relevant
            chunks, returns the canonical refusal phrase.
        """
        if not context_chunks:
            logger.info("Generate called with empty context | returning refusal")
            return REFUSAL_PHRASE

        # Build context string from chunks
        context_text = self._format_context(context_chunks)

        # Build the full prompt: system + user message
        full_prompt = f"""{SYSTEM_PROMPT}

Query: {query}

<context>
{context_text}
</context>

Answer the query using ONLY the context above. If the answer is not in the context, respond with the refusal phrase."""

        logger.info(
            "Generate | model=%s query_len=%d context_chunks=%d",
            self._model,
            len(query),
            len(context_chunks),
        )

        # Groq's exception hierarchy is shallow; we retry on any
        # exception (rate-limit, network, transient 5xx). The retry
        # budget is the same as the previous Gemini wrapper.
        @retry(
            retry=retry_if_exception_type((Exception,)),
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=2, max=30) + wait_random(0, 1),
            reraise=True,
        )
        def _call() -> str:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": full_prompt}],
                temperature=self.GENERATION_TEMPERATURE,
                max_tokens=self.GENERATION_MAX_TOKENS,
            )
            content = (response.choices[0].message.content or "").strip()
            return content

        try:
            answer = _call()
            if not answer:
                logger.warning("Groq returned empty content | returning refusal")
                return REFUSAL_PHRASE
            logger.info("Generate OK | answer_len=%d", len(answer))
            return answer
        except Exception as exc:
            logger.error("Generate failed: %s", exc)
            raise RuntimeError(f"Failed to generate answer: {exc}") from exc

    async def generate_stream(self, query: str, context_chunks: list) -> AsyncIterator[dict]:
        """Stream generated tokens from Groq for the given query/context."""
        if not context_chunks:
            logger.info("Generate stream called with empty context | returning refusal")
            yield {"type": "delta", "text": REFUSAL_PHRASE}
            yield {"type": "done"}
            return

        context_text = self._format_context(context_chunks)
        full_prompt = f"""{SYSTEM_PROMPT}

Query: {query}

<context>
{context_text}
</context>

Answer the query using ONLY the context above. If the answer is not in the context, respond with the refusal phrase."""

        logger.info(
            "Generate stream | model=%s query_len=%d context_chunks=%d",
            self._model,
            len(query),
            len(context_chunks),
        )

        try:
            response_cm = self._async_client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": full_prompt}],
                temperature=self.GENERATION_TEMPERATURE,
                max_tokens=self.GENERATION_MAX_TOKENS,
                stream=True,
            )
            async with response_cm as response:
                async for chunk in response:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if not delta:
                        continue
                    if delta.content:
                        yield {"type": "delta", "text": delta.content}
        except Exception as exc:
            logger.error("Generate stream failed: %s", exc)
            raise RuntimeError(f"Failed to stream answer: {exc}") from exc

    @staticmethod
    def _format_context(chunks: list) -> str:
        """Format retrieved chunks into a readable context block.

        Each chunk includes source, text, and score so the model knows
        which document it came from and how confident the retrieval was.
        """
        if not chunks:
            return ""

        lines = []
        for i, result in enumerate(chunks, 1):
            chunk = result.chunk
            score = result.score
            lines.append(f"[Source {i}: {chunk.source} (score: {score:.2f})]")
            lines.append(chunk.text)
            lines.append("")

        return "\n".join(lines)