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
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.io_utils import safe_print as print
from pipeline.artifact_identity import (
    sha256_bytes,
    write_output_record,
)
from pipeline.indexed_files import indexed_basename, indexed_files


def _identity_record(text, reference_id, model):
    return {
        "schema": "video-scaffold.tts-artifact-identity.v2",
        "script_sha256": sha256_bytes(text.encode("utf-8")),
        "endpoint": config.FISH_ENDPOINT,
        "model": model,
        "reference_id": reference_id or "",
        "format": config.FISH_FORMAT,
        "tail_silence_seconds": config.SCENE_TAIL_SILENCE,
    }


def audio_identity_matches(record_path, expected, audio_path):
    """Keep production provenance, but do not re-synthesize to select another timeline."""
    from pipeline.artifact_identity import read_record, sha256_file

    record = read_record(record_path)
    if not record or record.get("schema") not in (
        "video-scaffold.tts-artifact-identity.v1",
        "video-scaffold.tts-artifact-identity.v2",
    ):
        return False
    actual = dict(record)
    output_hash = actual.pop("output_sha256", None)
    if actual["schema"].endswith(".v1"):
        if actual.pop("timing_source", None) not in ("whisper", "fish"):
            return False
        actual["schema"] = expected["schema"]
    return (
        actual == expected
        and os.path.isfile(audio_path)
        and output_hash == sha256_file(audio_path)
    )


def _pad_tail(path, seconds=None):
    from pipeline.io_utils import atomic_output, run, positive

    sec = config.SCENE_TAIL_SILENCE if seconds is None else seconds
    positive(sec, "tail silence", zero=True)
    if not sec:
        return
    with atomic_output(path) as work:
        run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                path,
                "-af",
                f"apad=pad_dur={sec}",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-c:a",
                "libmp3lame",
                "-q:a",
                "2",
                work,
            ]
        )


def synth_one(text, out_path, reference_id=None, model=None):
    from pathlib import Path
    from pipeline.io_utils import atomic_output, atomic_json
    from pipeline.artifact_identity import sha256_file
    from pipeline.durations import probe_seconds
    import time

    reference_id = config.FISH_REFERENCE_ID if reference_id is None else reference_id
    model = config.FISH_MODEL if model is None else model
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty narration")
    if config.FISH_FORMAT != "mp3":
        raise ValueError("the current workflow requires MP3 narration")
    key = config.get_fish_api_key()
    if not key:
        raise RuntimeError("FISH_API_KEY is missing")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "model": model,
    }
    body = {"text": text, "format": "mp3"}
    if reference_id:
        body["reference_id"] = reference_id
    native = config.FISH_NATIVE_TIMESTAMPS
    url = config.FISH_ENDPOINT.rstrip("/") + (
        "/stream/with-timestamp" if native else ""
    )
    for attempt in range(3):
        response = None
        try:
            response = requests.post(
                url, headers=headers, json=body, timeout=(10, 120), stream=native
            )
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                response.close()
                time.sleep(1 + attempt)
                continue
            if response.status_code != 200:
                print(f"[fish] HTTP {response.status_code}")
                return False
            words = None
            with atomic_output(out_path) as work:
                if native:
                    from pipeline.fish_native import decode

                    with open(work, "wb") as output:
                        words = decode(response.iter_lines(), output)
                else:
                    Path(work).write_bytes(response.content)
                probe_seconds(work)
                _pad_tail(work)
                duration = probe_seconds(work)
                if words:
                    from pipeline.build_scene import validate_words

                    validate_words(words, duration)
            if words is not None:
                atomic_json(
                    str(out_path) + ".timestamps.json",
                    {
                        "schema": "video-scaffold.fish-timestamps.v1",
                        "audio_sha256": sha256_file(out_path),
                        "words": words,
                    },
                )
            elif not native:
                Path(str(out_path) + ".timestamps.json").unlink(missing_ok=True)
            return True
        except (requests.Timeout, requests.ConnectionError):
            if attempt == 2:
                raise
            time.sleep(1 + attempt)
        finally:
            if response is not None:
                response.close()
    return False


def synth_batch(
    scripts_dir=config.DIR_SCRIPTS,
    audio_dir=config.DIR_AUDIO,
    reference_id=config.FISH_REFERENCE_ID,
    model=config.FISH_MODEL,
    force=False,
):
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
        identity_path = os.path.join(
            audio_dir,
            indexed_basename("audio", index, ".identity.json"),
        )
        identity = _identity_record(text, reference_id, model)
        if not force and os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
            if audio_identity_matches(identity_path, identity, out_path):
                print(
                    f"[fish] reuse {os.path.basename(out_path)} (source identity matched)"
                )
                outputs.append(out_path)
                continue
            raise RuntimeError(
                f"{os.path.basename(out_path)} has no matching source identity; "
                "refusing stale narration reuse. Review the script, then run tts --force."
            )
        print(
            f"[fish] {os.path.basename(script)} -> {os.path.basename(out_path)} ({len(text)} chars)"
        )
        import tempfile
        from pathlib import Path
        from pipeline.io_utils import publish_bundle

        with tempfile.TemporaryDirectory(prefix=".tts-", dir=audio_dir) as temporary:
            staged = str(Path(temporary) / Path(out_path).name)
            if not synth_one(text, staged, reference_id=reference_id, model=model):
                raise RuntimeError(
                    f"Fish synthesis failed for {os.path.basename(script)}"
                )
            staged_identity = str(Path(temporary) / Path(identity_path).name)
            write_output_record(staged_identity, identity, staged)
            pairs = [(staged, out_path), (staged_identity, identity_path)]
            if config.FISH_NATIVE_TIMESTAMPS:
                pairs.append(
                    (staged + ".timestamps.json", out_path + ".timestamps.json")
                )
            publish_bundle(pairs)
            if not config.FISH_NATIVE_TIMESTAMPS:
                # A deliberately regenerated plain-TTS clip must not inherit an
                # obsolete native sidecar and block the shared-alignment route.
                Path(out_path + ".timestamps.json").unlink(missing_ok=True)
            outputs.append(out_path)
    return outputs


if __name__ == "__main__":
    synth_batch()
