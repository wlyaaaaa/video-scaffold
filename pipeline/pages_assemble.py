"""Join approved clips with frame-aligned pauses, video fades and grouped chapters."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile

from pipeline import render_queue
from pipeline.artifact_identity import sha256_file

FPS, PAUSE, FADE_FRAMES = 60, 0.45, 12


def _run(args, **kwargs):
    options = {"check": True, "timeout": 300, "encoding": "utf-8", "errors": "replace"}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(args, **{**options, **kwargs})


def probe(path, *, count=False):
    return json.loads(_run(["ffprobe", "-v", "error", *(["-count_frames"] if count else []),
                           "-show_format", "-show_streams", "-of", "json", str(path)],
                          capture_output=True).stdout)


def _stream(info, kind):
    return next((s for s in info["streams"] if s["codec_type"] == kind), None)


def speech_end(path, duration):
    result = _run(["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-threads", "1",
                   "-i", str(path), "-map", "0:a:0", "-vn", "-af",
                   "silencedetect=n=-38dB:d=0.12", "-f", "null", "-"], capture_output=True)
    starts = [float(v) for v in re.findall(r"silence_start: ([\d.]+)", result.stderr)]
    ends = [float(v) for v in re.findall(r"silence_end: ([\d.]+)", result.stderr)]
    if starts and (len(ends) < len(starts) or ends[-1] >= duration - 0.05):
        return starts[-1]
    return duration


def _resolve(base, value):
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def plan(manifest):
    manifest = Path(manifest).resolve()
    spec = json.loads(manifest.read_text(encoding="utf-8"))
    source = spec.get("parts", [])
    if not source:
        raise ValueError("assembly needs at least one part")
    ids = [p.get("id") for p in source]
    if any(not isinstance(v, str) or not v.strip() for v in ids) or len(set(ids)) != len(ids):
        raise ValueError("part ids must be nonempty and unique")
    chapters = spec.get("chapters", [])
    limit = spec.get("max_title_chars")
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("max_title_chars must be a positive integer")
    positions = []
    for chapter in chapters:
        title, part = chapter.get("title"), chapter.get("from")
        if not isinstance(title, str) or not title.strip() or (limit and len(title) > limit):
            raise ValueError("chapter title is empty or exceeds max_title_chars")
        if part not in ids:
            raise ValueError("chapter refers to an unknown part")
        positions.append(ids.index(part))
    if not positions or positions[0] != 0 or positions != sorted(set(positions)):
        raise ValueError("chapters must start at the first part and advance uniquely")
    parts, total, size = [], 0, None
    for index, item in enumerate(source):
        path = _resolve(manifest.parent, item["path"])
        if not path.is_file():
            raise FileNotFoundError(path)
        source_bytes, source_sha256 = path.stat().st_size, sha256_file(path)
        info = probe(path)
        video, audio = _stream(info, "video"), _stream(info, "audio")
        if not video or not audio:
            raise ValueError(f"part needs video and audio: {path}")
        current_size = (video["width"], video["height"])
        if size and current_size != size:
            raise ValueError("all parts must have the same video dimensions")
        size = current_size
        duration = float(info["format"]["duration"])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError(f"invalid source duration: {path}")
        end = speech_end(path, duration)
        cut = duration if index == len(source) - 1 else min(duration, end + PAUSE)
        frames = round(cut * FPS)
        if frames < 1 or (len(source) > 1 and frames < FADE_FRAMES):
            raise ValueError("a part is too short for the selected transition")
        parts.append({"id": item["id"], "path": str(path), "source_duration": duration,
                      "source_bytes": source_bytes, "source_sha256": source_sha256,
                      "video_duration": float(video.get("duration", duration)), "speech_end": end,
                      "frames": frames, "start_frame": total})
        total += frames
    chapter_rows = [{**chapter, "frame": parts[pos]["start_frame"],
                     "seconds": parts[pos]["start_frame"] / FPS}
                    for chapter, pos in zip(chapters, positions)]
    if len({int(row["seconds"]) for row in chapter_rows}) != len(chapter_rows):
        raise ValueError("chapter timestamps must remain distinct after rounding down to seconds")
    return {"schema": "video-scaffold.pages-assembly.v1", "manifest": str(manifest),
            "fps": FPS, "pause_seconds": PAUSE, "fade_frames": FADE_FRAMES,
            "parts": parts, "chapters": chapter_rows, "total_frames": total,
            "duration": total / FPS, "size": list(size),
            "out": str(_resolve(manifest.parent, spec["out"])) if spec.get("out") else None,
            "chapter_basis": spec.get("chapter_basis", "拼接表指定"),
            "source_statement": spec.get("source_statement", "复用拼接表指定片段")}


def command(result, output):
    inputs, filters = [], []
    parts = result["parts"]
    for index, part in enumerate(parts):
        inputs += ["-threads", "1", "-i", part["path"]]
        frames = part["frames"] + (FADE_FRAMES if index < len(parts) - 1 else 0)
        padding = max(0, frames / FPS - part["video_duration"]) + 1 / FPS
        filters.append(f"[{index}:v]setpts=PTS-STARTPTS,fps={FPS},settb=1/{FPS},"
                       f"format=yuv420p,tpad=stop_mode=clone:stop_duration={padding:.9f},"
                       f"trim=end_frame={frames},setpts=PTS-STARTPTS[v{index}]")
        samples = part["frames"] * (48000 // FPS)
        filters.append(f"[{index}:a]asetpts=PTS-STARTPTS,aresample=48000,"
                       f"aformat=sample_fmts=fltp:channel_layouts=stereo,apad=whole_len={samples},"
                       f"atrim=end_sample={samples},asetpts=PTS-STARTPTS[a{index}]")
    video, offset = "v0", 0
    for index in range(1, len(parts)):
        offset += parts[index - 1]["frames"]
        target = f"x{index}"
        filters.append(f"[{video}][v{index}]xfade=transition=fade:duration={FADE_FRAMES / FPS:.9f}:"
                       f"offset={offset / FPS:.9f}[{target}]")
        video = target
    filters.append("".join(f"[a{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[aout]")
    return ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-n", *inputs,
            "-filter_complex_threads", "1", "-filter_complex", ";".join(filters),
            "-map", f"[{video}]", "-map", "[aout]", "-c:v", "libx264", "-threads", "4",
            "-preset", "medium", "-crf", "18", "-profile:v", "high", "-level:v", "4.2",
            "-pix_fmt", "yuv420p", "-fps_mode", "cfr", "-r", str(FPS),
            "-frames:v", str(result["total_frames"]), "-t", f"{result['duration']:.9f}",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart",
            "-stats_period", "10", "-progress", "pipe:1", str(output)]


def verify(info, result):
    video, audio = _stream(info, "video"), _stream(info, "audio")
    if not video or not audio or "mp4" not in info["format"]["format_name"]:
        raise ValueError("assembled output must be MP4 with video and audio")
    frames = int(video.get("nb_read_frames", video.get("nb_frames", -1)))
    errors = {name: abs(float(value["duration"]) - result["duration"]) * FPS
              for name, value in (("format", info["format"]), ("video", video), ("audio", audio))}
    if frames != result["total_frames"] or any(error >= 1 for error in errors.values()):
        raise ValueError(f"assembly timing mismatch: frames={frames}; duration errors={errors}")
    if (video["codec_name"] != "h264" or audio["codec_name"] != "aac"
            or video["pix_fmt"] != "yuv420p" or video["r_frame_rate"] != "60/1"
            or [video["width"], video["height"]] != result["size"]):
        raise ValueError("assembled stream format differs from the planned format")
    return {"actual_frames": frames, "expected_frames": result["total_frames"],
            "duration_error_frames": errors}


def assemble(manifest):
    with render_queue.lease(f"assemble {Path(manifest).resolve()}"):
        result = plan(manifest)
        if not result["out"]:
            raise ValueError("assembly requires an explicit out path")
        out = Path(result["out"])
        if out.suffix.lower() != ".mp4":
            raise ValueError("assembly output must have the .mp4 extension")
        targets = [out, out.with_suffix(".chapters.txt"), out.with_suffix(".assembly.json")]
        if any(path.exists() for path in targets):
            raise FileExistsError("assembly output or matching receipt already exists")
        out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".{out.stem}-", dir=out.parent) as directory:
            staged = [Path(directory) / path.name for path in targets]
            args = command(result, staged[0])
            _run(args, timeout=7200)
            actual = probe(staged[0], count=True)
            if any(sha256_file(part["path"]) != part["source_sha256"] for part in result["parts"]):
                raise ValueError("a source clip changed during assembly")
            result.update(final_probe=actual, verification=verify(actual, result),
                          output_bytes=staged[0].stat().st_size, output_sha256=sha256_file(staged[0]),
                          chapters_path=str(targets[1]), receipt_path=str(targets[2]), ffmpeg_command=args)
            lines = []
            for chapter in result["chapters"]:
                seconds = int(chapter["seconds"])
                lines.append(f"{seconds // 60:02d}:{seconds % 60:02d} {chapter['title']}")
            staged[1].write_text("\n".join(lines) + "\n", encoding="utf-8")
            staged[2].write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            published = []
            try:
                for source, target in zip(staged, targets):
                    os.link(source, target)  # Fails if a concurrent writer created this target.
                    published.append(target)
            except BaseException:
                for target in published:
                    target.unlink()
                raise
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args(argv)
    result = plan(args.manifest) if args.plan else assemble(args.manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
