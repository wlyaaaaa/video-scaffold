# -*- coding: utf-8 -*-
"""
Stage 0.2 + 1.1 - inputs prep.

scan_assets()  : list the game art in assets/ and report N (the scene count is
                 usually driven by the script, but this validates the art set).
slice_script() : split one long narration into natural paragraphs and write
                 scripts/script_01.txt .. script_NN.txt.
"""

import os
import re
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def scan_assets(assets_dir=config.DIR_ASSETS):
    imgs = sorted(glob.glob(os.path.join(assets_dir, "*.png")))
    print(f"[prep] {len(imgs)} assets in {assets_dir}")
    for p in imgs:
        print(f"        {os.path.basename(p)}")
    return imgs


def slice_script(full_text, max_chars=120):
    """Split into paragraphs: blank lines first, else by sentence punctuation,
    greedily packing up to ~max_chars so each scene is a digestible beat."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", full_text) if b.strip()]
    if len(blocks) > 1:
        return blocks
    sentences = re.split(r"(?<=[。！？!?])", full_text.strip())
    segments, cur = [], ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(cur) + len(s) > max_chars and cur:
            segments.append(cur)
            cur = s
        else:
            cur += s
    if cur:
        segments.append(cur)
    return segments


def write_scripts(segments, scripts_dir=config.DIR_SCRIPTS):
    config.ensure_dirs()
    paths = []
    for i, seg in enumerate(segments, 1):
        p = os.path.join(scripts_dir, f"script_{i:02d}.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write(seg.strip())
        paths.append(p)
    print(f"[prep] wrote {len(paths)} scripts")
    return paths


if __name__ == "__main__":
    scan_assets()
