"""Current project inputs and generated-artifact lineage. All validators are read-only.

A file being present, or looking plausible in ffprobe, is not proof that it
belongs to the current scripts. Public workflow stages consume these contracts.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
import re
import config
from pipeline.artifact_identity import (
    read_record,
    sha256_file,
    output_record_matches,
    write_output_record,
)
from pipeline.indexed_files import indexed_files
from pipeline.io_utils import positive


def indexed(directory, prefix, extension):
    return indexed_files(os.path.join(directory, prefix + "_*" + extension))


def same(left, right, label):
    if left.keys() != right.keys():
        raise RuntimeError(
            f"{label} indices mismatch; missing={sorted(left.keys() - right.keys())}, extra={sorted(right.keys() - left.keys())}"
        )


def scripts():
    result = indexed(config.DIR_SCRIPTS, "script", ".txt")
    if not result:
        raise RuntimeError("no scripts/script_NN.txt found")
    for path in result.values():
        if not Path(path).read_text(encoding="utf-8").strip():
            raise RuntimeError(f"empty script: {Path(path).name}")
    return result


def require_audio():
    from pipeline import fish_tts

    source = scripts()
    audio = indexed(config.DIR_AUDIO, "audio", ".mp3")
    same(source, audio, "narration audio")
    for index, path in audio.items():
        text = Path(source[index]).read_text(encoding="utf-8").strip()
        expected = fish_tts._identity_record(
            text, config.FISH_REFERENCE_ID, config.FISH_MODEL
        )
        record = os.path.join(config.DIR_AUDIO, f"audio_{index:02d}.identity.json")
        if not output_record_matches(record, expected, path):
            raise RuntimeError(
                f"audio_{index:02d} is stale or unbound; review and run tts --force"
            )
    return audio


def require_timings():
    from pipeline import durations, transcribe, build_scene

    audio = require_audio()
    values = durations.load_validated(config.DIR_AUDIO, config.DURATIONS_JSON)
    if not isinstance(values, list) or len(values) != len(audio):
        raise RuntimeError("duration count does not match narration")
    values = [positive(value, "scene duration") for value in values]
    words = indexed(config.DIR_SRT, "srt", ".json")
    same(audio, words, "word timelines")
    for (index, path), duration in zip(words.items(), values):
        expected = transcribe._identity_record(audio[index])
        record = os.path.join(config.DIR_SRT, f"timing_{index:02d}.identity.json")
        if not output_record_matches(record, expected, path):
            raise RuntimeError(
                f"srt_{index:02d} is stale or unbound; run timing --force"
            )
        build_scene.validate_words(
            json.loads(Path(path).read_text(encoding="utf-8")), duration
        )
    return audio, words, values


def scene_expected(index):
    return {
        "schema": "video-scaffold.scene-inputs.v1",
        "scene_id": index,
        "template_sha256": sha256_file(config.TEMPLATE_BASE),
        "builder_sha256": sha256_file(str(Path(__file__).with_name("build_scene.py"))),
        "fragment_sha256": sha256_file(
            os.path.join(config.DIR_SCENE, f"fragment_{index:02d}.svg")
        ),
        "words_sha256": sha256_file(
            os.path.join(config.DIR_SRT, f"srt_{index:02d}.json")
        ),
    }


def record_scene(index, path):
    write_output_record(
        os.path.join(config.DIR_SCENE, f"scene_{index:02d}.identity.json"),
        scene_expected(index),
        path,
    )


def require_scenes():
    from pipeline.resources import inventory

    audio, words, values = require_timings()
    scenes = indexed(config.DIR_SCENE, "scene", ".html")
    fragments = indexed(config.DIR_SCENE, "fragment", ".svg")
    same(audio, fragments, "SVG fragments")
    same(audio, scenes, "built scenes")
    for index, path in scenes.items():
        record = os.path.join(config.DIR_SCENE, f"scene_{index:02d}.identity.json")
        if not output_record_matches(record, scene_expected(index), path):
            raise RuntimeError(f"scene_{index:02d} is stale or unbound; run build")
        text = Path(path).read_text(encoding="utf-8")
        if re.search(r"\bdata-cue(?:-missing)?\s*=", text):
            # Template documentation contains example cues; inspect the actual SVG.
            from html.parser import HTMLParser

            class Check(HTMLParser):
                missing = False

                def handle_starttag(self, tag, attrs):
                    if any(k in ("data-cue", "data-cue-missing") for k, v in attrs):
                        self.missing = True

            check = Check()
            check.feed(text)
            if check.missing:
                raise RuntimeError(f"unresolved narration cue in scene_{index:02d}")
    inventory(scenes.values())
    return scenes, values


def video_expected(scenes=None, values=None):
    from pipeline import render

    if scenes is None:
        scenes, values = require_scenes()
    count = round(sum(values) * config.FPS)
    if count < 1:
        raise RuntimeError("timeline is shorter than one frame")
    expected = render._render_identity_record(list(scenes.values()), values, 1, count)
    expected["schema"] = "video-scaffold.video-track.v1"
    expected.pop("frames", None)
    expected["total_frames"] = count
    expected["renderer_sha256"] = sha256_file(
        str(Path(__file__).with_name("render.py"))
    )
    return expected


def video_path():
    return os.path.join(config.DIR_OUTPUT, "video_track.mp4")


def record_video(path, expected):
    write_output_record(path + ".identity.json", expected, path)


def require_video():
    scenes, values = require_scenes()
    expected = video_expected(scenes, values)
    path = video_path()
    if not output_record_matches(path + ".identity.json", expected, path):
        raise RuntimeError("video_track.mp4 is stale or unbound; run render")
    return path, values, expected


def final_expected():
    video, values, expected = require_video()
    bgm = config.BGM_PATH
    return {
        "schema": "video-scaffold.final-video.v1",
        "video_sha256": sha256_file(video),
        "video_inputs": expected,
        "audio": [
            {"scene_id": i, "sha256": sha256_file(p)}
            for i, p in require_audio().items()
        ],
        "bgm_sha256": sha256_file(bgm) if os.path.isfile(bgm) else None,
        "bgm_volume": config.BGM_VOLUME,
        "merge_sha256": sha256_file(str(Path(__file__).with_name("merge.py"))),
        "expected_frames": round(sum(values) * config.FPS),
        "expected_seconds": round(sum(values) * config.FPS) / config.FPS,
    }


def require_final():
    expected = final_expected()
    path = os.path.join(config.DIR_OUTPUT, "final_output.mp4")
    if not output_record_matches(path + ".identity.json", expected, path):
        raise RuntimeError("final_output.mp4 is stale or unbound; run merge")
    return expected


def cover_expected(title, subtitle, kicker, hero_path):
    return {
        "schema": "video-scaffold.cover.v1",
        "title": title,
        "subtitle": subtitle,
        "kicker": kicker,
        "hero_path": str(Path(hero_path).resolve()) if hero_path else None,
        "hero_sha256": sha256_file(hero_path) if hero_path else None,
        "template_sha256": sha256_file(config.TEMPLATE_COVER),
    }


def require_cover():
    path = os.path.join(config.DIR_OUTPUT, "cover.png")
    record = read_record(path + ".identity.json")
    if record is None:
        raise RuntimeError("cover.png is unbound; run cover")
    expected = cover_expected(
        str(config.PROJECT_TITLE).strip(),
        record.get("subtitle", ""),
        record.get("kicker", ""),
        record.get("hero_path"),
    )
    if not output_record_matches(path + ".identity.json", expected, path):
        raise RuntimeError("cover.png is stale; run cover")
    return expected


def chapters_expected(definitions):
    audio, words, values = require_timings()
    return {
        "schema": "video-scaffold.chapters.v1",
        "definitions": str(Path(definitions).resolve()),
        "definitions_sha256": sha256_file(definitions),
        "scenes": [{"scene_id": i, "duration": d} for i, d in zip(audio, values)],
    }


def require_chapters():
    from pipeline.chapters import validate_lines

    path = os.path.join(config.DIR_OUTPUT, "chapters.txt")
    record = read_record(path + ".identity.json")
    if record is None or not record.get("definitions"):
        raise RuntimeError("chapters are unbound; run chapters")
    expected = chapters_expected(record["definitions"])
    if not output_record_matches(path + ".identity.json", expected, path):
        raise RuntimeError("chapters are stale; run chapters")
    validate_lines(
        Path(path).read_text(encoding="utf-8"),
        sum(item["duration"] for item in expected["scenes"]),
    )
    return expected


def status():
    checks = (
        ("scripts", scripts),
        ("tts", require_audio),
        ("timing", require_timings),
        ("build", require_scenes),
        ("render", require_video),
        ("merge", require_final),
        ("cover", require_cover),
        ("chapters", require_chapters),
    )
    stages = []
    for name, validator in checks:
        try:
            validator()
            stages.append(
                {
                    "stage": name,
                    "state": "current",
                    "reason": "input and output identities match",
                }
            )
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
            stages.append(
                {"stage": name, "state": "needs_action", "reason": str(error)}
            )
    return {
        "schema": "video-scaffold.status.v1",
        "read_only": True,
        "stages": stages,
        "plan": [item["stage"] for item in stages if item["state"] != "current"],
        "human_review": "preview and final viewing are separate from structural verification",
    }


def subtitles_expected():
    audio, words, values = require_timings()
    return {
        "schema": "video-scaffold.subtitles.v1",
        "scenes": [
            {"scene_id": i, "duration": d, "words_sha256": sha256_file(words[i])}
            for i, d in zip(audio, values)
        ],
        "exporter_sha256": sha256_file(str(Path(__file__).with_name("subtitles.py"))),
    }


def require_subtitles():
    expected = subtitles_expected()
    for name in ("subtitles.srt", "subtitles.vtt"):
        path = os.path.join(config.DIR_OUTPUT, name)
        if not output_record_matches(path + ".identity.json", expected, path):
            raise RuntimeError(f"{name} is stale or unbound; run subtitles")
    return expected
