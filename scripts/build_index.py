from __future__ import annotations

from pathlib import Path

from rich.console import Console

from backend.config import settings
from backend.embedding.embedder import Embedder
from backend.index.faiss_index import FaissIndex
from backend.models import CodeChunk

console = Console()


def load_chunks(path: Path) -> list[CodeChunk]:
    chunks: list[CodeChunk] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            chunks.append(CodeChunk.model_validate_json(line))
    return chunks


def main() -> None:
    chunks_path = settings.data_dir / "chunks.jsonl"
    if not chunks_path.exists():
        console.log(f"[red]{chunks_path} not found. Run ingestion first.[/]")
        raise SystemExit(1)

    console.rule("[bold cyan]Building FAISS index")
    console.log(f"loading chunks from {chunks_path}…")
    chunks = load_chunks(chunks_path)
    console.log(f"loaded {len(chunks):,} chunks")

    console.log(f"loading embedder ({settings.embedding_model})…")
    embedder = Embedder()

    console.log("encoding chunks (this is the slow part)…")
    vectors = embedder.encode_chunks(chunks)
    console.log(f"embeddings shape: {vectors.shape}")

    console.log("building FAISS index…")
    index = FaissIndex(dim=vectors.shape[1])
    index.build(vectors, chunks)

    console.log(f"saving to {settings.data_dir}…")
    index.save()
    console.log("[green]done.[/]")


if __name__ == "__main__":
    main()
