# -*- coding: utf-8 -*-
"""
Stage 2 - precise duration probe.

ffprobe each raw_audio/audio_NN.mp3 to a float second value (6 dp) and write
durations.json (an ordered list). Every later stage trusts this list as the
single source of truth for how long each scene must last.
"""

import os
import sys
import glob
import json
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def probe_seconds(media_path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", media_path],
        capture_output=True, text=True, check=True,
    )
    return round(float(out.stdout.strip()), 6)


def build(audio_dir=config.DIR_AUDIO, out_json=config.DURATIONS_JSON):
    audios = sorted(glob.glob(os.path.join(audio_dir, "audio_*.mp3")))
    durations = [probe_seconds(a) for a in audios]
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(durations, f, indent=2)
    print(f"[durations] {len(durations)} clips, total {sum(durations):.3f}s -> {out_json}")
    return durations


def offsets(durations):
    """Absolute timeline start of each scene: [0, d0, d0+d1, ...]."""
    acc, out = 0.0, []
    for d in durations:
        out.append(acc)
        acc += d
    return out


if __name__ == "__main__":
    build()
