"""Consume current word timings; local known-text alignment belongs to ChineseASR.

Auto reuses a valid existing timeline, then uses Fish native timestamps when
available, otherwise the registered shared aligner. A malformed present native
record is an error, not permission to conceal the failure or re-synthesize audio.
"""

from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import config
from pipeline.artifact_identity import read_record, sha256_file, write_output_record
from pipeline.indexed_files import indexed_files, indexed_basename
from pipeline.io_utils import atomic_json, publish_bundle, run, safe_print as print
from pipeline.build_scene import validate_words

SCHEMA = "video-scaffold.word-timing.v2"


def _script_path(audio_path):
    index = int(Path(audio_path).stem.split("_")[-1])
    return Path(config.DIR_SCRIPTS) / indexed_basename("script", index, ".txt")


def speech_text(text):
    # Remove only the supported Fish delivery controls, not arbitrary bracketed text.
    tags = set(config.FISH_EMOTION_TAGS + config.FISH_SFX_TAGS)
    return re.sub(
        r"\(([^()]*)\)|\[([^\[\]]*)\]",
        lambda m: "" if (m[1] or m[2]).strip().lower().lstrip("/") in tags else m[0],
        text,
    ).strip()


def _choose_source(audio_path):
    if config.TIMING_SOURCE != "auto":
        return config.TIMING_SOURCE
    return (
        "fish" if Path(str(audio_path) + ".timestamps.json").exists() else "chinese-asr"
    )


def _identity_record(audio_path, source=None):
    source = source or _choose_source(audio_path)
    value = {
        "schema": SCHEMA,
        "audio_sha256": sha256_file(audio_path),
        "script_sha256": sha256_file(str(_script_path(audio_path))),
        "source": source,
    }
    if source == "fish":
        value["native_sha256"] = sha256_file(str(audio_path) + ".timestamps.json")
    return value


def identity_matches(audio_path, timeline_path, record_path):
    record = read_record(record_path)
    if not record or not Path(timeline_path).is_file():
        return False
    if record.get("audio_sha256") != sha256_file(audio_path) or record.get(
        "output_sha256"
    ) != sha256_file(timeline_path):
        return False
    schema = record.get("schema")
    if schema == SCHEMA:
        source = record.get("source")
        if source not in ("fish", "chinese-asr"):
            return False
        if config.TIMING_SOURCE != "auto" and config.TIMING_SOURCE != source:
            return False
        if source == "chinese-asr":
            producer = record.get("producer") or {}
            if (
                not producer.get("model_identity")
                or producer.get("exact_text_coverage") is not True
            ):
                return False
        expected = _identity_record(audio_path, source)
        return all(record.get(k) == v for k, v in expected.items())
    # Narrow read-only compatibility: preserve existing valid outputs and their
    # original declared producer. Do not invent new Whisper provenance.
    if schema == "video-scaffold.word-timing-identity.v1":
        return (
            config.TIMING_SOURCE == "auto"
            and all(
                k in record
                for k in ("model", "device", "compute", "language", "word_timestamps")
            )
            and record["word_timestamps"] is True
        )
    if schema == "video-scaffold.fish-word-timing.v1":
        return config.TIMING_SOURCE in ("auto", "fish") and record.get(
            "native_sha256"
        ) == sha256_file(str(audio_path) + ".timestamps.json")
    return False


