# -*- coding: utf-8 -*-
"""Build deterministic SVG scenes with auditable narration-trigger attributes.

Cue timing uses the supplied word timeline and optional within-word interpolation.
Render timestamps are frame-clock driven; estimated speech times are not a
certificate of phonetic accuracy. Missing cues remain visible and strict builds
fail before replacing an accepted scene. Single/double-quoted XML attributes,
occurrence selection, offsets and duplicate-attribute rejection share one parser.
"""

import os
import re
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.io_utils import safe_print as print

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
        # Strip punctuation like commas, periods, question marks from words for robust alignment
        clean_word = re.sub(r"[^\w\s]", "", w["word"])
        chars = [c for c in clean_word if not c.isspace()]
        if not chars:
            continue
        n = len(chars)
        span = w["end"] - w["start"]
        for k, c in enumerate(chars):
            text.append(c)
            times.append(w["start"] + span * (k / n))
    return "".join(text), times


_CN = {
    "零": "0",
    "〇": "0",
    "一": "1",
    "二": "2",
    "两": "2",
    "三": "3",
    "四": "4",
    "五": "5",
    "六": "6",
    "七": "7",
    "八": "8",
    "九": "9",
}
_UNIT = {"十": 10, "百": 100, "千": 1000, "万": 10000, "亿": 100000000}


def _cn_value(run):
    """Parse a Chinese-numeral run to its Arabic value string (三十六->36, 一千->1000)."""
    total = section = cur = 0
    for ch in run:
        if ch in _CN:
            cur = int(_CN[ch])
        elif ch in _UNIT:
            u = _UNIT[ch]
            if u >= 10000:
                section = (section + cur) * u
                total += section
                section = 0
            else:
                cur = cur or 1
                section += cur * u
            cur = 0
    return str(total + section + cur)


def _cue_variants(phrase):
    """Whisper writes numbers as Arabic digits; offer numeral-normalised candidates."""
    cands = [phrase]
    conv = re.sub(
        r"[零〇一二两三四五六七八九十百千万亿]+",
        lambda m: _cn_value(m.group(0)),
        phrase,
    )
    if conv != phrase:
        cands.append(conv)
    if phrase and all(
        c in _CN for c in phrase
    ):  # spoken digit-string e.g. 七四八 -> 748
        cands.append("".join(_CN[c] for c in phrase))
    return cands


def validate_words(words, duration=None):
    from pipeline.io_utils import positive

    if not isinstance(words, list):
        raise ValueError("word timeline must be a list")
    previous = -1.0
    for word in words:
        if (
            not isinstance(word, dict)
            or not isinstance(word.get("word"), str)
            or not word["word"].strip()
        ):
            raise ValueError("invalid word record")
        start = positive(word.get("start"), "word start", zero=True)
        end = positive(word.get("end"), "word end", zero=True)
        if (
            end < start
            or start < previous
            or (duration is not None and end > duration + 0.05)
        ):
            raise ValueError("word timeline is unordered or outside narration")
        previous = start
    return words


def parse_fragment(fragment):
    import xml.etree.ElementTree as ET
    from pipeline.io_utils import positive

    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    try:
        root = ET.fromstring(
            '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
            + fragment
            + "</svg>"
        )
    except ET.ParseError as error:
        raise ValueError(f"invalid static SVG fragment: {error}") from error
    with open(config.TEMPLATE_BASE, encoding="utf-8") as source:
        known = set(re.findall(r'case "([a-z0-9-]+)"', source.read()))
    for element in list(root.iter())[1:]:
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in {
            "script",
            "style",
            "html",
            "iframe",
            "foreignObject",
            "animate",
            "animateTransform",
            "set",
        }:
            raise ValueError(
                f"non-deterministic or unsupported fragment element: {tag}"
            )
        if any(key.lower().startswith("on") for key in element.attrib):
            raise ValueError("event handlers are not part of the static SVG contract")
        animation = element.get("data-anim")
        if animation and animation not in known:
            raise ValueError(f"unknown animation: {animation}")
        for name in ("data-delay", "data-dur"):
            if name in element.attrib:
                positive(float(element.attrib[name]), name, zero=name == "data-delay")
    return root


def resolve_cues(fragment, words):
    """Resolve XML attributes once, including single quotes and occurrence choice."""
    import xml.etree.ElementTree as ET

    root = parse_fragment(fragment)
    validate_words(words)
    full, times = _char_index(words)
    for element in root.iter():
        if "data-cue" not in element.attrib:
            continue
        phrase = element.attrib.pop("data-cue")
        occurrence = element.get("data-cue-index", "1")
        if not occurrence.isascii() or not occurrence.isdigit() or int(occurrence) < 1:
            raise ValueError("data-cue-index must be an integer >= 1")
        found = None
        for candidate in _cue_variants(re.sub(r"[^\w]", "", phrase)):
            if not candidate:
                continue
            offset = -1
            for _ in range(int(occurrence)):
                offset = full.find(candidate, offset + 1)
                if offset < 0:
                    break
            if offset >= 0:
                found = times[offset]
                break
        if found is None:
            element.set("data-cue-missing", phrase)
        else:
            shift = float(element.get("data-cue-offset", "0"))
            import math

            if not math.isfinite(shift) or found + shift < 0:
                raise ValueError("invalid cue offset")
            element.set("data-delay", f"{found + shift:.3f}")
            element.set("data-cue-source", phrase)
            element.attrib.pop("data-cue-missing", None)
    return (root.text or "") + "".join(
        ET.tostring(child, encoding="unicode") for child in root
    )


def build(fragment_svg, out_path, template=None, srt=None, *, strict=False):
    from pipeline.io_utils import atomic_text

    template = template or config.TEMPLATE_BASE
    words = _load_words(srt)
    fragment_svg = resolve_cues(fragment_svg, words)
    if strict and "data-cue-missing=" in fragment_svg:
        raise RuntimeError("unresolved narration cues")
    with open(template, encoding="utf-8") as source:
        base = source.read()
    if base.count(MARKER) != 1:
        raise RuntimeError(f"expected exactly one marker {MARKER!r}")
    atomic_text(out_path, base.replace(MARKER, fragment_svg))
    print(f"[scene] -> {out_path}")
    return out_path
