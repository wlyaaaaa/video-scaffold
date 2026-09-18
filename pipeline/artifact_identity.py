# -*- coding: utf-8 -*-
"""Small, file-backed identities for reusable generated artifacts.

The pipeline deliberately keeps accepted audio, word timing and render chunks
between stages.  Reuse is safe only when the inputs that produced an artifact
still match.  These helpers keep that check local and dependency-free.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any
from contextlib import contextmanager
from contextvars import ContextVar

_HASHES = ContextVar("video_validation_hashes", default=None)


@contextmanager
def validation_session():
    if _HASHES.get() is not None:
        yield
        return
    token = _HASHES.set({})
    try:
        yield
    finally:
        _HASHES.reset(token)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str) -> str:
    def key():
        value = os.stat(path)
        return (
            os.path.realpath(path),
            value.st_dev,
            value.st_ino,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    before = key()
    cache = _HASHES.get()
    if cache is not None and before in cache:
        return cache[before]
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if key() != before:
        raise RuntimeError("File changed while hashing: " + os.fspath(path))
    result = digest.hexdigest()
    if cache is not None:
        cache[before] = result
    return result


def python_code_hash(path):
    """Ignore Python formatting/comments/docstrings, not executable behavior."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            )
            and node.body
        ):
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                node.body = node.body[1:]
    return sha256_bytes(ast.dump(tree, include_attributes=False).encode("utf-8"))


def read_record(path: str) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def write_record(path: str, value: dict[str, Any]) -> None:
    import uuid

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temporary = f"{path}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as target:
            json.dump(
                value,
                target,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            target.write("\n")
        os.replace(temporary, path)
    finally:
        try:
            if os.path.exists(temporary):
                os.remove(temporary)
        except OSError:
            pass


def output_record_matches(
    path: str, expected: dict[str, Any], output_path: str
) -> bool:
    if not os.path.isfile(output_path) or os.path.getsize(output_path) <= 0:
        return False
    actual = read_record(path)
    if actual is None:
        return False
    return actual == {**expected, "output_sha256": sha256_file(output_path)}


def write_output_record(path: str, expected: dict[str, Any], output_path: str) -> None:
    if not os.path.isfile(output_path) or os.path.getsize(output_path) <= 0:
        raise RuntimeError(f"generated artifact is missing or empty: {output_path}")
    write_record(path, {**expected, "output_sha256": sha256_file(output_path)})
