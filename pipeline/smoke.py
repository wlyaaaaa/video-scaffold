"""Isolated real media/browser integration with explicitly synthetic narration fixtures."""

from __future__ import annotations
import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import config


def _browser_acceptance():
    from playwright.sync_api import sync_playwright
    from pipeline.serve import preview_server
    from urllib.request import urlopen

    with preview_server() as url:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True, channel="chrome")
            except Exception:
                browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(url, wait_until="networkidle")
                page.wait_for_function("document.getElementById('audio').readyState>=1")
                assert page.locator("#scenes button").count() == 2
                page.locator("#words button").first.click()
                expected_time = (
                    page.locator("#words button")
                    .first.get_attribute("title")
                    .split("–")[0]
                )
                page.wait_for_function(
                    "t=>Math.abs(document.getElementById('audio').currentTime-t)<.08",
                    arg=float(expected_time),
                )
                assert not errors, errors
                assert (
                    page.locator("#scene").get_attribute("src").endswith("?preview=1")
                )
                page.locator("#scenes button").nth(1).click()
                page.wait_for_function("document.getElementById('audio').readyState>=1")
                page.locator("details summary").click()
                with page.expect_download() as download:
                    page.locator("#export").click()
                assert download.value.suggested_filename == "fragment_04.svg"
                page.screenshot(
                    path=str(Path(config.DIR_OUTPUT) / "smoke-preview.png"),
                    full_page=True,
                )
                from urllib.error import HTTPError

                try:
                    urlopen(url.replace("/output/preview.html", "/secret_local.py"))
                    raise AssertionError("preview served private configuration")
                except HTTPError as error:
                    assert error.code == 404
            finally:
                browser.close()
    return {
        "http_preview": True,
        "word_seek": True,
        "scene_selection": True,
        "svg_download": True,
    }


