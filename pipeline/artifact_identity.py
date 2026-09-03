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


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_record(path: str) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def write_record(path: str, value: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = f"{path}.{os.getpid()}.tmp"
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as target:
            json.dump(value, target, ensure_ascii=False, indent=2, sort_keys=True)
            target.write("\n")
        os.replace(temporary, path)
    finally:
        try:
            if os.path.exists(temporary):
                os.remove(temporary)
        except OSError:
            pass


def output_record_matches(path: str, expected: dict[str, Any], output_path: str) -> bool:
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
