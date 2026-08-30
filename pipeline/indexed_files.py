# -*- coding: utf-8 -*-
"""Discover canonical numbered pipeline artifacts in numeric order."""

from __future__ import annotations

import glob
import os
import re


_PATTERN = re.compile(
    r"(?P<prefix>[A-Za-z][A-Za-z0-9_-]*)_\*(?P<extension>\.[A-Za-z0-9.]+)",
    re.ASCII,
)


def indexed_basename(prefix: str, index: int, extension: str) -> str:
    """Return the one canonical basename for a positive artifact index."""

    if isinstance(index, bool) or not isinstance(index, int) or index < 1:
        raise ValueError("indexed artifact number must be an integer >= 1")
    return f"{prefix}_{index:02d}{extension}"


def _pattern_contract(pattern: str) -> tuple[str, str]:
    name = os.path.basename(pattern)
    match = _PATTERN.fullmatch(name)
    if not match:
        raise ValueError(f"invalid indexed artifact pattern: {name}")
    return match.group("prefix"), match.group("extension")


def _canonical_index(name: str, prefix: str, extension: str) -> int:
    match = re.fullmatch(
        rf"{re.escape(prefix)}_([0-9]+){re.escape(extension)}",
        name,
        flags=re.ASCII,
    )
    if not match:
        raise RuntimeError(f"non-canonical indexed filename: {name}")
    index = int(match.group(1))
    if index < 1:
        raise RuntimeError(f"indexed artifact number must be >= 1: {name}")
    canonical = indexed_basename(prefix, index, extension)
    if name != canonical:
        raise RuntimeError(
            f"non-canonical indexed filename: {name}; expected {canonical}"
        )
    return index


def indexed_files(
    pattern: str,
    *,
    ignore_noncanonical: bool = False,
) -> dict[int, str]:
    """Return canonical matches keyed and ordered by their numeric index.

    Source collections reject malformed and duplicate names. Generated-output
    cleanup may set ``ignore_noncanonical`` so unrelated files remain untouched.
    """

    pattern = os.fspath(pattern)
    prefix, extension = _pattern_contract(pattern)
    found: dict[int, str] = {}
    for path in glob.glob(pattern):
        name = os.path.basename(path)
        try:
            index = _canonical_index(name, prefix, extension)
        except RuntimeError:
            if ignore_noncanonical:
                continue
            raise
        if index in found:
            raise RuntimeError(
                f"duplicate {prefix} index {index:02d}: {found[index]} and {path}"
            )
        found[index] = path
    return {index: found[index] for index in sorted(found)}
