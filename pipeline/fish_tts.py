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
import glob
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def synth_one(text, out_path, reference_id=config.FISH_REFERENCE_ID, model=config.FISH_MODEL):
    """Synthesize a single utterance. Returns True on success.

    For the production 央视 voice pass model=FISH_MODEL + reference_id (needs
    credit). For a free default-voice clip pass model=FISH_MODEL_FREE and
    reference_id=None (the free model ignores custom references).
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
    return True


def synth_batch(scripts_dir=config.DIR_SCRIPTS, audio_dir=config.DIR_AUDIO,
                reference_id=config.FISH_REFERENCE_ID, model=config.FISH_MODEL):
    """Synthesize every script_NN.txt -> audio_NN.mp3 in order."""
    config.ensure_dirs()
    scripts = sorted(glob.glob(os.path.join(scripts_dir, "script_*.txt")))
    if not scripts:
        print(f"[fish] no scripts in {scripts_dir}")
        return []

    outputs = []
    for script in scripts:
        idx = os.path.splitext(os.path.basename(script))[0].split("_")[-1]
        with open(script, "r", encoding="utf-8") as f:
            text = f.read().strip()
        out_path = os.path.join(audio_dir, f"audio_{idx}.mp3")
        print(f"[fish] {os.path.basename(script)} -> {os.path.basename(out_path)} ({len(text)} chars)")
        if synth_one(text, out_path, reference_id=reference_id, model=model):
            outputs.append(out_path)
        else:
            print(f"  [fish] FAILED on {script}; aborting batch.")
            break
    return outputs


if __name__ == "__main__":
    synth_batch()
