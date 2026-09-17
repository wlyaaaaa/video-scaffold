"""Read-only delivery verification and explicit, bounded generated-file cleanup."""

from __future__ import annotations
import glob
import json
import math
import os
from pathlib import Path
import re
from fractions import Fraction
import config
from pipeline.io_utils import safe_print as print
from pipeline.io_utils import run, positive


def cleanup(keep_srt=True, keep_scene_html=True, *, dry_run=False):
    candidates = []
    output = Path(config.DIR_OUTPUT)
    exact = {
        "_concat.txt",
        "_audio_list.txt",
        "_main_audio.mp3",
        "_main_audio.wav",
        "_render_identity.json",
    }
    if output.is_dir():
        for path in output.iterdir():
            if path.is_file() and (
                path.name in exact
                or re.fullmatch(r"_chunk_[0-9]{5}\.mp4(?:\.identity\.json)?", path.name)
            ):
                candidates.append(path)
    for directory, pattern in (
        (config.DIR_SRT, r"(?:srt_[0-9]+\.json|timing_[0-9]+\.identity\.json)"),
        (config.DIR_SCENE, r"scene_[0-9]+\.(?:html|identity\.json)"),
    ):
        preserve = keep_srt if directory == config.DIR_SRT else keep_scene_html
        if not preserve and Path(directory).is_dir():
            candidates += [
                p
                for p in Path(directory).iterdir()
                if p.is_file() and re.fullmatch(pattern, p.name)
            ]
    removed = []
    failed = []
    if not dry_run:
        for path in candidates:
            try:
                path.unlink()
                removed.append(str(path))
            except OSError as error:
                failed.append({"path": str(path), "error": str(error)})
    result = {
        "dry_run": dry_run,
        "planned": [str(p) for p in candidates],
        "removed": removed,
        "failed": failed,
    }
    print(json.dumps(result, ensure_ascii=False))
    if failed:
        raise RuntimeError(
            f"cleanup incomplete: {len(failed)} generated files could not be removed"
        )
    return result


def _ffprobe(path):
    return json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-count_packets",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                path,
            ],
            timeout=120,
        ).stdout
    )


def _first_stream(probe, kind):
    return next(
        (s for s in probe.get("streams", []) if s.get("codec_type") == kind), None
    )


def _fps(stream):
    try:
        return float(
            Fraction(
                stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/1"
            )
        )
    except (ValueError, TypeError, ZeroDivisionError):
        return 0.0


def _duration(value):
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (ValueError, TypeError):
        return None


def _stream_duration(stream):
    result = _duration(stream.get("duration"))
    if result is None and stream.get("duration_ts") is not None:
        try:
            result = float(Fraction(stream["time_base"]) * int(stream["duration_ts"]))
        except (ValueError, TypeError, KeyError, ZeroDivisionError):
            return None
    return result


def _expected_codec():
    return {
        "av1_nvenc": "av1",
        "h264_nvenc": "h264",
        "hevc_nvenc": "hevc",
        "libx264": "h264",
        "libx265": "hevc",
    }.get(config.VCODEC, config.VCODEC)


def verify():
    from pipeline import contracts

    ok = True
    expected = None

    def report(passed, name, detail):
        nonlocal ok
        ok = ok and bool(passed)
        print(f"[verify] {'PASS' if passed else 'FAIL'} {name}: {detail}")

    title = str(config.PROJECT_TITLE).strip()
    report(
        bool(title and title != "Untitled Video"), "project-title", title or "missing"
    )
    for name, validator in (
        ("final-lineage", contracts.require_final),
        ("cover-lineage", contracts.require_cover),
        ("chapters-lineage", contracts.require_chapters),
    ):
        try:
            value = validator()
            if name == "final-lineage":
                expected = value
            report(True, name, "current inputs and output hashes match")
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
            report(False, name, str(error))
    final = Path(config.DIR_OUTPUT) / "final_output.mp4"
    try:
        probe = _ffprobe(str(final))
        video = _first_stream(probe, "video")
        audio = _first_stream(probe, "audio")
        report(video is not None, "video-stream", "present" if video else "missing")
        report(audio is not None, "audio-stream", "present" if audio else "missing")
        if video:
            dimensions = (int(video.get("width", 0)), int(video.get("height", 0)))
            report(
                dimensions == (config.WIDTH, config.HEIGHT),
                "video-size",
                str(dimensions),
            )
            report(abs(_fps(video) - config.FPS) < 0.001, "video-fps", str(_fps(video)))
            report(
                video.get("codec_name") == _expected_codec(),
                "video-codec",
                str(video.get("codec_name")),
            )
            frames = int(video.get("nb_read_packets") or video.get("nb_frames") or -1)
            report(
                expected is not None and frames == expected["expected_frames"],
                "video-frames",
                str(frames),
            )
        duration = _duration(probe.get("format", {}).get("duration"))
        report(duration is not None and duration > 0, "format-duration", str(duration))
        if expected and duration is not None:
            report(
                abs(duration - expected["expected_seconds"])
                <= max(0.08, 2 / config.FPS),
                "expected-duration",
                str(duration),
            )
        if video and audio:
            vd = _stream_duration(video)
            ad = _stream_duration(audio)
            report(
                vd is not None and ad is not None,
                "stream-durations",
                "known" if vd is not None and ad is not None else "unavailable",
            )
            if vd is not None and ad is not None:
                report(
                    abs(vd - ad) <= max(0.08, 2 / config.FPS),
                    "av-duration-delta",
                    f"{abs(vd - ad):.6f}s",
                )
                if expected:
                    report(
                        abs(vd - expected["expected_seconds"]) <= 1 / config.FPS,
                        "complete-video-duration",
                        f"{vd:.6f}s",
                    )
            starts = [_duration(s.get("start_time")) for s in (video, audio)]
            report(
                all(v is not None and v <= 0.05 for v in starts),
                "stream-start-times",
                str(starts),
            )
    except Exception as error:
        report(False, "final-probe", str(error))
    try:
        cover = _first_stream(
            _ffprobe(str(Path(config.DIR_OUTPUT) / "cover.png")), "video"
        )
        passed = (
            cover is not None
            and cover.get("codec_name") == "png"
            and (int(cover.get("width", 0)), int(cover.get("height", 0)))
            == (config.WIDTH, config.HEIGHT)
        )
        report(
            passed,
            "cover-format-size",
            "PNG at project dimensions" if passed else "invalid cover",
        )
    except Exception as error:
        report(False, "cover-probe", str(error))
    print("[verify] READY" if ok else "[verify] NOT READY")
    return ok


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    from pipeline.io_utils import project_lock

    if args.dry_run:
        cleanup(dry_run=True)
    else:
        with project_lock(config.ROOT):
            cleanup()