def _inside_fixture_impl(*, live_fish=False):
    if not getattr(config, "SMOKE_FIXTURE", False):
        raise RuntimeError(
            "internal fixture mode requires an isolated generated project"
        )
    from pipeline import fish_tts, transcribe, durations, workflow, cleanup, contracts
    from pipeline.artifact_identity import write_output_record, sha256_file
    from pipeline.io_utils import atomic_json, run

    config.ensure_dirs()
    ids = [1, 4]
    scripts = ["测试画面，确认同步。", "第二画面，确认结束。"]
    for index, text in zip(ids, scripts):
        (Path(config.DIR_SCRIPTS) / f"script_{index:02d}.txt").write_text(
            text, encoding="utf-8"
        )
        (Path(config.DIR_SCENE) / f"fragment_{index:02d}.svg").write_text(
            f'<g transform="translate(300,850)"><text data-anim="fade-up" data-cue="{text[:4]}" data-delay="0.1" data-dur="0.25" x="0" y="0" font-size="180" fill="#0C2B1B">{text[:4]}</text></g>',
            encoding="utf-8",
        )
    if live_fish:
        workflow.stage_tts()
        workflow.stage_timing()
    else:
        for index, text in zip(ids, scripts):
            audio = str(Path(config.DIR_AUDIO) / f"audio_{index:02d}.mp3")
            run(
                [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    f"sine=frequency={440 + index * 50}:duration=1.2:sample_rate=48000",
                    "-ac",
                    "2",
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                    audio,
                ]
            )
            write_output_record(
                str(Path(config.DIR_AUDIO) / f"audio_{index:02d}.identity.json"),
                fish_tts._identity_record(
                    text, config.FISH_REFERENCE_ID, config.FISH_MODEL
                ),
                audio,
            )
            words = str(Path(config.DIR_SRT) / f"srt_{index:02d}.json")
            atomic_json(
                words,
                [
                    {"word": text[:4], "start": 0.2, "end": 0.75},
                    {"word": text[5:], "start": 0.8, "end": 1.1},
                ],
            )
            write_output_record(
                str(Path(config.DIR_SRT) / f"timing_{index:02d}.identity.json"),
                transcribe._identity_record(audio),
                words,
            )
        durations.build()
    atomic_json(
        Path(config.ROOT) / "chapters.json",
        [{"scene": 1, "title": "测试"}, {"scene": 4, "title": "结束"}],
    )
    workflow.stage_build()
    workflow.stage_preview()
    browser = _browser_acceptance()
    workflow.stage_render()
    workflow.stage_merge()
    workflow.stage_cover(subtitle="Synthetic fixture / 非配音质量证明")
    workflow.stage_chapters()
    workflow.stage_subtitles()
    workflow.stage_manifest()
    first = {
        p.name: sha256_file(str(p))
        for p in Path(config.DIR_OUTPUT).glob("_chunk_*.mp4")
    }
    # A completed video must be rejected when a fragment changes, before rebuilding.
    fragment = Path(config.DIR_SCENE) / "fragment_04.svg"
    fragment.write_text(
        fragment.read_text(encoding="utf-8").replace(
            'fill="#0C2B1B"', 'fill="#1F7A4D"'
        ),
        encoding="utf-8",
    )
    rejected = False
    try:
        contracts.require_final()
    except RuntimeError:
        rejected = True
    assert rejected, "stale final video accepted"
    workflow.stage_build()
    workflow.stage_render()
    workflow.stage_merge()
    workflow.stage_preview()
    workflow.stage_manifest()
    second = {
        p.name: sha256_file(str(p))
        for p in Path(config.DIR_OUTPUT).glob("_chunk_*.mp4")
    }
    reused = sum(first.get(name) == digest for name, digest in second.items())
    rebuilt = sum(first.get(name) != digest for name, digest in second.items())
    assert reused > 0 and rebuilt > 0, (reused, rebuilt)
    assert cleanup.verify()
    result = {
        "schema": "video-scaffold.smoke.v1",
        "status": "pass",
        "narration": "live Fish"
        if live_fish
        else "synthetic tones; not speech quality",
        "encoder": config.VCODEC,
        "canvas": [config.WIDTH, config.HEIGHT, config.FPS],
        "browser": browser,
        "stale_final_rejected": rejected,
        "reused_chunks": reused,
        "rebuilt_chunks": rebuilt,
        "actual_frames": contracts.require_final()["expected_frames"],
        "default_project_untouched": True,
    }
    atomic_json(Path(config.DIR_OUTPUT) / "smoke-result.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return result


def _inside_fixture(*, live_fish=False):
    from pipeline.gpu import gpu_lease

    with gpu_lease():
        return _inside_fixture_impl(live_fish=live_fish)


def run_fixture(target=None, *, gpu=False, live_fish=False):
    from init_project import init

    if target is not None:
        destination = Path(target).resolve()
        if destination.exists() and (
            not destination.is_dir() or any(destination.iterdir())
        ):
            raise RuntimeError("refusing nonempty demo/smoke target")
        context = nullcontext(str(destination))
    else:
        context = tempfile.TemporaryDirectory(prefix="video-scaffold-smoke-")
    with context as directory:
        init(directory)
        config_path = Path(directory) / "config.py"
        with config_path.open("a", encoding="utf-8") as output:
            output.write(
                "\nSMOKE_FIXTURE=True\nPROJECT_TITLE='合成验收测试'\nNUM_WORKERS=1\nCHUNK_FRAMES=30\nCINEMATIC=False\n"
            )
            if not live_fish:
                output.write(
                    "FISH_MODEL='synthetic-integration-fixture'\nFISH_REFERENCE_ID='synthetic-fixture'\nWHISPER_MODEL='synthetic-integration-fixture'\nTIMING_SOURCE='whisper'\n"
                )
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        if not gpu:
            environment["VIDEO_ENCODER_PROFILE"] = "cpu-h264"
        if config.GPU_BROKER_URL:
            environment["VIDEO_GPU_BROKER_URL"] = config.GPU_BROKER_URL
        command = [sys.executable, "-B", "-m", "pipeline.smoke", "--inside-fixture"]
        if live_fish:
            command.append("--live-fish")
        result = subprocess.run(
            command, cwd=directory, env=environment, timeout=900, check=False
        )
        if result.returncode:
            raise RuntimeError(
                f"isolated media acceptance failed: exit {result.returncode}"
            )
        report = json.loads(
            (Path(directory) / "output" / "smoke-result.json").read_text(
                encoding="utf-8"
            )
        )
        if target:
            print(f"[smoke] isolated artifacts retained at {directory}")
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target", help="retain an isolated project at this empty target"
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="use configured production GPU encoding, not explicit CPU fixture profile",
    )
    parser.add_argument(
        "--live-fish",
        action="store_true",
        help="explicitly synthesize test narration using the configured account; no source key file is copied",
    )
    parser.add_argument("--inside-fixture", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inside_fixture:
        _inside_fixture(live_fish=args.live_fish)
    else:
        run_fixture(args.target, gpu=args.gpu, live_fish=args.live_fish)


if __name__ == "__main__":
    main()
