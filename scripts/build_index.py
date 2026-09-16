from __future__ import annotations

from pathlib import Path
from typing import Iterator

import faiss
from rich.console import Console

from backend.config import settings
from backend.embedding.embedder import Embedder
from backend.models import CodeChunk

console = Console()

# How many chunks to embed + add to the index per batch.
# Memory usage per batch is roughly:
#   BATCH_SIZE * (avg_chunk_bytes + embedding_dim * 4)
# For BATCH_SIZE=5000 and ~2KB average chunk, that's ~15MB per batch. Plenty of headroom.
BATCH_SIZE = 5000


def count_lines(path: Path) -> int:
    """Cheap line count for the progress bar."""
    with path.open("rb") as f:
        return sum(1 for _ in f)


def iter_chunks(path: Path) -> Iterator[CodeChunk]:
    """Stream chunks from the JSONL file, one at a time."""
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield CodeChunk.model_validate_json(line)


def main() -> None:
    chunks_path = settings.data_dir / "chunks.jsonl"
    if not chunks_path.exists():
        console.log(f"[red]{chunks_path} not found. Run ingestion first.[/]")
        raise SystemExit(1)

    console.rule("[bold cyan]Building FAISS index (streaming)")
    console.log(f"counting chunks in {chunks_path}…")
    total = count_lines(chunks_path)
    console.log(f"total chunks: {total:,}")

    console.log(f"loading embedder ({settings.embedding_model})…")
    embedder = Embedder()

    # Create the FAISS index up front — we'll add batches into it as we go.
    console.log("initializing FAISS index…")
    index = faiss.IndexFlatIP(settings.embedding_dim)

    # Stream through chunks in batches. Also stream metadata to disk
    # so we never hold all 2M+ CodeChunks in memory at once.
    metadata_path = settings.data_dir / "metadata.jsonl"
    console.log(f"streaming embed + add + write metadata (batch size {BATCH_SIZE})…")

    processed = 0
    batch: list[CodeChunk] = []

    with metadata_path.open("w", encoding="utf-8") as meta_fh:
        for chunk in iter_chunks(chunks_path):
            batch.append(chunk)
            if len(batch) >= BATCH_SIZE:
                _process_batch(batch, embedder, index, meta_fh)
                processed += len(batch)
                console.log(f"  {processed:,} / {total:,} ({100*processed/total:.1f}%)")
                batch = []

        # Flush the final partial batch
        if batch:
            _process_batch(batch, embedder, index, meta_fh)
            processed += len(batch)
            console.log(f"  {processed:,} / {total:,} (100.0%)")

    console.log(f"index has {index.ntotal:,} vectors")

    index_path = settings.data_dir / "faiss.index"
    console.log(f"writing index to {index_path}…")
    faiss.write_index(index, str(index_path))

    console.log("[green]done.[/]")


def _process_batch(
    batch: list[CodeChunk],
    embedder: Embedder,
    index: faiss.Index,
    meta_fh,
) -> None:
    """Embed one batch, add to index, write metadata."""
    # Suppress the per-batch progress bar; we're logging our own progress.
    texts = [embedder.compose_text(c) for c in batch]
    vectors = embedder.model.encode(
        texts,
        batch_size=64,
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype("float32")

    index.add(vectors)
    for c in batch:
        meta_fh.write(c.model_dump_json() + "\n")


if __name__ == "__main__":
    main()