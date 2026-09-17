# -*- coding: utf-8 -*-
"""Generic, content-neutral command surface for one video project.

The workflow deliberately stops between ``prompts`` and ``build``: a human or
an AI author must review each prompt and save the resulting SVG fragment as
``scene_html/fragment_NN.svg``. Nothing in this module chooses a topic, writes a
script, or designs a scene on its own.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.io_utils import safe_print as print
from pipeline import author, build_scene, chapters, cleanup, cover, durations
from pipeline import fish_tts, lint, merge, preview, render, transcribe
from pipeline.indexed_files import indexed_files
from pipeline import contracts
from pipeline.artifact_identity import write_output_record
from pipeline.io_utils import project_lock, atomic_json


def _indexed(pattern: str) -> dict[int, str]:
    return indexed_files(pattern)


def _require(label: str, indexed: dict[int, str]) -> dict[int, str]:
    if not indexed:
        raise RuntimeError(f"no {label} found")
    return indexed


def _same_indices(
    left_name: str, left: dict[int, str], right_name: str, right: dict[int, str]
) -> None:
    if left.keys() != right.keys():
        missing = sorted(left.keys() - right.keys())
        extra = sorted(right.keys() - left.keys())
        raise RuntimeError(
            f"{right_name} do not match {left_name}; missing={missing}, extra={extra}"
        )


def _load_durations(scene_count: int | None = None) -> list[float]:
    if not os.path.isfile(config.DURATIONS_JSON):
        raise RuntimeError("durations.json is missing; run timing first")
    if not durations.identity_matches(config.DIR_AUDIO, config.DURATIONS_JSON):
        raise RuntimeError(
            "durations.json does not match the current narration audio; run timing first"
        )
    with open(config.DURATIONS_JSON, encoding="utf-8") as source:
        values = json.load(source)
    if (
        not isinstance(values, list)
        or not values
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
            for value in values
        )
    ):
        raise RuntimeError(
            "durations.json must be a non-empty list of positive seconds"
        )
    result = [float(value) for value in values]
    if scene_count is not None and len(result) != scene_count:
        raise RuntimeError(
            f"duration count {len(result)} does not match scene count {scene_count}"
        )
    return result


def stage_tts(*, force: bool = False, **_: object) -> bool:
    scripts = _require(
        "scripts/script_NN.txt",
        _indexed(os.path.join(config.DIR_SCRIPTS, "script_*.txt")),
    )
    fish_tts.synth_batch(force=force)
    audio = _indexed(os.path.join(config.DIR_AUDIO, "audio_*.mp3"))
    _same_indices("scripts", scripts, "audio clips", audio)
    return True


def stage_timing(*, force: bool = False, **_: object) -> bool:
    scripts = _require(
        "scripts/script_NN.txt",
        _indexed(os.path.join(config.DIR_SCRIPTS, "script_*.txt")),
    )
    audio = _require(
        "raw_audio/audio_NN.mp3",
        _indexed(os.path.join(config.DIR_AUDIO, "audio_*.mp3")),
    )
    _same_indices("scripts", scripts, "audio clips", audio)
    contracts.require_audio()
    durations.build()
    transcribe.transcribe_batch(force=force)
    words = _indexed(os.path.join(config.DIR_SRT, "srt_*.json"))
    _same_indices("audio clips", audio, "word timelines", words)
    _load_durations(len(audio))
    return True


def stage_prompts(**_: object) -> bool:
    contracts.require_timings()
    _require(
        "scripts/script_NN.txt",
        _indexed(os.path.join(config.DIR_SCRIPTS, "script_*.txt")),
    )
    author.assemble_all()
    return True


def stage_build(**_: object) -> bool:
    from pathlib import Path

    audio, timelines, values = contracts.require_timings()
    fragments = _indexed(os.path.join(config.DIR_SCENE, "fragment_*.svg"))
    _same_indices("narration", audio, "SVG fragments", fragments)
    prepared = []
    # Parse every fragment before changing any accepted scene.
    for index, path in fragments.items():
        fragment = Path(path).read_text(encoding="utf-8")
        words = json.loads(Path(timelines[index]).read_text(encoding="utf-8"))
        resolved = build_scene.resolve_cues(fragment, words)
        if "data-cue-missing=" in resolved:
            raise RuntimeError(f"unresolved narration cues: scene_{index:02d}")
        prepared.append((index, fragment))
    for index, fragment in prepared:
        output = os.path.join(config.DIR_SCENE, f"scene_{index:02d}.html")
        identity = contracts.scene_expected(index)
        from pipeline.artifact_identity import output_record_matches

        if output_record_matches(
            os.path.join(config.DIR_SCENE, f"scene_{index:02d}.identity.json"),
            identity,
            output,
        ):
            print(f"[build] reuse scene_{index:02d}")
            continue
        build_scene.build(fragment, output, srt=timelines[index], strict=True)
        contracts.record_scene(index, output)
    return True


def _scenes_and_durations() -> tuple[list[str], list[float]]:
    scenes, values = contracts.require_scenes()
    return list(scenes.values()), values


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
    lint_count = lint.lint(scenes, scene_durations)
    if lint_count:
        raise RuntimeError(f"layout lint found {lint_count} HARD finding(s)")
    expected = contracts.video_expected()
    result = render.render_timeline(scenes, scene_durations)
    if expected != contracts.video_expected():
        raise RuntimeError("render inputs changed while rendering; rerun render")
    contracts.record_video(result, expected)
    return True


def stage_merge(**_: object) -> bool:
    video_track = os.path.join(config.DIR_OUTPUT, "video_track.mp4")
    if not os.path.isfile(video_track) or os.path.getsize(video_track) == 0:
        raise RuntimeError("output/video_track.mp4 is missing; run render first")
    contracts.require_video()
    expected = contracts.final_expected()
    audio_track = merge.concat_audio()
    if not audio_track:
        raise RuntimeError(
            "narration audio is missing; refusing to create a silent final delivery"
        )
    result = merge.mux(video_track, audio_track)
    if expected != contracts.final_expected():
        raise RuntimeError("merge inputs changed; rerun merge")
    write_output_record(result + ".identity.json", expected, result)
    return True


def stage_cover(
    *, subtitle: str = "", kicker: str = "", hero: str | None = None, **_: object
) -> bool:
    title = str(config.PROJECT_TITLE).strip()
    if not title or title == "Untitled Video":
        raise RuntimeError(
            "set PROJECT_TITLE (or VIDEO_PROJECT_TITLE) before rendering a cover"
        )
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
        raw_title = item.get("title", "")
        title = raw_title.strip() if isinstance(raw_title, str) else ""
        if (
            type(scene) is not int
            or scene < 1
            or not title
            or "\n" in title
            or "\r" in title
        ):
            raise RuntimeError("each chapter needs scene >= 1 and a non-empty title")
        groups.append((scene - 1, title))
    indices = [index for index, _title in groups]
    if indices[0] != 0:
        raise RuntimeError("chapters.json must start at scene 1")
    if indices != sorted(set(indices)):
        raise RuntimeError("chapter scenes must be unique and strictly increasing")
    return groups


def stage_chapters(*, chapters_json: str | None = None, **_: object) -> bool:
    audio, words, values = contracts.require_timings()
    path = chapters_json or os.path.join(config.ROOT, "chapters.json")
    groups = _chapter_groups(path)
    ids = list(audio)
    if any(index + 1 not in audio for index, title in groups):
        raise RuntimeError("chapters.json refers to an absent scene ID")
    positional = [(ids.index(index + 1), title) for index, title in groups]
    result = chapters.write(chapters.from_scene_groups(values, positional))
    write_output_record(
        result + ".identity.json", contracts.chapters_expected(path), result
    )
    return True


def stage_status(**_: object) -> bool:
    print(json.dumps(contracts.status(), ensure_ascii=False, indent=2))
    return True


def stage_subtitles(**_: object) -> bool:
    from pipeline.subtitles import export

    export()
    return True


def stage_manifest(**_: object) -> bool:
    if not cleanup.verify():
        return False
    from pipeline.artifact_identity import sha256_file

    files = ["final_output.mp4", "cover.png", "chapters.txt"]
    if any(
        os.path.exists(os.path.join(config.DIR_OUTPUT, name))
        for name in ("subtitles.srt", "subtitles.vtt")
    ):
        contracts.require_subtitles()
        files += ["subtitles.srt", "subtitles.vtt"]
    atomic_json(
        os.path.join(config.DIR_OUTPUT, "delivery.json"),
        {
            "schema": "video-scaffold.delivery.v1",
            "title": config.PROJECT_TITLE,
            "files": [
                {
                    "name": name,
                    "sha256": sha256_file(os.path.join(config.DIR_OUTPUT, name)),
                }
                for name in files
            ],
            "inputs": contracts.require_final(),
            "human_viewing": "required, not automatically certified",
        },
    )
    return True


def stage_verify(**_: object) -> bool:
    return cleanup.verify()


def stage_cleanup(*, dry_run=False, **_: object) -> bool:
    cleanup.cleanup(dry_run=dry_run)
    return True


STAGES = {
    "status": stage_status,
    "plan": stage_status,
    "subtitles": stage_subtitles,
    "manifest": stage_manifest,
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
    parser = argparse.ArgumentParser(
        description="Run one content-neutral video workflow stage."
    )
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview generated-file cleanup without writing",
    )
    parser.add_argument(
        "--json", action="store_true", help="status/plan already emit JSON"
    )
    parser.add_argument(
        "--force", action="store_true", help="regenerate accepted TTS/timing files"
    )
    parser.add_argument("--subtitle", default="", help="cover subtitle")
    parser.add_argument("--kicker", default="", help="cover kicker")
    parser.add_argument("--hero", help="cover hero image path")
    parser.add_argument(
        "--chapters-json", help="chapter definitions; defaults to chapters.json"
    )
    args = vars(parser.parse_args())
    stage = args.pop("stage")
    try:
        if stage in ("status", "plan", "verify") or (
            stage == "cleanup" and args.get("dry_run")
        ):
            accepted = STAGES[stage](**args)
        else:
            with project_lock(config.ROOT):
                accepted = STAGES[stage](**args)
    except Exception as error:
        print(f"[workflow] FAIL {stage}: {error}", file=sys.stderr)
        return 1
    if not accepted:
        print(f"[workflow] FAIL {stage}", file=sys.stderr)
        return 1
    if stage not in ("status", "plan"):
        print(f"[workflow] PASS {stage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
