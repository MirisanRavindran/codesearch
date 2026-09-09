from pydantic import BaseModel, Field


class CodeChunk(BaseModel):
    """A single extracted function or class from a source file."""

    # Stable identifier: repo + file path + name + start line.
    chunk_id: str

    # Where it came from
    repo: str  # e.g. "psf/requests"
    file_path: str  # relative to repo root, e.g. "src/requests/api.py"
    start_line: int
    end_line: int

    # What it is
    kind: str  # "function" | "class" | "method"
    name: str  # e.g. "get" or "Session.request"

    # Content
    docstring: str | None = None  # first docstring if present
    source: str  # full source text of the chunk (bounded by max_file_size_bytes)

    # URL back to GitHub — computed on ingest so the API is dumb.
    github_url: str  # e.g. "https://github.com/psf/requests/blob/main/src/requests/api.py#L14-L64"


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=50)


class SearchHit(BaseModel):
    """One result. Score is the raw FAISS similarity (inner product on normalized vectors)."""

    chunk: CodeChunk
    score: float  # higher = more similar; in [0, 1] for our normalized embeddings


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]
    latency_ms: float  
