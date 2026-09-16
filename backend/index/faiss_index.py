"""
FAISS index wrapper.

We start with IndexFlatIP — exact brute-force inner-product search.
- Pros: exact results, no training, easy to reason about
- Cons: O(N * D) per query; at 300K chunks × 384 dims that's ~115M multiplies,
  which is ~30-50ms on a modern CPU. Fine for MVP.

If you scale past ~1M chunks or need sub-10ms latency, switch to
IndexIVFPQ or IndexHNSW. Interview-relevant question:
"Why would you switch from Flat to IVF?" Answer: sublinear search,
but you trade some recall.

Alongside the FAISS binary, we persist a parallel `metadata.json` list —
FAISS only knows integer row ids, so we need a way to map back to CodeChunks.
"""

from __future__ import annotations

from pathlib import Path

import faiss
import numpy as np

from backend.config import settings
from backend.models import CodeChunk


class FaissIndex:
    """Simple flat inner-product index + parallel metadata list."""

    INDEX_FILENAME = "faiss.index"
    METADATA_FILENAME = "metadata.jsonl"

    def __init__(self, dim: int | None = None):
        self.dim = dim or settings.embedding_dim
        self.index: faiss.Index | None = None
        # metadata[i] gives the CodeChunk for FAISS row i.
        self.metadata: list[CodeChunk] = []

    # ---- Build / persist ----

    def build(self, vectors: np.ndarray, chunks: list[CodeChunk]) -> None:
        """Build a fresh index from vectors and their parallel chunk list."""
        assert vectors.shape[0] == len(chunks), (
            f"vector count {vectors.shape[0]} != chunk count {len(chunks)}"
        )
        assert vectors.shape[1] == self.dim, (
            f"vector dim {vectors.shape[1]} != expected {self.dim}"
        )
        self.index = faiss.IndexFlatIP(self.dim)
        self.index.add(vectors)
        self.metadata = list(chunks)

    def save(self, dir: Path | None = None) -> None:
        d = dir or settings.data_dir
        d.mkdir(parents=True, exist_ok=True)
        assert self.index is not None, "index not built"
        faiss.write_index(self.index, str(d / self.INDEX_FILENAME))
        # JSONL is streamable and easier to inspect than a big JSON array.
        with (d / self.METADATA_FILENAME).open("w", encoding="utf-8") as fh:
            for chunk in self.metadata:
                fh.write(chunk.model_dump_json() + "\n")

    def load(self, dir: Path | None = None) -> None:
        d = dir or settings.data_dir
        self.index = faiss.read_index(str(d / self.INDEX_FILENAME))
        self.metadata = []
        with (d / self.METADATA_FILENAME).open("r", encoding="utf-8") as fh:
            for line in fh:
                self.metadata.append(CodeChunk.model_validate_json(line))
        # Sanity check
        assert self.index.ntotal == len(self.metadata), "index/metadata mismatch"
        self.dim = self.index.d

    # ---- Search ----

    def search(self, query_vec: np.ndarray, top_k: int) -> list[tuple[CodeChunk, float]]:
        """
        Return [(chunk, score), ...] sorted by score descending.

        Score is inner product on normalized vectors, i.e. cosine similarity in [-1, 1].
        """
        assert self.index is not None, "index not loaded"
        # FAISS expects a batch dimension even for a single query.
        q = query_vec.reshape(1, -1).astype(np.float32)
        scores, ids = self.index.search(q, top_k)

        results: list[tuple[CodeChunk, float]] = []
        for score, idx in zip(scores[0], ids[0]):
            # FAISS returns -1 for missing (shouldn't happen with Flat, but be safe)
            if idx < 0:
                continue
            results.append((self.metadata[idx], float(score)))
        return results
