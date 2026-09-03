# -*- coding: utf-8 -*-
"""
Stage 6c/6d - temp cleanup + ready check.

cleanup() removes heavy intermediates (chunk files, rendered/, the temp merged
audio, optionally srt/scene_html) to free NVMe space. verify() confirms the
deliverables exist and are non-empty so a publish step can trust the workspace.
"""

import os
import sys
import glob
import json
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def cleanup(keep_srt=True, keep_scene_html=True):
    removed = []

    for pat in (os.path.join(config.DIR_OUTPUT, "_chunk_*.mp4"),
                os.path.join(config.DIR_OUTPUT, "_concat.txt"),
                os.path.join(config.DIR_OUTPUT, "_audio_list.txt"),
                os.path.join(config.DIR_OUTPUT, "_main_audio.mp3"),
                os.path.join(config.DIR_OUTPUT, "_render_identity.json"),
                os.path.join(config.DIR_RENDERED, "*")):
        for f in glob.glob(pat):
            try:
                os.remove(f); removed.append(f)
            except OSError:
                pass

    if not keep_srt:
        for f in glob.glob(os.path.join(config.DIR_SRT, "*.json")):
            try: os.remove(f); removed.append(f)
            except OSError: pass
    if not keep_scene_html:
        for f in glob.glob(os.path.join(config.DIR_SCENE, "*.html")):
            try: os.remove(f); removed.append(f)
            except OSError: pass

    print(f"[cleanup] removed {len(removed)} temp files")
    return removed


def _ffprobe(path):
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


def _first_stream(probe, kind):
    return next((stream for stream in probe.get("streams", [])
                 if stream.get("codec_type") == kind), None)


def _fps(stream):
    rate = str(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/1")
    try:
        numerator, denominator = (float(part) for part in rate.split("/", 1))
        return numerator / denominator if denominator else 0.0
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _expected_codec():
    return {
        "av1_nvenc": "av1",
        "h264_nvenc": "h264",
        "hevc_nvenc": "hevc",
    }.get(config.VCODEC, config.VCODEC)


def _duration(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def verify():
    """Validate the actual Bilibili delivery contract, not only file presence."""
    ok = True

    def report(passed, name, detail):
        nonlocal ok
        ok = ok and passed
        print(f"[verify] {'PASS' if passed else 'FAIL':4s} {name}: {detail}")

    final_path = os.path.join(config.DIR_OUTPUT, "final_output.mp4")
    cover_path = os.path.join(config.DIR_OUTPUT, "cover.png")
    chapters_path = os.path.join(config.DIR_OUTPUT, "chapters.txt")

    title = str(getattr(config, "PROJECT_TITLE", "")).strip()
    report(bool(title and title != "Untitled Video"), "project-title", title or "missing")

    for name, path in (("final", final_path), ("cover", cover_path),
                       ("chapters", chapters_path)):
        size = os.path.getsize(path) if os.path.isfile(path) else 0
        report(size > 0, f"{name}-file", f"{size} bytes" if size else "missing or empty")

    if os.path.isfile(final_path) and os.path.getsize(final_path) > 0:
        try:
            probe = _ffprobe(final_path)
            video = _first_stream(probe, "video")
            audio = _first_stream(probe, "audio")
            report(video is not None, "video-stream", "present" if video else "missing")
            report(audio is not None, "audio-stream", "present" if audio else "missing")
            if video:
                dimensions = (int(video.get("width", 0)), int(video.get("height", 0)))
                report(dimensions == (config.WIDTH, config.HEIGHT),
                       "video-size", f"{dimensions[0]}x{dimensions[1]}")
                fps = _fps(video)
                report(abs(fps - config.FPS) < 0.01, "video-fps", f"{fps:g}")
                codec = str(video.get("codec_name", ""))
                report(codec == _expected_codec(), "video-codec", codec or "missing")
            format_duration = _duration(probe.get("format", {}).get("duration"))
            report(bool(format_duration and format_duration > 0),
                   "video-duration", f"{format_duration or 0:.3f}s")
            if video and audio:
                video_duration = _duration(video.get("duration"))
                audio_duration = _duration(audio.get("duration"))
                if video_duration is not None and audio_duration is not None:
                    delta = abs(video_duration - audio_duration)
                    report(delta <= max(0.25, 2 / config.FPS),
                           "av-duration-delta", f"{delta:.3f}s")
        except Exception as error:
            report(False, "final-probe", str(error))

    if os.path.isfile(cover_path) and os.path.getsize(cover_path) > 0:
        try:
            probe = _ffprobe(cover_path)
            cover = _first_stream(probe, "video")
            dimensions = ((int(cover.get("width", 0)), int(cover.get("height", 0)))
                          if cover else (0, 0))
            report(dimensions == (config.WIDTH, config.HEIGHT),
                   "cover-size", f"{dimensions[0]}x{dimensions[1]}")
        except Exception as error:
            report(False, "cover-probe", str(error))

    if os.path.isfile(chapters_path) and os.path.getsize(chapters_path) > 0:
        try:
            with open(chapters_path, encoding="utf-8") as chapter_file:
                lines = [line.strip() for line in chapter_file if line.strip()]
            report(bool(lines and lines[0].startswith("00:00 ")), "chapters-start",
                   lines[0] if lines else "empty")
        except (OSError, UnicodeError) as error:
            report(False, "chapters-read", str(error))

    scene_paths = sorted(glob.glob(os.path.join(config.DIR_SCENE, "scene_*.html")))
    report(bool(scene_paths), "scene-count", str(len(scene_paths)))
    missing_cues = []
    for scene in scene_paths:
        try:
            with open(scene, encoding="utf-8") as scene_file:
                text = scene_file.read()
        except (OSError, UnicodeError) as error:
            report(False, "scene-read", f"{scene}: {error}")
            continue
        if "data-cue-missing=" in text:
            missing_cues.append(os.path.basename(scene))
    report(not missing_cues, "cue-audit",
           "no unresolved cues" if not missing_cues else ", ".join(missing_cues))

    print("[verify] READY" if ok else "[verify] NOT READY")
    return ok


if __name__ == "__main__":
    cleanup()
    raise SystemExit(0 if verify() else 1)
