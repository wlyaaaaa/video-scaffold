"""Explicit opt-in adapter to the existing scaffold's real Fish production entry."""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import sys

from .common import new_output, probe, read_json, run, sha256, temp_workspace, write_json


def narrate(text_path, output_path, *, legacy_root):
    text_path, legacy_root = Path(text_path).resolve(), Path(legacy_root).resolve()
    output = new_output(output_path)
    for suffix in (".json", ".timestamps.json"):
        if Path(str(output) + suffix).exists():
            raise FileExistsError("Narration evidence already exists; use a new output filename")
    if output.suffix.lower() != ".mp3":
        raise ValueError("Existing Fish narration adapter outputs MP3")
    if not (legacy_root / "pipeline/fish_tts.py").is_file():
        raise FileNotFoundError("The existing Fish production adapter is unavailable at --legacy-root")
    text = text_path.read_text(encoding="utf-8-sig").strip()
    input_file_hash = sha256(text_path)
    if not text:
        raise ValueError("Narration script is empty")
    with temp_workspace(output.parent, "narration-") as temporary:
        scripts, audio = temporary / "scripts", temporary / "audio"
        scripts.mkdir()
        audio.mkdir()
        (scripts / "script_01.txt").write_text(text, encoding="utf-8")
        # Key retrieval stays entirely inside the existing explicitly invoked
        # TTS entry. No credential lookup, login, or secret output is added.
        code = "from pipeline.fish_tts import synth_batch; import sys; synth_batch(scripts_dir=sys.argv[1], audio_dir=sys.argv[2])"
        env = dict(os.environ, TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary))
        run([sys.executable, "-X", "utf8", "-B", "-c", code, scripts, audio], cwd=legacy_root, env=env, timeout=420)
        if input_file_hash != sha256(text_path):
            raise RuntimeError("Narration script changed during synthesis; output was not rebound to the new script")
        return publish_existing(text_path, audio / "audio_01.mp3", audio / "audio_01.identity.json",
                                audio / "audio_01.mp3.timestamps.json", output, move=True)


def publish_existing(text_path, source, identity_path, native, output, *, move=False):
    """Recover an already synthesized, source-bound clip without generating again."""
    import shutil
    text_path, source, native, output = map(Path, (text_path, source, native, output))
    new_output(output)
    for suffix in (".json", ".timestamps.json"):
        if Path(str(output) + suffix).exists():
            raise FileExistsError("Narration evidence already exists")
    text = text_path.read_text(encoding="utf-8-sig").strip()
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    source_identity = read_json(identity_path)
    if source_identity.get("output_sha256") != sha256(source) or source_identity.get("script_sha256") != text_hash:
        raise RuntimeError("Existing Fish audio/script identity does not match its consumed bytes")
    duration = float(probe(source)["format"]["duration"])
    cues, timing_source = [], "unavailable"
    if native.is_file():
        timestamps = read_json(native)
        if timestamps.get("audio_sha256") != sha256(source):
            raise RuntimeError("Native Fish timestamps have the wrong audio fingerprint")
        current, start, end = "", None, 0
        for word in timestamps["words"]:
            word_text = word.get("text", word.get("word", ""))
            word_start, word_end = float(word["start"]), float(word["end"])
            if not 0 <= word_start <= word_end <= duration:
                raise RuntimeError("Fish timestamp is outside its audio track")
            if start is None:
                start = word_start
            current += word_text
            end = word_end
            if len(current) >= 20 or current.endswith(("。", "！", "？", "；", ".", "!", "?")):
                if end > start:
                    cues.append({"start": start, "end": end, "text": current})
                current, start = "", None
        if current and end > start:
            cues.append({"start": start, "end": end, "text": current})
        timing_source = "Fish native timestamps"
    transfer = (lambda a,b: Path(a).replace(b)) if move else shutil.copyfile
    transfer(source, output)
    if native.is_file():
        transfer(native, Path(str(output) + ".timestamps.json"))
    result = {"schema": "webfilm.narration.v1", "source": "existing video-scaffold Fish production entry",
              "text_sha256": text_hash, "text_file_sha256": sha256(text_path), "audio_sha256": sha256(output), "duration": duration,
              "tts_identity": source_identity, "timing_source": timing_source, "cues": cues}
    write_json(str(output) + ".json", result)
    return result
