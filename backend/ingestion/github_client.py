"""
Minimal GitHub API client.

We only need two things:
1. List top-N Python repos by stars (search API).
2. Download the repo tarball (fastest way to get all files without cloning).

We use httpx (async) even though ingestion is a one-shot script,
because it's the same lib the FastAPI backend uses — one less dep.
"""

from __future__ import annotations

import io
import tarfile
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import settings


GITHUB_API = "https://api.github.com"


def _headers() -> dict[str, str]:
    """Build request headers. Auth is optional but strongly recommended
    (unauthenticated: 60 req/hr, authenticated: 5000 req/hr)."""
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if settings.github_token:
        h["Authorization"] = f"Bearer {settings.github_token}"
    return h


@dataclass(frozen=True)
class RepoInfo:
    full_name: str  # "owner/repo"
    default_branch: str
    stars: int
    tarball_url: str


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def list_top_python_repos(n: int, client: httpx.AsyncClient) -> list[RepoInfo]:
    """
    Return top-N most-starred Python repos.

    The search API caps at 100 per page, so we paginate.
    Sort by stars descending — this is what "top" means for our use case.
    """
    repos: list[RepoInfo] = []
    page = 1
    per_page = 100

    while len(repos) < n:
        # NOTE: this query includes tutorials/awesome-lists too. If you want
        # only "real" code, add filters like "size:>1000" or exclude common
        # non-code repo topics. Left as a TODO for you.
        params = {
            "q": "language:Python",
            "sort": "stars",
            "order": "desc",
            "per_page": per_page,
            "page": page,
        }
        r = await client.get(
            f"{GITHUB_API}/search/repositories",
            params=params,
            headers=_headers(),
            timeout=30.0,
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            break

        for item in items:
            repos.append(
                RepoInfo(
                    full_name=item["full_name"],
                    default_branch=item["default_branch"],
                    stars=item["stargazers_count"],
                    tarball_url=(
                        f"{GITHUB_API}/repos/{item['full_name']}/tarball/"
                        f"{item['default_branch']}"
                    ),
                )
            )
            if len(repos) >= n:
                break
        page += 1

    return repos


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
async def download_repo_tarball(repo: RepoInfo, client: httpx.AsyncClient) -> bytes:
    """
    Download the whole repo as a tarball.

    We follow redirects (tarball_url returns a 302 to a codeload URL).
    Timeout is generous — some repos are big.
    """
    r = await client.get(
        repo.tarball_url,
        headers=_headers(),
        follow_redirects=True,
        timeout=120.0,
    )
    r.raise_for_status()
    return r.content


def iter_python_files_from_tarball(tarball_bytes: bytes):
    """
    Yield (relative_path, source_text) for each .py file in the tarball.

    Tarball root looks like "psf-requests-abc123/..." — we strip that top dir
    so file_path is repo-relative.

    Skips files larger than max_file_size_bytes (usually generated code / data).
    """
    buf = io.BytesIO(tarball_bytes)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile() or not member.name.endswith(".py"):
                continue
            if member.size > settings.max_file_size_bytes:
                continue

            # Strip the leading "owner-repo-sha/" prefix
            parts = member.name.split("/", 1)
            rel_path = parts[1] if len(parts) == 2 else parts[0]

            try:
                f = tar.extractfile(member)
                if f is None:
                    continue
                raw = f.read()
                # Some repos have non-UTF-8 files (rare but real). Skip those.
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    continue
                yield rel_path, text
            except Exception:
                # A single bad file shouldn't kill the whole ingest.
                continue
