# -*- coding: utf-8 -*-
"""
Stage 1 - Fish Audio TTS.

Turns scripts/script_NN.txt into raw_audio/audio_NN.mp3 using one model in one
batch, so every clip shares the same sample rate / channels / bitrate. That
uniformity is what lets ffmpeg concat the audio later without re-encoding.

API contract (see config.py):
    POST https://api.fish.audio/v1/tts
    headers: Authorization: Bearer <key>, model: <FISH_MODEL>
    json:    {"text": ..., "reference_id": <voice>, "format": "mp3"}
"""

import os
import sys
import subprocess
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.indexed_files import indexed_basename, indexed_files


def _pad_tail(path, seconds=None):
    """Append a short silence so the splice into the next scene breathes instead of
    rushing ("两句话的拼接偏快"). Re-encodes to a uniform mp3 profile (every clip
    identical) so merge can still stream-copy concat. No-op if disabled."""
    sec = config.SCENE_TAIL_SILENCE if seconds is None else seconds
    if not sec or sec <= 0:
        return
    tmp = path + ".pad.mp3"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", path, "-af", f"apad=pad_dur={sec}",
                    "-c:a", "libmp3lame", "-q:a", "2", tmp], check=True)
    os.replace(tmp, path)


def synth_one(text, out_path, reference_id=config.FISH_REFERENCE_ID, model=config.FISH_MODEL):
    """Synthesize a single utterance. Returns True on success.

    The checked-in configuration uses the verified free model together with
    the 云飞 reference voice. ``doctor-live`` is the canonical compatibility
    probe because service-side model behavior can change independently.
    """
    headers = {
        "Authorization": f"Bearer {config.FISH_API_KEY}",
        "Content-Type": "application/json",
        "model": model,
    }
    body = {"text": text, "format": config.FISH_FORMAT}
    if reference_id:
        body["reference_id"] = reference_id

    resp = requests.post(config.FISH_ENDPOINT, headers=headers, json=body, timeout=120)
    if resp.status_code != 200 or not resp.content:
        print(f"  [fish] HTTP {resp.status_code}: {resp.text[:200]}")
        return False
    with open(out_path, "wb") as f:
        f.write(resp.content)
    _pad_tail(out_path)   # add the inter-scene breath; durations.build picks it up
    return True


def synth_batch(scripts_dir=config.DIR_SCRIPTS, audio_dir=config.DIR_AUDIO,
                reference_id=config.FISH_REFERENCE_ID, model=config.FISH_MODEL,
                force=False):
    """Synthesize every script_NN.txt -> audio_NN.mp3 in order.

    Accepted, non-empty clips are reused by default so a later workflow stage
    cannot silently change narration timing. Pass ``force=True`` explicitly to
    regenerate them.
    """
    os.makedirs(audio_dir, exist_ok=True)
    scripts = indexed_files(os.path.join(scripts_dir, "script_*.txt"))
    if not scripts:
        print(f"[fish] no scripts in {scripts_dir}")
        return []

    outputs = []
    for index, script in scripts.items():
        with open(script, "r", encoding="utf-8") as f:
            text = f.read().strip()
        out_path = os.path.join(
            audio_dir,
            indexed_basename("audio", index, ".mp3"),
        )
        if not force and os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
            print(f"[fish] reuse {os.path.basename(out_path)}")
            outputs.append(out_path)
            continue
        print(f"[fish] {os.path.basename(script)} -> {os.path.basename(out_path)} ({len(text)} chars)")
        if synth_one(text, out_path, reference_id=reference_id, model=model):
            outputs.append(out_path)
        else:
            print(f"  [fish] FAILED on {script}; aborting batch.")
            break
    return outputs


if __name__ == "__main__":
    synth_batch()
