from __future__ import annotations

import ast
import hashlib
from typing import Iterator

from backend.models import CodeChunk


def _github_url(repo: str, default_branch: str, file_path: str, start: int, end: int) -> str:
    return (
        f"https://github.com/{repo}/blob/{default_branch}/{file_path}"
        f"#L{start}-L{end}"
    )


def _chunk_id(repo: str, file_path: str, name: str, start_line: int) -> str:
    """Deterministic short id — same inputs always give same id, so re-ingest doesn't dup."""
    raw = f"{repo}::{file_path}::{name}::{start_line}"
    return hashlib.blake2b(raw.encode(), digest_size=8).hexdigest()


def _extract_docstring(node: ast.AST) -> str | None:
    """Get the first docstring if the node is one of def/class."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
        return ast.get_docstring(node)
    return None


def _node_source(source: str, node: ast.AST) -> str:
    lines = source.splitlines(keepends=True)
    # ast is 1-indexed; end_lineno is inclusive
    start = node.lineno - 1
    end = getattr(node, "end_lineno", node.lineno)
    return "".join(lines[start:end])


def chunk_python_file(
    *,
    repo: str,
    default_branch: str,
    file_path: str,
    source: str,
) -> Iterator[CodeChunk]:
    
    try:
        tree = ast.parse(source, filename=file_path)
    except (SyntaxError, ValueError, RecursionError):
        return

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield _make_chunk(
                repo=repo,
                default_branch=default_branch,
                file_path=file_path,
                source=source,
                node=node,
                name=node.name,
                kind="function",
            )
        elif isinstance(node, ast.ClassDef):
            # Emit the class itself
            yield _make_chunk(
                repo=repo,
                default_branch=default_branch,
                file_path=file_path,
                source=source,
                node=node,
                name=node.name,
                kind="class",
            )
            # Emit methods as separate chunks so queries can match individual methods
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield _make_chunk(
                        repo=repo,
                        default_branch=default_branch,
                        file_path=file_path,
                        source=source,
                        node=sub,
                        name=f"{node.name}.{sub.name}",
                        kind="method",
                    )


def _make_chunk(
    *,
    repo: str,
    default_branch: str,
    file_path: str,
    source: str,
    node: ast.AST,
    name: str,
    kind: str,
) -> CodeChunk:
    start = node.lineno
    end = getattr(node, "end_lineno", node.lineno)
    return CodeChunk(
        chunk_id=_chunk_id(repo, file_path, name, start),
        repo=repo,
        file_path=file_path,
        start_line=start,
        end_line=end,
        kind=kind,
        name=name,
        docstring=_extract_docstring(node),
        source=_node_source(source, node),
        github_url=_github_url(repo, default_branch, file_path, start, end),
    )
