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
from pipeline.io_utils import safe_print as print


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


def write_scripts(segments, scripts_dir=None, *, mode="create"):
    """create refuses existing numbered scripts; update preserves other scenes;
    replace reconciles only files owned by the previous generated manifest.
    """
    from pathlib import Path
    import tempfile
    from pipeline.indexed_files import indexed_files
    from pipeline.artifact_identity import read_record, sha256_file
    from pipeline.io_utils import publish_bundle, atomic_json

    if mode not in ("create", "update", "replace"):
        raise ValueError("invalid script write mode")
    if not segments or any(not isinstance(s, str) or not s.strip() for s in segments):
        raise ValueError("scripts must be nonempty strings")
    directory = Path(scripts_dir or config.DIR_SCRIPTS)
    existing = indexed_files(str(directory / "script_*.txt"))
    manifest = directory / ".generated-scripts.json"
    previous = read_record(str(manifest)) or {"files": {}}
    if mode == "create" and existing:
        raise RuntimeError(
            "scripts already exist; select update or owned replacement explicitly"
        )
    stale = []
    if mode == "replace":
        for path in existing.values():
            name = Path(path).name
            if previous.get("files", {}).get(name) != sha256_file(path):
                raise RuntimeError(
                    f"refusing to replace unowned or edited original: {name}"
                )
            if int(Path(path).stem.split("_")[-1]) > len(segments):
                stale.append(Path(path))
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".scripts-", dir=directory) as temporary:
        staged = Path(temporary)
        pairs = []
        files = dict(previous.get("files", {})) if mode == "update" else {}
        for index, text in enumerate(segments, 1):
            name = f"script_{index:02d}.txt"
            path = staged / name
            path.write_text(text.strip(), encoding="utf-8")
            files[name] = sha256_file(str(path))
            pairs.append((path, directory / name))
        atomic_json(
            staged / "manifest.json",
            {"schema": "video-scaffold.generated-scripts.v1", "files": files},
        )
        moved = []
        try:
            for path in stale:
                backup = staged / (path.name + ".removed")
                os.replace(path, backup)
                moved.append((backup, path))
            publish_bundle(pairs + [(staged / "manifest.json", manifest)])
        except BaseException:
            for backup, path in reversed(moved):
                os.replace(backup, path)
            raise
    return [
        str(directory / f"script_{index:02d}.txt")
        for index in range(1, len(segments) + 1)
    ]


if __name__ == "__main__":
    scan_assets()
