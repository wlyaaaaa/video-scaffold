# -*- coding: utf-8 -*-
"""
Stage 6b - Bilibili chapter markers (分 P / 章节).

Bilibili turns lines like "MM:SS Title" (or "HH:MM:SS Title") in the video
description into clickable chapters. Rules we honour:
  * the first marker MUST be 00:00,
  * titles stay short (chapters are a table of contents, not sentences),
  * a handful of chapters reads best - we warn past CHAPTER_MAX.

Chapters are coarser than scenes: you usually group several scenes under one
heading. Pass either explicit (start_seconds, title) pairs, or scene-index
groupings resolved against the duration list.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

CHAPTERS_TXT = os.path.join(config.DIR_OUTPUT, "chapters.txt")


def fmt_ts(seconds):
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def title_len(title):
    """Visual length: CJK glyph = 1, latin/digit/space ≈ 0.6 (so 'vs'/'BUFF'/'22'
    don't over-count). Used to keep chapter titles glanceably short."""
    return round(sum(1.0 if ord(c) >= 0x2E80 else 0.6 for c in title.strip()), 1)


def audit(chapters):
    """Warn when the two principles are broken: too many chapters, a title that's
    too long, or two chapters too close together. Returns the list unchanged."""
    n, budget = len(chapters), config.CHAPTER_TITLE_MAXLEN
    if n > config.CHAPTER_MAX:
        print(
            f"[chapters] WARN {n} chapters (> {config.CHAPTER_MAX}) - fewer reads better; merge some."
        )
    for t, title in chapters:
        if title_len(title) > budget:
            print(
                f"[chapters] WARN title too long ({title_len(title)} > {budget}): "
                f"{title!r} @ {fmt_ts(t)} - shorten it (4-6 chars)."
            )
    sc = sorted(chapters, key=lambda c: c[0])
    for (t0, a), (t1, b) in zip(sc, sc[1:]):
        if t1 - t0 < config.CHAPTER_MIN_GAP:
            print(
                f"[chapters] WARN {b!r} only {t1 - t0:.0f}s after {a!r} "
                f"(< {config.CHAPTER_MIN_GAP}s) - Bilibili may reject; merge or move."
            )
    return chapters


def from_scene_groups(durations, groups):
    """groups: list of (scene_index, title). scene_index is 0-based start scene
    of that chapter. Returns [(start_seconds, title)] with the offsets summed."""
    offsets, acc = [], 0.0
    for d in durations:
        offsets.append(acc)
        acc += d
    return [(offsets[i], title) for i, title in groups]


def validate_lines(text, total_seconds):
    import re
    from pipeline.io_utils import positive

    total_seconds = positive(total_seconds, "video duration")
    previous = -1
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("empty chapters")
    for position, line in enumerate(lines):
        match = re.fullmatch(r"(?:(\d{2,}):)?(\d{2}):(\d{2}) ([^\r\n]+)", line)
        if not match:
            raise ValueError(f"malformed chapter line: {line}")
        hours, minutes, seconds, title = match.groups()
        if (
            int(seconds) >= 60
            or (hours is not None and int(minutes) >= 60)
            or not title.strip()
        ):
            raise ValueError("invalid chapter time/title")
        value = int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)
        if (
            (position == 0 and value != 0)
            or value <= previous
            or value >= total_seconds
        ):
            raise ValueError(
                "chapters must start at zero, increase, and lie inside the video"
            )
        previous = value
    return lines


def write(chapters, out_path=None):
    out_path = out_path or os.path.join(config.DIR_OUTPUT, "chapters.txt")
    from pipeline.io_utils import atomic_text, positive

    if not chapters:
        raise ValueError("empty chapters")
    previous = -1
    for seconds, title in chapters:
        positive(seconds, "chapter time", zero=True)
        if (
            seconds <= previous
            or not isinstance(title, str)
            or not title.strip()
            or "\n" in title
            or "\r" in title
        ):
            raise ValueError("invalid chapter ordering or title")
        previous = seconds
    if chapters[0][0] != 0:
        raise ValueError("chapters must start at zero")
    audit(chapters)
    lines = [f"{fmt_ts(t)} {title.strip()}" for t, title in chapters]
    text = "\n".join(lines) + "\n"
    validate_lines(text, max(t for t, title in chapters) + 2)
    atomic_text(out_path, text)
    print(f"[chapters] {len(lines)} markers -> {out_path}")
    return out_path
