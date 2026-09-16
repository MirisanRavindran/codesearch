"""
Main ingestion entrypoint.

Pipeline: search top repos → download tarball → chunk each .py file
         → append chunks to chunks.jsonl.

We write JSONL (one JSON object per line) because:
- Streamable: don't need to hold all chunks in memory
- Append-only: can resume if the process crashes
- Trivial to inspect (just `head` or `grep`)

Run with:
    python -m backend.ingestion.ingest

Environment vars respected (see backend/config.py):
    GITHUB_TOKEN, NUM_REPOS_TO_INGEST, DATA_DIR
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from rich.console import Console
from tqdm import tqdm

from backend.config import settings
from backend.ingestion.chunker import chunk_python_file
from backend.ingestion.github_client import (
    RepoInfo,
    download_repo_tarball,
    iter_python_files_from_tarball,
    list_top_python_repos,
)

console = Console()


async def ingest_one_repo(
    repo: RepoInfo,
    client: httpx.AsyncClient,
    out_fh,
) -> int:
    """Ingest a single repo, appending chunks to `out_fh`. Returns chunk count."""
    try:
        tarball = await download_repo_tarball(repo, client)
    except Exception as e:
        console.log(f"[yellow]skip {repo.full_name}: download failed ({e})[/]")
        return 0

    count = 0
    for file_path, source in iter_python_files_from_tarball(tarball):
        for chunk in chunk_python_file(
            repo=repo.full_name,
            default_branch=repo.default_branch,
            file_path=file_path,
            source=source,
        ):
            # model_dump_json is Pydantic v2's serializer
            out_fh.write(chunk.model_dump_json() + "\n")
            count += 1

    return count


async def main() -> None:
    out_path: Path = settings.data_dir / "chunks.jsonl"
    console.rule("[bold cyan]CodeSearch ingest")
    console.log(f"target: {settings.num_repos_to_ingest} repos → {out_path}")
    if not settings.github_token:
        console.log(
            "[yellow]No GITHUB_TOKEN set — you'll hit rate limits fast.[/]\n"
            "[yellow]Generate one at https://github.com/settings/tokens (no scopes needed)[/]"
        )

    async with httpx.AsyncClient() as client:
        console.log("Listing top repos…")
        repos = await list_top_python_repos(settings.num_repos_to_ingest, client)
        console.log(f"Got {len(repos)} repos. Ingesting…")

        total_chunks = 0
        # Fresh file each run so we don't mix old/new. If you want incremental,
        # switch to append mode and dedupe by chunk_id at index time.
        with out_path.open("w", encoding="utf-8") as fh:
            for repo in tqdm(repos, desc="repos"):
                n = await ingest_one_repo(repo, client, fh)
                total_chunks += n

    console.log(f"[green]Done. {total_chunks:,} chunks written to {out_path}[/]")


if __name__ == "__main__":
    asyncio.run(main())
