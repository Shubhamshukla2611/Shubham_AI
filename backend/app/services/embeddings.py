"""
Local embeddings via sentence-transformers (MiniLM).

Uses the local `sentence-transformers` library to embed chunks of text
into fixed-dimensional vectors (default: 384-dim, normalized for cosine
similarity). These vectors power the ChromaDB similarity search in the
retriever.

Key design choices:
  - **Local inference** — no API key, no rate limits, no internet at query
    time. The model is downloaded once to the HuggingFace cache
    (~/.cache/huggingface/) on first use.
  - **Lazy model load** — model is loaded on first embed call. The ingest
    script calls `warmup()` to amortize this cost upfront.
  - **Batched calls** — sentence-transformers handles batched encoding
    internally; we cap at DEFAULT_BATCH_SIZE for predictable memory.
  - **Normalized outputs** — `normalize_embeddings=True` so vectors are
    unit-length and inner product == cosine similarity.
  - **Caching** — SHA-256 keyed in-memory cache so identical text within
    a process is not re-embedded.
  - **No retries needed** — local CPU inference is reliable. We keep the
    same public API as the previous Gemini-backed client so callers do
    not change.
"""

from __future__ import annotations

import hashlib

from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingsClient:
    """Wrapper around sentence-transformers for local embedding inference.

    Args:
        model: HuggingFace model identifier. Defaults to
            `sentence-transformers/all-MiniLM-L6-v2` (384-dim, fast,
            strong for English).
        dim: Output vector dimensionality. Must match the model's
            actual output; defaults to 384.
        cache: Optional pre-populated cache of {text_hash: vector}.
            Pass an existing cache to avoid re-embedding identical text
            across runs.
    """

    # Default batch size — sentence-transformers handles larger lists
    # but we cap to keep memory predictable on CPU.
    DEFAULT_BATCH_SIZE = 32

    # The MiniLM-L6-v2 model produces 384-dim normalized vectors.
    DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    DEFAULT_DIM = 384

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        dim: int = DEFAULT_DIM,
        cache: dict[str, list[float]] | None = None,
    ) -> None:
        if dim <= 0:
            raise ValueError(f"dim must be > 0, got {dim}")

        self._model_name = model
        self._dim = dim
        self._cache: dict[str, list[float]] = cache if cache is not None else {}
        self._model = None  # lazy — load on first embed

        logger.info(
            "EmbeddingsClient initialized | model=%s dim=%d cache_size=%d",
            model,
            dim,
            len(self._cache),
        )

    @property
    def embedding_dim(self) -> int:
        """Dimensionality of vectors produced by the configured model.

        Unlike the previous Gemini-backed client, we do not probe the
        model at runtime — the dim is configured in __init__. This is
        safe because the model is fixed at construction time.
        """
        return self._dim

    # ─── Model lifecycle ──────────────────────────────────────────────────

    def _ensure_model(self):
        """Lazy-load the sentence-transformers model on first use.

        The first call downloads the model weights (~80 MB for MiniLM)
        to the HuggingFace cache directory. Subsequent loads use the
        cached weights.
        """
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(
                    f"sentence-transformers is not installed: {exc}. "
                    "Run `pip install sentence-transformers`."
                ) from exc
            logger.info("Loading sentence-transformers model | model=%s", self._model_name)
            self._model = SentenceTransformer(self._model_name)
            logger.info("Model loaded | model=%s dim=%d", self._model_name, self._dim)
        return self._model

    def warmup(self) -> None:
        """Eagerly load the model and run a probe embed.

        Call from ingestion scripts so the server's first chat request
        does not pay the ~2-3 second cold-start cost.
        """
        self._ensure_model()
        self._embed_uncached(["warmup probe"])
        logger.info("EmbeddingsClient warmup complete | model=%s", self._model_name)

    # ─── Caching ───────────────────────────────────────────────────────────

    @staticmethod
    def _hash_text(text: str) -> str:
        """Stable cache key for a text string."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    # ─── Core embedding ───────────────────────────────────────────────────

    def _embed_uncached(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts that are not in the cache.

        Returns a list of plain float lists (JSON-serializable).
        """
        if not texts:
            return []

        model = self._ensure_model()
        # sentence-transformers handles batching internally; we pass
        # batch_size to control memory. normalize_embeddings=True makes
        # inner product == cosine similarity, which is what Chroma's
        # cosine distance expects.
        vectors = model.encode(
            texts,
            batch_size=self.DEFAULT_BATCH_SIZE,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [v.astype(float).tolist() for v in vectors]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Cached results are reused.

        The cache is keyed on a SHA-256 hash of the text, so identical
        chunks across documents share a single embedding call.

        Args:
            texts: List of strings to embed. May be empty.

        Returns:
            List of float vectors in the same order as `texts`. Each
            vector has length `self.embedding_dim`.
        """
        if not texts:
            return []

        # Split into cached vs uncached.
        results: list[list[float] | None] = [None] * len(texts)
        uncached_texts: list[str] = []
        uncached_indices: list[int] = []

        for i, text in enumerate(texts):
            key = self._hash_text(text)
            if key in self._cache:
                results[i] = self._cache[key]
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        if uncached_texts:
            logger.info(
                "Embedding batch | total=%d cached=%d to_embed=%d",
                len(texts),
                len(texts) - len(uncached_texts),
                len(uncached_texts),
            )
            # sentence-transformers handles internal batching, but we
            # still sub-batch here to keep log granularity useful.
            for start in range(0, len(uncached_texts), self.DEFAULT_BATCH_SIZE):
                batch = uncached_texts[start : start + self.DEFAULT_BATCH_SIZE]
                vectors = self._embed_uncached(batch)
                for j, vec in enumerate(vectors):
                    global_idx = uncached_indices[start + j]
                    results[global_idx] = vec
                    self._cache[self._hash_text(batch[j])] = vec

        # Type narrowing: every slot is populated by the time we get here.
        out: list[list[float]] = [v for v in results if v is not None]  # type: ignore[misc]
        if len(out) != len(texts):
            raise RuntimeError(
                f"embed_texts internal error: expected {len(texts)} vectors, got {len(out)}"
            )
        return out

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        return self.embed_texts([query])[0]

    @property
    def cache(self) -> dict[str, list[float]]:
        """Public read-only view of the embedding cache (for persistence)."""
        return dict(self._cache)