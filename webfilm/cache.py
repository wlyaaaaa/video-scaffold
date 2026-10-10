"""Byte-verified two-second checkpoints for deterministic canvas encoding."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import time

from .common import probe, read_json, run, sha256, tool, write_json


def scene_ranges(config, files, fps, first, last):
    """Optional author-declared scene dependencies; undeclared files are global."""
    scenes = config.get("render_segments")
    if scenes is None:
        scenes = [{"start": 0, "end": config["duration"], "files": []}]
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("render_segments must be a nonempty complete scene list")
    known, assigned, parsed, cursor = {f["path"] for f in files}, set(), [], 0
    for scene in scenes:
        try:
            start, end, selected = scene["start"], scene["end"], scene["files"]
            if (any(type(t) not in (int, float) for t in (start, end)) or
                    any(not math.isfinite(t) or abs(t*fps-round(t*fps)) > 1e-7 for t in (start, end))):
                raise ValueError("Scene times must be finite frame boundaries")
            start, end = round(start*fps), round(end*fps)
            if start != cursor or end <= start or not isinstance(selected, list) or any(p not in known for p in selected):
                raise ValueError("Scene ranges must cover the work in order, with existing file dependencies")
            assigned.update(selected)
            parsed.append((start, end, set(selected)))
            cursor = end
        except (KeyError, TypeError) as error:
            raise ValueError("Invalid render_segments declaration") from error
    if cursor != round(config["duration"]*fps):
        raise ValueError("Scene ranges must cover the complete source duration")
    for start, end, selected in parsed:
        dependencies = [f for f in files if f["path"] not in assigned or f["path"] in selected]
        for at in range(max(first, start), min(last, end), fps*2):
            yield at, min(at+fps*2, end, last), dependencies


@contextmanager
def cache_lock(folder):
    folder.mkdir(parents=True, exist_ok=True)
    # OS-held lock disappears after a killed render; no stale PID lock files.
    with (folder / "render.lock").open("a+b") as handle:
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        if __import__("os").name == "nt":
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise RuntimeError("Another render owns this work's checkpoint cache") from error
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if __import__("os").name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def checkpoint(folder, first, last):
    video, record = folder / f"{first}-{last}.mp4", folder / f"{first}-{last}.json"
    try:
        saved = read_json(record)
        indices = saved.get("frame_indices", list(range(first, last)))
        if (saved.get("schema") != "webfilm.checkpoint.v1" or saved.get("range") != [first, last]
                or len(saved.get("frames", [])) != len(indices)
                or indices != sorted(set(indices)) or (indices and not first <= indices[0] <= indices[-1] < last)
                or not video.is_file()
                or saved.get("video_sha256") != sha256(video)):
            return None
        return video, saved
    except (OSError, ValueError, TypeError, KeyError):
        return None


def capture_segments(page, runtime, root, report, config, parent, temporary, output,
                     width, height, fps, first, last, *, verify_frames=False):
    from .webcodecs import capture_canvas, canvas_session
    engine_files = [Path(__file__).with_name(name) for name in
                    ("webcodecs.py", "webcodecs.js", "browser.py", "cache.py", "render.py")]
    engine = [sha256(path) for path in engine_files]
    key = {"root": str(root), "width": width, "height": height, "fps": fps,
           "config": config, "chrome": runtime["chrome"], "engine": engine, "verify_frames": verify_frames,
           "range": [first, last]}
    digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:24]
    folder = parent / ".webfilm-cache" / digest
    frames, frame_indices, segments, receipts = [], [], [], []
    samples = sorted({first, (first+last)//2, last-1})
    with cache_lock(folder), canvas_session(page):
        for start, end, dependencies in scene_ranges(config, report["files"], fps, first, last):
            if runtime.get("lease"):
                runtime["lease"].check()
            previous = checkpoint(folder, start, end)
            began = time.monotonic()
            video, record_path = folder / f"{start}-{end}.mp4", folder / f"{start}-{end}.json"
            same_source = bool(previous and previous[1].get("files") == report["files"])
            reused = bool(previous and (same_source or (not verify_frames and
                          previous[1].get("dependencies") == dependencies)))
            evidence = previous[1].get("evidence", {}) if previous else {}
            if reused:
                hashes = previous[1]["frames"]
                indices = previous[1]["frame_indices"]
            else:
                raw = temporary / f"{start}-{end}.h264"
                result = capture_canvas(page, runtime, raw, fps, start, end,
                                        verify_frames=verify_frames, keep_encoder=True,
                                        sample_frames=[i for i in samples if start <= i < end])
                hashes, evidence, reused = result["frames"], result["evidence"], result.get("reused", False)
                indices = result["frame_indices"]
                if len(hashes) != len(indices) or (verify_frames and len(hashes) != end-start):
                    raise RuntimeError("Canvas checkpoint has the wrong source hash count")
                from .check import check_work
                if check_work(root, max_duration=max(120, config["duration"]), config=config)["files"] != report["files"]:
                    raise RuntimeError("Work inputs changed during a checkpoint; refusing to cache mixed sources")
                if not reused:
                    staged = temporary / f"{start}-{end}.mp4"
                    color = evidence.get("decoder_color_space") or {}
                    if (color.get("matrix"), color.get("primaries"), color.get("transfer")) != ("bt709", "bt709", "iec61966-2-1"):
                        raise RuntimeError("Hardware encoder did not report the supported output color space")
                    tags = "h264_metadata=level=5.2:matrix_coefficients=1:colour_primaries=1:transfer_characteristics=13:video_full_range_flag=" + str(int(color["fullRange"]))
                    run([tool("ffmpeg"), "-v", "error", "-y", "-r", str(fps), "-f", "h264", "-i", raw,
                         "-map", "0:v:0", "-c:v", "copy", "-an", "-bsf:v",
                         tags + f",setts=pts=N/({fps}*TB):dts=N/({fps}*TB):duration=1/({fps}*TB)", staged])
                    stream = next(v for v in probe(staged)["streams"] if v["codec_type"] == "video")
                    if (int(stream.get("nb_frames", -1)) != end-start or stream["width"] != width
                            or stream["height"] != height or stream.get("has_b_frames") != 0
                            or abs(float(stream["duration"])-(end-start)/fps) > 1e-7):
                        raise RuntimeError("Encoded checkpoint dimensions/frame count failed verification")
                    staged.replace(video)
                saved = {"schema": "webfilm.checkpoint.v1", "range": [start, end], "frames": hashes,
                         "frame_indices": indices,
                         "video_sha256": sha256(video), "files": report["files"], "evidence": evidence,
                         "timing": result["timing"], "dependencies": dependencies,
                         "produced_from": previous[1].get("produced_from", previous[1]["files"]) if reused else report["files"]}
                staged_record = temporary / f"{start}-{end}.json"
                write_json(staged_record, saved)
                staged_record.replace(record_path)
            frames.extend(hashes)
            frame_indices.extend(indices)
            segments.append(video)
            saved = previous[1] if previous and reused and same_source else read_json(record_path)
            receipts.append({"range": [start, end], "reused": reused, "dependencies": dependencies,
                             "produced_from": saved.get("produced_from", saved["files"]),
                             "video_sha256": saved["video_sha256"], "evidence": evidence,
                             "reuse_basis": "same source bytes" if same_source else "author scene dependencies" if reused else None,
                             "seconds": round(time.monotonic()-began, 3), "timing": saved.get("timing", {})})
            print(f"webfilm checkpoint {start}/{end} reused={reused} elapsed={receipts[-1]['seconds']}s", flush=True)
            if runtime.get("lease"):
                runtime["lease"].check()
        # Keep paths relative: concat's format must not reinterpret quotes in a parent path.
        listing = folder / "concat.txt"
        listing.write_text("".join(f"file '{v.name}'\n" for v in segments), encoding="utf-8")
        run([tool("ffmpeg"), "-v", "error", "-y", "-f", "concat", "-safe", "1", "-i", listing,
             "-map", "0:v:0", "-c:v", "copy", "-an", output])
        if engine != [sha256(path) for path in engine_files]:
            raise RuntimeError("Renderer code changed during capture; refusing mixed engine provenance")
    return frames, {"backend": "WebCodecs Canvas", "cache": str(folder), "segments": receipts,
                    "frame_indices": frame_indices, "pixel_verification": "all frames" if verify_frames else "sampled"}
