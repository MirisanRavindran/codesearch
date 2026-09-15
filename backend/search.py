from __future__ import annotations

import time

from backend.embedding.embedder import Embedder
from backend.index.faiss_index import FaissIndex
from backend.models import SearchHit, SearchResponse


class SearchService:
    def __init__(self):
        self.embedder = Embedder()
        self.index = FaissIndex()
        self.index.load()

    def search(self, query: str, top_k: int) -> SearchResponse:
        t0 = time.perf_counter()
        q_vec = self.embedder.encode_query(query)
        raw = self.index.search(q_vec, top_k)
        latency_ms = (time.perf_counter() - t0) * 1000

        return SearchResponse(
            query=query,
            hits=[SearchHit(chunk=chunk, score=score) for chunk, score in raw],
            latency_ms=round(latency_ms, 2),
        )
