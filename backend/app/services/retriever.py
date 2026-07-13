"""
Retriever: embeds a query and fetches the top-k most relevant chunks.

This is a thin orchestration layer over `EmbeddingsClient` and
`VectorStore`. It exists to:

  1. Give the RAG pipeline a single high-level method
     (`retrieve(query) → list[Chunk]`) instead of two coupled calls.
  2. Apply query preprocessing consistently (trim, normalize whitespace).
  3. Enforce a minimum similarity threshold so irrelevant chunks do
     not pollute the generator's context window. Without this, FAISS
     happily returns chunks with cosine ~0.0 just because we asked
     for k=4 — even when nothing in the KB matches the question.
  4. Convert raw FAISS dicts back into `Chunk` dataclasses so the
     generator and API layer never see FAISS types.

Design notes:
  - This class is stateless beyond its dependencies. It is safe to
    instantiate once at app startup and reuse for every request.
  - We do not cache query embeddings here. Query volume is low and
    the cache key (sha256 of text) costs more than the API call it
    would save at <100 QPS.
  - The score threshold is configurable so we can tune precision/
    recall without code changes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.logging import get_logger
from app.services.chunker import Chunk
from app.services.embeddings import EmbeddingsClient
from app.services.vector_store import VectorStore

logger = get_logger(__name__)


@dataclass
class RetrievalResult:
    """A retrieved chunk plus its similarity score.

    The score is the cosine similarity between the query and the
    chunk embedding, in the range [-1, 1]. In practice values are
    typically 0.4-0.8 for relevant matches and 0.1-0.4 for noise.
    """

    chunk: Chunk
    score: float

    @property
    def is_relevant(self) -> bool:
        """Heuristic: scores above this are treated as real matches.

        The exact threshold is a tunable knob. 0.5 is a sensible
        default for Gemini embeddings on English text.
        """
        return self.score >= 0.5


class Retriever:
    """Top-k chunk retriever over a FAISS vector store.

    Args:
        vector_store: An initialized (and ideally loaded) VectorStore.
        embeddings_client: Gemini embeddings client.
        top_k: Maximum chunks to return per query.
        min_score: Drop chunks whose cosine similarity is below this.
            Set to 0.0 to disable filtering (return everything FAISS
            found).
    """

    # Minimum sane query length after trimming — shorter queries almost
    # always produce noisy retrievals and are usually typos.
    MIN_QUERY_LENGTH = 2

    def __init__(
        self,
        vector_store: VectorStore,
        embeddings_client: EmbeddingsClient,
        top_k: int = 4,
        min_score: float = 0.5,
    ) -> None:
        if top_k <= 0:
            raise ValueError(f"top_k must be > 0, got {top_k}")
        if not (0.0 <= min_score <= 1.0):
            raise ValueError(f"min_score must be in [0.0, 1.0], got {min_score}")

        self._vector_store = vector_store
        self._embeddings = embeddings_client
        self._top_k = top_k
        self._min_score = min_score

        logger.info(
            "Retriever initialized | top_k=%d min_score=%.2f",
            top_k,
            min_score,
        )

    # ─── Query preprocessing ─────────────────────────────────────────────

    @staticmethod
    def _normalize_query(query: str) -> str:
        """Trim whitespace and collapse internal whitespace runs.

        This is intentionally light. Aggressive normalization
        (lowercasing, stemming, stopword removal) hurts retrieval
        quality because the chunker preserves original casing and
        technical terms — we want to match those exactly.
        """
        if not query:
            return ""
        # Collapse runs of whitespace (including newlines) to a single space
        normalized = re.sub(r"\s+", " ", query).strip()
        return normalized

    def _validate_query(self, query: str) -> str:
        normalized = self._normalize_query(query)
        if len(normalized) < self.MIN_QUERY_LENGTH:
            raise ValueError(
                f"Query too short: {len(normalized)} chars (min {self.MIN_QUERY_LENGTH})."
            )
        return normalized

    # ─── Public API ──────────────────────────────────────────────────────

    def retrieve(self, query: str) -> list[RetrievalResult]:
        """Embed the query and return the top-k relevant chunks.

        Args:
            query: Natural-language question from the user.

        Returns:
            List of `RetrievalResult` ordered by descending score.
            Empty list if the vector store is empty or no chunk meets
            the minimum similarity threshold.

        Raises:
            ValueError: If the query is too short or empty.
            RuntimeError: If the vector store has not been built/loaded.
        """
        normalized = self._validate_query(query)

        if self._vector_store.size == 0:
            logger.warning("Retrieve called on empty vector store")
            return []

        # 1. Embed the query
        query_embedding = self._embeddings.embed_query(normalized)

        # 2. Search FAISS for top-k candidates (over-fetch slightly so
        #    we have headroom for the score filter — important when
        #    top_k is small and many low-score chunks would otherwise
        #    crowd out good matches).
        fetch_k = min(self._top_k * 2, max(self._top_k, self._vector_store.size))
        raw_results = self._vector_store.search(query_embedding, k=fetch_k)

        # 3. Filter by minimum score, then trim to top_k
        filtered = [r for r in raw_results if r["score"] >= self._min_score]
        filtered.sort(key=lambda r: r["score"], reverse=True)
        top = filtered[: self._top_k]

        # 4. Reconstruct Chunk objects so callers see our domain type
        results: list[RetrievalResult] = []
        for r in top:
            chunk = Chunk(
                chunk_id=r["chunk_id"],
                doc_id=r["metadata"].get("doc_id") or self._doc_id_from_chunk_id(r["chunk_id"]),
                source=r["source"],
                text=r["text"],
                index=r["metadata"].get("index", 0),
                metadata=r["metadata"],
            )
            results.append(RetrievalResult(chunk=chunk, score=r["score"]))

        logger.info(
            "Retrieve | query_len=%d fetched=%d filtered=%d returned=%d top_score=%.4f",
            len(normalized),
            len(raw_results),
            len(filtered),
            len(results),
            results[0].score if results else 0.0,
        )
        return results

    # ─── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _doc_id_from_chunk_id(chunk_id: str) -> str:
        """Fallback when chunk metadata is missing the doc_id field.

        Chunk ids are formatted as `<doc_id>::<index>`. Splitting on
        '::' recovers the doc_id when metadata has been lost.
        """
        return chunk_id.split("::", 1)[0] if "::" in chunk_id else chunk_id

    # ─── Convenience properties ─────────────────────────────────────────

    @property
    def top_k(self) -> int:
        return self._top_k

    @property
    def min_score(self) -> float:
        return self._min_score
