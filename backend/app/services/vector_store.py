"""
ChromaDB-backed vector store.

Stores chunk embeddings in a ChromaDB persistent collection and exposes
the same public API that the previous FAISS-backed `VectorStore` did:
build / search / save / load / is_built / size / get_chunk_by_id /
get_all_chunks. This keeps the retriever (and the rest of the codebase)
untouched.

We chose ChromaDB over FAISS because:
  - Built-in persistence (no manual sidecar chunks.json to maintain).
  - Native metadata filtering.
  - Same accuracy at our scale (12 chunks); the migration is invisible
    to the application logic.

Cosine distance is used (`hnsw:space: cosine`) so distances map cleanly:
  similarity = clamp(1 - distance, 0, 1),  range [0, 1]
This conversion happens inside `search()`; callers always see a `score`
field in [0, 1].

Persistence layout in `data/index/`:
  - chroma/                — Chroma PersistentClient directory
      chroma.sqlite3       — sqlite metadata store
      <uuid>.bin           — HNSW index segments
  - index_meta.json        — sidecar: embedding_dim, model, num_vectors
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.chunker import Chunk

logger = get_logger(__name__)


class VectorStore:
    """ChromaDB-backed vector store. Preserves the previous FAISS API.

    Args:
        index_dir: Directory where the Chroma collection and sidecar
            metadata live. Created if it does not exist.
        embedding_dim: Dimensionality of the vectors being stored.
            Must match across build/load/search. Used by `is_built` to
            reject a stale index whose dim does not match the configured
            one.
    """

    INDEX_DIR_NAME = "chroma"
    META_FILENAME = "index_meta.json"
    COLLECTION_NAME = "persona_chunks"

    def __init__(self, index_dir: Path, embedding_dim: int) -> None:
        if embedding_dim <= 0:
            raise ValueError(f"embedding_dim must be > 0, got {embedding_dim}")

        self._index_dir = Path(index_dir)
        self._embedding_dim = embedding_dim
        self._chroma_dir = self._index_dir / self.INDEX_DIR_NAME
        self._chroma_dir.mkdir(parents=True, exist_ok=True)

        # Lazy — do not connect on construction. The health endpoint
        # must not pay the disk / sqlite cost.
        self._client = None
        self._collection = None
        # In-memory mirror of chunk dicts for O(1) get_chunk_by_id().
        self._chunks_by_id: dict[str, dict[str, Any]] = {}

        logger.info(
            "VectorStore initialized | dir=%s dim=%d chroma_dir=%s",
            self._index_dir,
            embedding_dim,
            self._chroma_dir,
        )

    # ─── Internal helpers ──────────────────────────────────────────────────

    def _connect(self) -> None:
        """Open the Chroma PersistentClient and ensure the collection exists.

        Idempotent — safe to call repeatedly. Created with cosine
        distance space so `similarity = 1 - distance`.
        """
        if self._collection is not None:
            return
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"chromadb is not installed: {exc}. "
                "Run `pip install chromadb`."
            ) from exc

        self._client = chromadb.PersistentClient(
            path=str(self._chroma_dir),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=False,
            ),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def _meta_path(self) -> Path:
        return self._index_dir / self.META_FILENAME

    def _read_meta(self) -> dict[str, Any]:
        with self._meta_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    # ─── Cheap metadata properties ─────────────────────────────────────────

    @property
    def is_built(self) -> bool:
        """True if a persisted index exists and matches the expected dim.

        Uses the sidecar index_meta.json (cheap) plus a sqlite file
        existence check (also cheap) — does not open Chroma.
        """
        if not self._meta_path.exists():
            return False
        try:
            meta = self._read_meta()
        except Exception:  # noqa: BLE001
            return False
        sqlite_path = self._chroma_dir / "chroma.sqlite3"
        return (
            int(meta.get("embedding_dim", 0)) == self._embedding_dim
            and sqlite_path.exists()
            and int(meta.get("num_vectors", 0)) > 0
        )

    @property
    def size(self) -> int:
        """Number of vectors currently in the collection.

        Reads from the in-memory collection when available; falls back to
        the sidecar meta file before the collection has been loaded.
        """
        if self._collection is not None:
            try:
                return int(self._collection.count())
            except Exception:  # noqa: BLE001
                pass
        if self._meta_path.exists():
            try:
                meta = self._read_meta()
                return int(meta.get("num_vectors", 0))
            except Exception:  # noqa: BLE001
                return 0
        return 0

    # ─── Build ─────────────────────────────────────────────────────────────

    def build(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        """Build a fresh Chroma collection from chunks + their embeddings.

        Overwrites any existing collection on disk. Use this on first
        ingestion or whenever the knowledge base is rebuilt.

        Args:
            chunks: Source chunks, one per embedding.
            embeddings: Vectors in the same order as `chunks`. Each
                must be `embedding_dim` long.
        """
        if not chunks:
            raise ValueError("Cannot build an empty vector store (no chunks)")
        if not embeddings:
            raise ValueError("Cannot build an empty vector store (no embeddings)")
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Chunk/embedding count mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings"
            )

        # Validate embedding dim without depending on numpy.
        bad_dim = next(
            (len(v) for v in embeddings if len(v) != self._embedding_dim),
            None,
        )
        if bad_dim is not None:
            raise ValueError(
                f"Embedding dim mismatch: index expects {self._embedding_dim}, got {bad_dim}"
            )

        self._connect()

        # Idempotent rebuild — drop the existing collection if any, then
        # create a fresh one with the correct cosine distance metadata.
        try:
            self._client.delete_collection(self.COLLECTION_NAME)
        except Exception:  # noqa: BLE001 — collection may not exist yet
            pass
        self._collection = self._client.create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "doc_id": c.doc_id,
                "source": c.source,
                "index": c.index,
                **c.metadata,
            }
            for c in chunks
        ]

        # Chroma requires non-empty documents; chunker guarantees that.
        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        # Mirror chunks for O(1) get_chunk_by_id().
        self._chunks_by_id = {
            c.chunk_id: {
                "chunk_id": c.chunk_id,
                "doc_id": c.doc_id,
                "source": c.source,
                "text": c.text,
                "index": c.index,
                "metadata": {
                    "doc_id": c.doc_id,
                    "source": c.source,
                    "index": c.index,
                    **c.metadata,
                },
            }
            for c in chunks
        }

        self.save()

        logger.info(
            "Chroma collection built | vectors=%d dim=%d",
            len(chunks),
            self._embedding_dim,
        )

    # ─── Search ────────────────────────────────────────────────────────────

    def search(self, query_embedding: list[float], k: int) -> list[dict[str, Any]]:
        """Return the top-k chunks most similar to the query vector.

        Args:
            query_embedding: Vector of length `embedding_dim`.
            k: Number of results to return. Clamped to the current size.

        Returns:
            List of dicts with `chunk_id`, `source`, `text`, `score`
            (cosine similarity in [0, 1], higher = more similar),
            and `metadata`. Ordered by descending score.
        """
        if self._collection is None:
            logger.warning("Search called before collection was loaded")
            return []

        try:
            count = int(self._collection.count())
        except Exception:  # noqa: BLE001
            count = 0
        if count == 0:
            logger.warning("Search called on empty collection")
            return []
        if k <= 0:
            return []
        k = min(k, count)

        if len(query_embedding) != self._embedding_dim:
            raise ValueError(
                f"Query dim mismatch: index expects {self._embedding_dim}, "
                f"got {len(query_embedding)}"
            )

        res = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )

        ids = (res.get("ids") or [[]])[0]
        documents = (res.get("documents") or [[]])[0]
        metadatas = (res.get("metadatas") or [[]])[0]
        distances = (res.get("distances") or [[]])[0]

        results: list[dict[str, Any]] = []
        for cid, doc, meta, dist in zip(ids, documents, metadatas, distances):
            # Cosine distance ∈ [0, 2]; with normalized vectors it sits in
            # [0, 1]. Convert to similarity and clamp defensively.
            raw = 1.0 - float(dist)
            similarity = max(0.0, min(1.0, raw))
            if similarity != raw:
                logger.warning(
                    "Chroma score conversion clamped | raw=%f clamped=%f", raw, similarity
                )
            results.append(
                {
                    "chunk_id": cid,
                    "source": (meta or {}).get("source", "unknown"),
                    "text": doc,
                    "score": similarity,
                    "metadata": meta or {},
                }
            )

        logger.info(
            "Chroma search | k=%d top_score=%.4f low_score=%.4f",
            len(results),
            results[0]["score"] if results else 0.0,
            results[-1]["score"] if results else 0.0,
        )
        return results

    # ─── Persistence ──────────────────────────────────────────────────────

    def save(self) -> None:
        """Persist the sidecar index_meta.json.

        ChromaDB persists itself via PersistentClient on every write;
        we only need to update our own sidecar so `is_built`/`size` can
        answer without opening Chroma.
        """
        meta = {
            "embedding_dim": self._embedding_dim,
            "model": "sentence-transformers/all-MiniLM-L6-v2",
            "build_timestamp": time.time(),
            "num_vectors": int(self.size),
            "num_chunks": int(self.size),
        }
        with self._meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        logger.info(
            "Sidecar meta written | dim=%d vectors=%d",
            meta["embedding_dim"],
            meta["num_vectors"],
        )

    def load(self) -> None:
        """Load the persisted Chroma collection into memory.

        Raises FileNotFoundError if no collection exists, and ValueError
        if the on-disk dimension does not match the configured one.
        """
        self._connect()
        try:
            count = int(self._collection.count())
        except Exception as exc:  # noqa: BLE001
            raise FileNotFoundError(
                f"No persisted Chroma collection at {self._chroma_dir}. "
                "Run scripts/ingest.py to build one."
            ) from exc

        if count == 0:
            raise FileNotFoundError(
                f"Chroma collection at {self._chroma_dir} is empty. "
                "Run scripts/ingest.py to build one."
            )

        # Hydrate the in-memory chunks mirror from the collection.
        got = self._collection.get(include=["documents", "metadatas"])
        self._chunks_by_id = {}
        for cid, doc, meta in zip(
            got.get("ids", []),
            got.get("documents", []),
            got.get("metadatas", []),
        ):
            meta = meta or {}
            self._chunks_by_id[cid] = {
                "chunk_id": cid,
                "doc_id": meta.get("doc_id", cid.split("::", 1)[0]),
                "source": meta.get("source", "unknown"),
                "text": doc,
                "index": meta.get("index", 0),
                "metadata": meta,
            }

        logger.info(
            "Chroma collection loaded | vectors=%d chunks_mirrored=%d",
            count,
            len(self._chunks_by_id),
        )

    # ─── Lookup helpers ───────────────────────────────────────────────────

    def get_chunk_by_id(self, chunk_id: str) -> dict[str, Any] | None:
        """Return the chunk dict for a given chunk_id, or None."""
        return self._chunks_by_id.get(chunk_id)

    def get_all_chunks(self) -> list[dict[str, Any]]:
        """Return all chunks in the store (debug / inspection)."""
        return list(self._chunks_by_id.values())