def _shared_alignment(audio_path, text, staged_output):
    root, python = Path(config.CHINESE_ASR_ROOT), Path(config.CHINESE_ASR_PYTHON)
    if (
        not config.CHINESE_ASR_ROOT
        or not config.CHINESE_ASR_PYTHON
        or not root.is_dir()
        or not python.is_file()
    ):
        raise RuntimeError(
            "Native timestamps are unavailable. Configure the existing ChineseASR root/interpreter through the machine adapter, or supply Fish native timing; narration was not changed."
        )
    with tempfile.TemporaryDirectory(
        prefix=".shared-align-", dir=Path(staged_output).parent
    ) as temp:
        text_path, result_path = (
            Path(temp) / "narration.txt",
            Path(temp) / "result.json",
        )
        text_path.write_text(text, encoding="utf-8", newline="\n")
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        if config.GPU_BROKER_URL:
            env["LOCAL_GPU_BROKER_URL"] = config.GPU_BROKER_URL
        command = [
            str(python),
            "-X",
            "utf8",
            "-B",
            "-m",
            "zh_asr",
            "align",
            str(Path(audio_path).resolve()),
            "--text-file",
            str(text_path),
            "--output",
            str(result_path),
            "--timeout-sec",
            str(config.ALIGNMENT_TIMEOUT_SECONDS),
        ]
        # The shared CLI supervises its GPU worker; a timed-out parent is
        # observed by that worker and cannot leave model execution orphaned.
        run(
            command,
            cwd=str(root),
            env=env,
            timeout=config.ALIGNMENT_TIMEOUT_SECONDS + 20,
        )
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if (
            result.get("schema") != "zh_asr.alignment-entry.v1"
            or result.get("status") != "succeeded"
            or result.get("exact_text_coverage") is not True
        ):
            raise RuntimeError(
                "ChineseASR did not return a complete known-text alignment"
            )
        if (
            result.get("audio_sha256") != sha256_file(audio_path)
            or result.get("text_sha256")
            != hashlib.sha256(text.encode("utf-8")).hexdigest()
        ):
            raise RuntimeError(
                "ChineseASR alignment belongs to different audio or text"
            )
        words = validate_words(result.get("words"), result.get("duration_seconds"))
        if not words:
            raise RuntimeError("ChineseASR returned no word timings")
        atomic_json(
            str(staged_output) + ".producer.json",
            {
                "model_identity": result.get("model_identity"),
                "lexical_truth_verified": False,
                "exact_text_coverage": True,
            },
        )
        return words


def transcribe_one(audio_path, out_path):
    source = _choose_source(audio_path)
    if source == "fish":
        from pipeline.fish_native import load

        words = load(audio_path)
    else:
        text = speech_text(_script_path(audio_path).read_text(encoding="utf-8"))
        words = _shared_alignment(audio_path, text, out_path)
    validate_words(words)
    atomic_json(out_path, words)
    return words


def transcribe_batch(audio_dir=None, srt_dir=None, force=False):
    audio_dir, srt_dir = audio_dir or config.DIR_AUDIO, srt_dir or config.DIR_SRT
    audios = indexed_files(os.path.join(audio_dir, "audio_*.mp3"))
    if not audios:
        raise RuntimeError("no narration audio")
    Path(srt_dir).mkdir(parents=True, exist_ok=True)
    for index, audio in audios.items():
        out = Path(srt_dir) / indexed_basename("srt", index, ".json")
        record = Path(srt_dir) / indexed_basename("timing", index, ".identity.json")
        if not force and out.is_file():
            if identity_matches(audio, out, record):
                if not validate_words(json.loads(out.read_text(encoding="utf-8"))):
                    raise RuntimeError(
                        "Accepted word timeline is empty; review before regenerating"
                    )
                print(f"[timing] reuse {out.name}; accepted producer retained")
                continue
            raise RuntimeError(
                f"{out.name}: refusing stale word timing reuse; review and run timing --force (audio is preserved)"
            )
        expected = _identity_record(audio)
        print(f"[timing] {Path(audio).name}: {expected['source']}")
        with tempfile.TemporaryDirectory(prefix=".timing-", dir=srt_dir) as temp:
            staged = Path(temp) / out.name
            transcribe_one(audio, str(staged))
            if not validate_words(json.loads(staged.read_text(encoding="utf-8"))):
                raise RuntimeError(
                    "No usable word timings returned; previous output retained"
                )
            if expected != _identity_record(audio):
                raise RuntimeError(
                    "Audio, text or timing source changed during alignment"
                )
            producer = read_record(str(staged) + ".producer.json")
            identity = dict(expected)
            if producer:
                identity["producer"] = producer
            staged_record = Path(temp) / record.name
            write_output_record(staged_record, identity, staged)
            publish_bundle([(staged, out), (staged_record, record)])


if __name__ == "__main__":
    transcribe_batch()
