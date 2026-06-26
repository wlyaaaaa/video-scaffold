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


def from_scene_groups(durations, groups):
    """groups: list of (scene_index, title). scene_index is 0-based start scene
    of that chapter. Returns [(start_seconds, title)] with the offsets summed."""
    offsets, acc = [], 0.0
    for d in durations:
        offsets.append(acc)
        acc += d
    return [(offsets[i], title) for i, title in groups]


def write(chapters, out_path=CHAPTERS_TXT):
    """chapters: list of (start_seconds, title), ascending."""
    chapters = sorted(chapters, key=lambda c: c[0])
    if not chapters:
        return None
    if chapters[0][0] > 0.001:
        chapters = [(0.0, chapters[0][1])] + chapters[1:]  # Bilibili needs 00:00
    if len(chapters) > config.CHAPTER_MAX:
        print(f"[chapters] WARN {len(chapters)} chapters (> {config.CHAPTER_MAX}); "
              f"Bilibili reads best with fewer, shorter headings.")
    lines = [f"{fmt_ts(t)} {title.strip()}" for t, title in chapters]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[chapters] {len(lines)} markers -> {out_path}")
    return out_path
