# -*- coding: utf-8 -*-
"""Generic, content-neutral command surface for one video project.

The workflow deliberately stops between ``prompts`` and ``build``: a human or
an AI author must review each prompt and save the resulting SVG fragment as
``scene_html/fragment_NN.svg``. Nothing in this module chooses a topic, writes a
script, or designs a scene on its own.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline import author, build_scene, chapters, cleanup, cover, durations
from pipeline import fish_tts, lint, merge, preview, render, transcribe


def _indexed(pattern: str) -> dict[int, str]:
    indexed: dict[int, str] = {}
    for path in sorted(glob.glob(pattern)):
        match = re.search(r"_(\d+)\.[^.]+$", os.path.basename(path))
        if not match:
            continue
        index = int(match.group(1))
        if index in indexed:
            raise RuntimeError(f"duplicate index {index:02d}: {indexed[index]} and {path}")
        indexed[index] = path
    return indexed


def _require(label: str, indexed: dict[int, str]) -> dict[int, str]:
    if not indexed:
        raise RuntimeError(f"no {label} found")
    return indexed


def _same_indices(left_name: str, left: dict[int, str], right_name: str,
                  right: dict[int, str]) -> None:
    if left.keys() != right.keys():
        missing = sorted(left.keys() - right.keys())
        extra = sorted(right.keys() - left.keys())
        raise RuntimeError(
            f"{right_name} do not match {left_name}; missing={missing}, extra={extra}"
        )


def _load_durations(scene_count: int | None = None) -> list[float]:
    if not os.path.isfile(config.DURATIONS_JSON):
        raise RuntimeError("durations.json is missing; run timing first")
    with open(config.DURATIONS_JSON, encoding="utf-8") as source:
        values = json.load(source)
    if not isinstance(values, list) or not values or any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
        for value in values
    ):
        raise RuntimeError("durations.json must be a non-empty list of positive seconds")
    result = [float(value) for value in values]
    if scene_count is not None and len(result) != scene_count:
        raise RuntimeError(
            f"duration count {len(result)} does not match scene count {scene_count}"
        )
    return result


def stage_tts(*, force: bool = False, **_: object) -> bool:
    scripts = _require("scripts/script_NN.txt", _indexed(os.path.join(config.DIR_SCRIPTS, "script_*.txt")))
    fish_tts.synth_batch(force=force)
    audio = _indexed(os.path.join(config.DIR_AUDIO, "audio_*.mp3"))
    _same_indices("scripts", scripts, "audio clips", audio)
    return True


def stage_timing(*, force: bool = False, **_: object) -> bool:
    scripts = _require("scripts/script_NN.txt", _indexed(os.path.join(config.DIR_SCRIPTS, "script_*.txt")))
    audio = _require("raw_audio/audio_NN.mp3", _indexed(os.path.join(config.DIR_AUDIO, "audio_*.mp3")))
    _same_indices("scripts", scripts, "audio clips", audio)
    durations.build()
    transcribe.transcribe_batch(force=force)
    words = _indexed(os.path.join(config.DIR_SRT, "srt_*.json"))
    _same_indices("audio clips", audio, "word timelines", words)
    _load_durations(len(audio))
    return True


def stage_prompts(**_: object) -> bool:
    _require("scripts/script_NN.txt", _indexed(os.path.join(config.DIR_SCRIPTS, "script_*.txt")))
    author.assemble_all()
    return True


def stage_build(**_: object) -> bool:
    scripts = _require("scripts/script_NN.txt", _indexed(os.path.join(config.DIR_SCRIPTS, "script_*.txt")))
    fragments = _indexed(os.path.join(config.DIR_SCENE, "fragment_*.svg"))
    timelines = _indexed(os.path.join(config.DIR_SRT, "srt_*.json"))
    _same_indices("scripts", scripts, "SVG fragments", fragments)
    _same_indices("scripts", scripts, "word timelines", timelines)

    unresolved: list[str] = []
    for index in scripts:
        with open(fragments[index], encoding="utf-8") as source:
            fragment = source.read()
        output = os.path.join(config.DIR_SCENE, f"scene_{index:02d}.html")
        build_scene.build(fragment, output, srt=timelines[index])
        with open(output, encoding="utf-8") as built:
            if "data-cue-missing=" in built.read():
                unresolved.append(os.path.basename(output))
    if unresolved:
        raise RuntimeError("unresolved narration cues: " + ", ".join(unresolved))
    return True


def _scenes_and_durations() -> tuple[list[str], list[float]]:
    scenes = _require("scene_html/scene_NN.html", _indexed(os.path.join(config.DIR_SCENE, "scene_*.html")))
    return [scenes[index] for index in sorted(scenes)], _load_durations(len(scenes))


def stage_lint(**_: object) -> bool:
    scenes, scene_durations = _scenes_and_durations()
    hard_findings = lint.lint(scenes, scene_durations)
    if hard_findings:
        raise RuntimeError(f"layout lint found {hard_findings} HARD finding(s)")
    return True


def stage_preview(**_: object) -> bool:
    _scenes_and_durations()
    preview.build()
    return True


def stage_render(**_: object) -> bool:
    scenes, scene_durations = _scenes_and_durations()
    render.render_timeline(scenes, scene_durations)
    return True


def stage_merge(**_: object) -> bool:
    video_track = os.path.join(config.DIR_OUTPUT, "video_track.mp4")
    if not os.path.isfile(video_track) or os.path.getsize(video_track) == 0:
        raise RuntimeError("output/video_track.mp4 is missing; run render first")
    audio_track = merge.concat_audio()
    if not audio_track:
        raise RuntimeError("narration audio is missing; refusing to create a silent final delivery")
    merge.mux(video_track, audio_track)
    return True


def stage_cover(*, subtitle: str = "", kicker: str = "", hero: str | None = None,
                **_: object) -> bool:
    title = str(config.PROJECT_TITLE).strip()
    if not title or title == "Untitled Video":
        raise RuntimeError("set PROJECT_TITLE (or VIDEO_PROJECT_TITLE) before rendering a cover")
    cover.build(title, subtitle=subtitle, kicker=kicker, hero_path=hero)
    return True


def _chapter_groups(path: str) -> list[tuple[int, str]]:
    if not os.path.isfile(path):
        raise RuntimeError(
            f"{path} is missing; create a JSON list like "
            '[{"scene": 1, "title": "开场"}]'
        )
    with open(path, encoding="utf-8") as source:
        data = json.load(source)
    if not isinstance(data, list) or not data:
        raise RuntimeError("chapters.json must be a non-empty JSON list")
    groups = []
    for item in data:
        if not isinstance(item, dict):
            raise RuntimeError("each chapter must be an object with scene and title")
        scene = item.get("scene")
        title = str(item.get("title", "")).strip()
        if not isinstance(scene, int) or scene < 1 or not title:
            raise RuntimeError("each chapter needs scene >= 1 and a non-empty title")
        groups.append((scene - 1, title))
    indices = [index for index, _title in groups]
    if indices[0] != 0:
        raise RuntimeError("chapters.json must start at scene 1")
    if indices != sorted(set(indices)):
        raise RuntimeError("chapter scenes must be unique and strictly increasing")
    return groups


def stage_chapters(*, chapters_json: str | None = None, **_: object) -> bool:
    scene_durations = _load_durations()
    path = chapters_json or os.path.join(config.ROOT, "chapters.json")
    groups = _chapter_groups(path)
    if any(index >= len(scene_durations) for index, _title in groups):
        raise RuntimeError("chapters.json refers to a scene outside durations.json")
    chapters.write(chapters.from_scene_groups(scene_durations, groups))
    return True


def stage_verify(**_: object) -> bool:
    return cleanup.verify()


def stage_cleanup(**_: object) -> bool:
    cleanup.cleanup()
    return True


STAGES = {
    "tts": stage_tts,
    "timing": stage_timing,
    "prompts": stage_prompts,
    "build": stage_build,
    "lint": stage_lint,
    "preview": stage_preview,
    "render": stage_render,
    "merge": stage_merge,
    "cover": stage_cover,
    "chapters": stage_chapters,
    "verify": stage_verify,
    "cleanup": stage_cleanup,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one content-neutral video workflow stage.")
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument("--force", action="store_true", help="regenerate accepted TTS/timing files")
    parser.add_argument("--subtitle", default="", help="cover subtitle")
    parser.add_argument("--kicker", default="", help="cover kicker")
    parser.add_argument("--hero", help="cover hero image path")
    parser.add_argument("--chapters-json", help="chapter definitions; defaults to chapters.json")
    args = vars(parser.parse_args())
    stage = args.pop("stage")
    try:
        accepted = STAGES[stage](**args)
    except Exception as error:
        print(f"[workflow] FAIL {stage}: {error}", file=sys.stderr)
        return 1
    if not accepted:
        print(f"[workflow] FAIL {stage}", file=sys.stderr)
        return 1
    print(f"[workflow] PASS {stage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
