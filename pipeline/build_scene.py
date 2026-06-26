# -*- coding: utf-8 -*-
"""
Stage 4a - assemble a scene HTML from the universal base board, and (key for
frame-perfect sync) resolve word cues against the Whisper timeline.

The AI writes a small static SVG fragment with data-anim attributes. To pin an
animation to the narration, it adds:

    data-cue="续航能力"      # start exactly when this spoken phrase is heard

This module looks the phrase up in srt_NN.json (Whisper word timestamps) and
rewrites it to  data-delay="<seconds>". Because the renderer drives the scene by
the SAME per-clip timeline, the element then animates on the precise frame the
word is spoken - that is what makes audio and motion 分毫不差.

If no srt is supplied, data-cue attributes are simply dropped (the element falls
back to any data-delay you set, or 0).
"""

import os
import re
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

MARKER = "<!-- @@SCENE_CONTENT@@ -->"


def _load_words(srt):
    if srt is None:
        return []
    if isinstance(srt, str):
        if not os.path.exists(srt):
            return []
        with open(srt, "r", encoding="utf-8") as f:
            return json.load(f)
    return srt


def _char_index(words):
    """Flatten word timestamps into per-character (text, start_time) arrays.

    Time inside a multi-char word is interpolated linearly so a cue lands on the
    right glyph, not just the right word.
    """
    text, times = [], []
    for w in words:
        chars = [c for c in w["word"] if not c.isspace()]
        n = max(len(chars), 1)
        span = w["end"] - w["start"]
        for k, c in enumerate(chars):
            text.append(c)
            times.append(w["start"] + span * (k / n))
    return "".join(text), times


def resolve_cues(fragment, words):
    """Rewrite every data-cue="phrase" into data-delay="t" using the timeline."""
    if not words:
        return re.sub(r'\s*data-cue="[^"]*"', "", fragment)
    full, times = _char_index(words)

    def repl(m):
        phrase = re.sub(r"\s", "", m.group(1))
        idx = full.find(phrase)
        if idx < 0:
            print(f"[scene] WARN cue not found in narration: {m.group(1)!r}")
            return ""  # drop cue; keep any existing data-delay
        return f' data-delay="{times[idx]:.3f}"'

    return re.sub(r'\s*data-cue="([^"]*)"', repl, fragment)


def build(fragment_svg, out_path, template=config.TEMPLATE_BASE, srt=None):
    words = _load_words(srt)
    fragment_svg = resolve_cues(fragment_svg, words)

    with open(template, "r", encoding="utf-8") as f:
        base = f.read()
    if MARKER not in base:
        raise RuntimeError(f"marker {MARKER!r} not found in template")
    html = base.replace(MARKER, fragment_svg)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[scene] -> {out_path}")
    return out_path
