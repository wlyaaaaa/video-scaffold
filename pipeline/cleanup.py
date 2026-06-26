# -*- coding: utf-8 -*-
"""
Stage 6c/6d - temp cleanup + ready check.

cleanup() removes heavy intermediates (chunk files, rendered/, the temp merged
audio, optionally srt/scene_html) to free NVMe space. verify() confirms the
deliverables exist and are non-empty so a publish step can trust the workspace.
"""

import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def cleanup(keep_srt=True, keep_scene_html=True):
    removed = []

    for pat in (os.path.join(config.DIR_OUTPUT, "_chunk_*.mp4"),
                os.path.join(config.DIR_OUTPUT, "_concat.txt"),
                os.path.join(config.DIR_OUTPUT, "_audio_list.txt"),
                os.path.join(config.DIR_OUTPUT, "_main_audio.mp3"),
                os.path.join(config.DIR_RENDERED, "*")):
        for f in glob.glob(pat):
            try:
                os.remove(f); removed.append(f)
            except OSError:
                pass

    if not keep_srt:
        for f in glob.glob(os.path.join(config.DIR_SRT, "*.json")):
            try: os.remove(f); removed.append(f)
            except OSError: pass
    if not keep_scene_html:
        for f in glob.glob(os.path.join(config.DIR_SCENE, "*.html")):
            try: os.remove(f); removed.append(f)
            except OSError: pass

    print(f"[cleanup] removed {len(removed)} temp files")
    return removed


def verify(required=("final_output.mp4", "cover.png")):
    ok = True
    for name in required:
        path = os.path.join(config.DIR_OUTPUT, name)
        size = os.path.getsize(path) if os.path.exists(path) else 0
        status = "OK" if size > 0 else "MISSING"
        if size == 0:
            ok = False
        print(f"[verify] {status:8s} {name} ({size} bytes)")
    print("[verify] READY" if ok else "[verify] NOT READY")
    return ok


if __name__ == "__main__":
    cleanup()
    verify()
