from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from backend.config import settings
from backend.models import CodeChunk


class Embedder:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embedding_model
        # Loads from HuggingFace cache; first call downloads (~80MB for MiniLM).
        self.model = SentenceTransformer(self.model_name)

    def compose_text(self, chunk: CodeChunk) -> str:
        """Turn a chunk into the string we actually embed."""
        parts = [f"{chunk.kind} {chunk.name}"]
        if chunk.docstring:
            parts.append(chunk.docstring)
        parts.append(chunk.source)
        return "\n".join(parts)

    def encode_chunks(self, chunks: list[CodeChunk], batch_size: int = 64) -> np.ndarray:
        """
        Embed a batch of chunks. Returns (N, embedding_dim) float32 array.

        Batching matters: sentence-transformers is much faster with batching,
        because most GPU work is matmul overhead per batch.
        """
        texts = [self.compose_text(c) for c in chunks]
        emb = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            normalize_embeddings=True,  # unit vectors → inner product = cosine
            convert_to_numpy=True,
        )
        # sentence-transformers returns float32 by default, but be defensive
        return emb.astype(np.float32)

    def encode_query(self, query: str) -> np.ndarray:
        """Embed a single search query. Returns (embedding_dim,) float32."""
        emb = self.model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return emb[0].astype(np.float32)
