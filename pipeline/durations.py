# -*- coding: utf-8 -*-
"""
Stage 2 - precise duration probe.

ffprobe each raw_audio/audio_NN.mp3 to a float second value (6 dp) and write
durations.json (an ordered list). Every later stage trusts this list as the
single source of truth for how long each scene must last.
"""

import os
import sys
import json
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.io_utils import safe_print as print
from pipeline.artifact_identity import (
    output_record_matches,
    sha256_file,
    write_output_record,
)
from pipeline.indexed_files import indexed_files


def identity_path(out_json=config.DURATIONS_JSON):
    return out_json + ".identity.json"


def _identity_record(audio_paths):
    return {
        "schema": "video-scaffold.duration-list-identity.v1",
        "audio": [
            {"name": os.path.basename(path), "sha256": sha256_file(path)}
            for path in audio_paths
        ],
        "probe": "ffprobe-format-duration-rounded-6dp",
    }


def identity_matches(audio_dir=config.DIR_AUDIO, out_json=config.DURATIONS_JSON):
    audios = indexed_files(os.path.join(audio_dir, "audio_*.mp3"))
    return output_record_matches(
        identity_path(out_json),
        _identity_record(list(audios.values())),
        out_json,
    )


def load_validated(audio_dir=config.DIR_AUDIO, out_json=config.DURATIONS_JSON):
    if not identity_matches(audio_dir, out_json):
        raise RuntimeError(
            "durations.json has no matching audio identity; run timing before later stages"
        )
    with open(out_json, encoding="utf-8") as source:
        return json.load(source)


def probe_seconds(media_path):
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            media_path,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=True,
    )
    from pipeline.io_utils import positive

    return round(positive(float(out.stdout.strip()), "media duration"), 6)


def build(audio_dir=config.DIR_AUDIO, out_json=config.DURATIONS_JSON):
    audios = indexed_files(os.path.join(audio_dir, "audio_*.mp3"))
    if not audios:
        raise RuntimeError("no narration audio")
    from pipeline.io_utils import atomic_json, positive

    durations = [
        positive(probe_seconds(path), "media duration") for path in audios.values()
    ]
    atomic_json(out_json, durations)
    write_output_record(
        identity_path(out_json),
        _identity_record(list(audios.values())),
        out_json,
    )
    print(
        f"[durations] {len(durations)} clips, total {sum(durations):.3f}s -> {out_json}"
    )
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
