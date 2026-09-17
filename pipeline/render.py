# -*- coding: utf-8 -*-
"""
Stage 4b - GPU frame-grab compositor.

Drives each scene HTML through window.seekTime(t), screenshots every frame with
a transparent background, and overlays it onto the 4K background. The background
is LOOPED (stream_loop -1 + modulo seek) so it covers any total duration - this
is the fix for "set 15 min, only 1 min of background" where the 60 s clip used
to run out and leave blank frames.

Architecture (verified on a modern multi-core CPU + NVIDIA RTX GPU):
  * a fixed pool of headless Chromium workers, each keeps its pages warm;
  * the global frame range is sliced into CHUNK_FRAMES tasks on a queue;
  * each task pipes PNG frames into one ffmpeg (av1_nvenc) overlay process;
  * chunks are concatenated losslessly at the end.

Public entry:
  render_timeline(scene_html_paths, durations) -> output/video_track.mp4
"""

import os
import sys
import time
import queue
import base64
import asyncio
import glob
import re
import subprocess
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname
from collections import OrderedDict
from multiprocessing import Process, Value, Lock, Queue

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.artifact_identity import (
    read_record,
    sha256_file,
    write_record,
    output_record_matches,
    write_output_record,
)
from pipeline.io_utils import (
    atomic_output,
    encoder_process,
    positive,
    run as run_process,
)
from pathlib import Path

VIDEO_TRACK = os.path.join(config.DIR_OUTPUT, "video_track.mp4")
RENDER_IDENTITY = "_render_identity.json"
FILE_URI = re.compile(r"""file:///[^\s"'<>)]*""", re.IGNORECASE)


def _scene_file_resources(scene_html_paths):
    from pipeline.resources import inventory

    return inventory(scene_html_paths)


def _render_identity_record(scene_html_paths, durations, chunk_frames, total_frames):
    return {
        "schema": "video-scaffold.render-resume-identity.v1",
        "scenes": [
            {
                "name": os.path.basename(path),
                "sha256": sha256_file(path),
                "duration_seconds": float(duration),
            }
            for path, duration in zip(scene_html_paths, durations)
        ],
        "file_resources": _scene_file_resources(scene_html_paths),
        "background_sha256": sha256_file(config.BG_VIDEO),
        "canvas": {"width": config.WIDTH, "height": config.HEIGHT, "fps": config.FPS},
        "frames": {
            "total": total_frames,
            "chunk": chunk_frames,
            "chunks": (total_frames + chunk_frames - 1) // chunk_frames,
        },
        "transition": {
            "type": config.TRANSITION,
            "seconds": config.TRANSITION_SECONDS,
            "shift": config.TRANSITION_SHIFT,
        },
        "finishing": {
            "cinematic": config.CINEMATIC,
            "vignette_angle": config.VIGNETTE_ANGLE,
            "grain": config.GRAIN,
        },
        "encoder": {
            "codec": config.VCODEC,
            "cq": config.CQ,
            "extra": list(config.NVENC_EXTRA),
        },
        "screenshot_fast": config.SCREENSHOT_FAST,
        "renderer_sha256": sha256_file(__file__),
    }


def _prepare_resume(identity, output_dir=None, *, preserve_verified=False):
    output_dir = output_dir or config.DIR_OUTPUT
    identity_path = os.path.join(output_dir, RENDER_IDENTITY)
    previous = read_record(identity_path)
    chunks = glob.glob(os.path.join(output_dir, "_chunk_*.mp4"))
    stale = []
    if previous != identity:
        stale = [
            path
            for path in chunks
            if not preserve_verified or not read_record(path + ".identity.json")
        ]
        for path in stale:
            try:
                os.remove(path)
            except OSError:
                pass
        remaining = [path for path in stale if os.path.exists(path)]
        if remaining:
            raise RuntimeError(
                "render inputs changed but stale resume chunks could not be removed: "
                + ", ".join(remaining)
            )
        for path in stale:
            Path(path + ".identity.json").unlink(missing_ok=True)
        write_record(identity_path, identity)
    if stale:
        print(f"[render] discarded {len(stale)} unbound resume chunks")
    return bool(stale)


def _chunk_identity(identity, timeline, index, chunk_frames, total_frames, bg_duration):
    start = index * chunk_frames / config.FPS
    end = min((index + 1) * chunk_frames, total_frames) / config.FPS
    positions = [
        i
        for i, scene in enumerate(timeline)
        if scene["start"] < end and scene["end"] > start
    ]
    record = {
        key: value
        for key, value in identity.items()
        if key not in ("scenes", "file_resources", "frames")
    }
    record["schema"] = "video-scaffold.render-chunk.v1"
    record["range"] = {
        "index": index,
        "start_frame": index * chunk_frames,
        "frames": round((end - start) * config.FPS),
        "background_offset": start % bg_duration,
    }
    record["scenes"] = [
        {**identity["scenes"][i], "start": timeline[i]["start"]} for i in positions
    ]
    record["file_resources"] = _scene_file_resources(
        [timeline[i]["html"] for i in positions]
    )
    return record


def _bg_duration():
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            config.BG_VIDEO,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=True,
    )
    return float(out.stdout.strip())


def _chunk_nframes(path):
    """Coded frame count of a chunk - fast (counts packets, no decode).

    This is the guard that keeps audio and video in lock-step. A chunk that
    encoded FEWER frames than it was fed (NVENC session pressure under many
    workers makes ffmpeg exit 0 yet drop frames) used to slip past the old
    `size > 0` check; once concatenated, every later frame slid earlier than its
    narration -> the "3:47 音画不同步" drift. We now reject any chunk whose frame
    count != expected. Returns -1 on probe failure so an error is treated as a
    bad chunk, never a silent pass."""
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-count_packets",
                "-show_entries",
                "stream=nb_read_packets",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=True,
        )
        return int(out.stdout.strip())
    except Exception:
        return -1


def build_timeline(scene_html_paths, durations):
    """[{html, start, end, fade_in_end, fade_out_start}] in global seconds."""
    if not scene_html_paths or len(scene_html_paths) != len(durations):
        raise ValueError("scene/duration count mismatch or empty timeline")
    durations = [positive(value, "scene duration") for value in durations]
    timeline, acc = [], 0.0
    for html, d in zip(scene_html_paths, durations):
        timeline.append({"html": os.path.abspath(html), "start": acc, "end": acc + d})
        acc += d
    return timeline, acc


def _scene_at(timeline, t):
    for s in timeline:
        if s["start"] <= t < s["end"]:
            return s
    return timeline[-1]


def _envelope_at(scene, t):
    """Scene transition: returns (opacity, css_transform) for the body.
    Each scene eases in at its start and out at its end; adjacent scenes meet at
    the boundary so the effect is a cross-dissolve (plus motion) through the
    background. Timing is unchanged, so audio / data-cue sync is preserved."""
    tr = min(config.TRANSITION_SECONDS, (scene["end"] - scene["start"]) / 2)
    ein = max(0.0, min(1.0, (t - scene["start"]) / tr)) if tr > 0 else 1.0
    eout = max(0.0, min(1.0, (scene["end"] - t) / tr)) if tr > 0 else 1.0
    op = min(ein, eout)
    s = config.TRANSITION_SHIFT
    typ = config.TRANSITION
    if typ == "rise":
        return op, f"translateY({(1 - ein) * s - (1 - eout) * s:.1f}px)"
    if typ == "slide-left":
        return op, f"translateX({(1 - ein) * s - (1 - eout) * s:.1f}px)"
    if typ == "slide-right":
        return op, f"translateX({-(1 - ein) * s + (1 - eout) * s:.1f}px)"
    if typ == "zoom":
        return op, f"scale({0.97 + 0.03 * ein:.3f})"
    return op, ""  # "fade"


def _chunk_cmd(bg_offset, chunk_dur, chunk_out):
    vfilter = f"[0:v]trim=start={bg_offset:.3f},setpts=PTS-STARTPTS[bg]; [bg][1:v]overlay=0:0:shortest=1"
    if config.CINEMATIC:
        if config.VIGNETTE_ANGLE > 0:
            vfilter += f",vignette=angle={config.VIGNETTE_ANGLE}"
        if config.GRAIN > 0:
            vfilter += f",noise=alls={config.GRAIN}:allf=t"
    return [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-stream_loop",
        "-1",
        "-i",
        config.BG_VIDEO,
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "-r",
        str(config.FPS),
        "-i",
        "-",
        "-filter_complex",
        vfilter,
        "-c:v",
        config.VCODEC,
        *config.NVENC_EXTRA,
        ("-cq" if config.VCODEC.endswith("_nvenc") else "-crf"),
        config.CQ,
        "-an",
        "-threads",
        "2",
        chunk_out,
    ]


async def _worker_loop(
    task_queue,
    counter,
    lock,
    t0,
    timeline,
    total_frames,
    bg_dur,
    chunk_frames,
    completed_frames=0,
    chunk_records=None,
):
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=True,
                channel="chrome",
                args=[
                    "--force-gpu-rasterization",
                    "--enable-zero-copy",
                    "--disable-gpu-vsync",
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--mute-audio",
                ],
            )
        except Exception:
            browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": config.WIDTH, "height": config.HEIGHT}
        )

        # LRU of warm pages: cap memory at MAX_PAGES per worker instead of one
        # page per scene (the all-scenes preload was the OOM driver).
        cache = OrderedDict()  # html -> {"page", "cdp"}

        async def get_entry(html):
            if html in cache:
                cache.move_to_end(html)
                return cache[html]
            page = await ctx.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.goto(Path(html).resolve().as_uri(), wait_until="load")
            from pipeline.browser_runtime import ready

            await ready(page)
            if errors:
                raise RuntimeError("scene JavaScript error: " + errors[0])
            cdp = None
            if config.SCREENSHOT_FAST:
                try:  # transparent bg so CDP captureScreenshot keeps alpha
                    cdp = await ctx.new_cdp_session(page)
                    await cdp.send(
                        "Emulation.setDefaultBackgroundColorOverride",
                        {"color": {"r": 0, "g": 0, "b": 0, "a": 0}},
                    )
                except Exception:
                    cdp = None
            cache[html] = {"page": page, "cdp": cdp, "errors": errors}
            cache.move_to_end(html)
            while len(cache) > max(1, config.MAX_PAGES_PER_WORKER):
                _, old = cache.popitem(last=False)
                try:
                    await old["page"].close()
                except Exception:
                    pass
            return cache[html]

        async def grab(entry):
            if entry["cdp"] is not None:
                try:  # optimizeForSpeed: lighter PNG -> faster encode AND decode
                    r = await entry["cdp"].send(
                        "Page.captureScreenshot",
                        {
                            "format": "png",
                            "optimizeForSpeed": True,
                            "captureBeyondViewport": False,
                        },
                    )
                    return base64.b64decode(r["data"])
                except Exception:
                    entry["cdp"] = None
            return await entry["page"].screenshot(type="png", omit_background=True)

        async def render_chunk(chunk_idx):
            start_idx = chunk_idx * chunk_frames
            end_idx = min(start_idx + chunk_frames, total_frames)
            expected_frames = end_idx - start_idx
            if expected_frames <= 0:
                return True
            bg_offset = (start_idx / config.FPS) % bg_dur
            chunk_out = os.path.join(config.DIR_OUTPUT, f"_chunk_{chunk_idx:05d}.mp4")
            written = 0
            accepted = False
            try:
                with atomic_output(chunk_out) as staged:
                    with encoder_process(
                        _chunk_cmd(bg_offset, expected_frames / config.FPS, staged),
                        config.PROCESS_TIMEOUT_SECONDS,
                    ) as (proc, errors):
                        for idx in range(start_idx, end_idx):
                            t = idx / config.FPS
                            scene = _scene_at(timeline, t)
                            entry = await get_entry(scene["html"])
                            op, transform = _envelope_at(scene, t)
                            await entry["page"].evaluate(
                                """([t,opacity,transform]) => {
                              window.seekTime(t); document.body.style.opacity=opacity;
                              document.body.style.transform=transform;
                            }""",
                                [t - scene["start"], op, transform],
                            )
                            if entry["errors"]:
                                raise RuntimeError(
                                    "scene runtime error: " + entry["errors"][0]
                                )
                            proc.stdin.write(await grab(entry))
                            proc.stdin.flush()
                            written += 1
                            with counter.get_lock():
                                counter.value += 1
                        proc.stdin.close()
                        rc = proc.wait(timeout=config.PROCESS_TIMEOUT_SECONDS)
                        errors.seek(0)
                        message = errors.read()[-3000:].decode(
                            "utf-8", errors="replace"
                        )
                        if rc != 0:
                            raise RuntimeError(f"encoder failed ({rc}): {message}")
                    if _chunk_nframes(staged) != expected_frames:
                        raise RuntimeError("encoder dropped frames")
                if chunk_records is not None:
                    write_output_record(
                        chunk_out + ".identity.json",
                        chunk_records[chunk_idx],
                        chunk_out,
                    )
                accepted = True
                with lock:
                    print(
                        f"[render] chunk {chunk_idx + 1} accepted ({expected_frames} frames)",
                        flush=True,
                    )
                return True
            finally:
                if not accepted:
                    with counter.get_lock():
                        counter.value -= written

        while True:
            try:
                chunk_idx = task_queue.get(timeout=2)
            except queue.Empty:
                break
            for attempt in range(config.CHUNK_RETRIES + 1):
                try:
                    if await render_chunk(chunk_idx):
                        break
                except Exception as e:
                    print(
                        f"\n  [worker] chunk {chunk_idx} attempt {attempt + 1} error: {e}"
                    )
                if attempt < config.CHUNK_RETRIES:
                    await asyncio.sleep(1.0)  # let transient NVENC pressure clear

        for entry in cache.values():
            try:
                await entry["page"].close()
            except Exception:
                pass
        await browser.close()


def _worker_entry(
    task_queue,
    counter,
    lock,
    t0,
    timeline,
    total_frames,
    bg_dur,
    chunk_frames,
    completed_frames=0,
    chunk_records=None,
):
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(
        _worker_loop(
            task_queue,
            counter,
            lock,
            t0,
            timeline,
            total_frames,
            bg_dur,
            chunk_frames,
            completed_frames,
            chunk_records,
        )
    )


def _render_timeline(
    scene_html_paths, durations, out_path=VIDEO_TRACK, num_workers=None, lease=None
):
    config.ensure_dirs()
    if not os.path.exists(config.BG_VIDEO):
        raise FileNotFoundError(f"background not found: {config.BG_VIDEO}")

    num_workers = config.NUM_WORKERS if num_workers is None else num_workers
    if type(num_workers) is not int or num_workers < 1:
        raise ValueError("num_workers must be a positive integer")
    bg_dur = positive(_bg_duration(), "background duration")
    timeline, total_seconds = build_timeline(scene_html_paths, durations)
    total_frames = int(round(total_seconds * config.FPS))
    if total_frames < 1:
        raise ValueError("timeline is shorter than one frame")

    # Shrink the chunk so EVERY worker gets work even on short videos
    # (a 13s clip was making only 3 of 8 cores busy). Long videos keep 300.
    import math

    chunk_frames = max(
        1, min(config.CHUNK_FRAMES, math.ceil(total_frames / num_workers))
    )
    total_chunks = (total_frames + chunk_frames - 1) // chunk_frames
    identity = _render_identity_record(
        scene_html_paths, durations, chunk_frames, total_frames
    )
    _prepare_resume(identity, preserve_verified=True)
    chunk_records = [
        _chunk_identity(identity, timeline, i, chunk_frames, total_frames, bg_dur)
        for i in range(total_chunks)
    ]

    def _expected(i):
        start_idx = i * chunk_frames
        return min(start_idx + chunk_frames, total_frames) - start_idx

    def _bad(i):
        path = os.path.join(config.DIR_OUTPUT, f"_chunk_{i:05d}.mp4")
        if (not os.path.exists(path)) or os.path.getsize(path) == 0:
            return True
        return not output_record_matches(
            path + ".identity.json", chunk_records[i], path
        ) or _chunk_nframes(path) != _expected(i)

    # 1. Identify which chunks are bad and must be re-rendered (Smart Resuming)
    bad_chunks = []
    for i in range(total_chunks):
        if _bad(i):
            bad_chunks.append(i)
            # Remove bad/partial chunk file so the retry/render rewrites cleanly
            path = os.path.join(config.DIR_OUTPUT, f"_chunk_{i:05d}.mp4")
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass

    # 2. Delete any orphaned chunk files from a previous run with a larger total_chunks
    existing_chunks = glob.glob(os.path.join(config.DIR_OUTPUT, "_chunk_*.mp4"))
    for f in existing_chunks:
        try:
            bn = os.path.basename(f)
            idx = int(bn.split("_")[2].split(".")[0])
            if idx >= total_chunks:
                os.remove(f)
                Path(f + ".identity.json").unlink(missing_ok=True)
        except Exception:
            pass

    # 3. Clean up generic concatenation helper lists
    for f in [
        os.path.join(config.DIR_OUTPUT, "_concat.txt"),
        os.path.join(config.DIR_OUTPUT, "_audio_list.txt"),
    ]:
        try:
            if os.path.exists(f):
                os.remove(f)
        except OSError:
            pass

    # 4. Calculate completed frames in already rendered valid chunks
    completed_frames = sum(
        _expected(i) for i in range(total_chunks) if i not in bad_chunks
    )

    # Output resuming status
    if completed_frames > 0:
        print(
            f"[render] Smart Resuming: found {total_chunks - len(bad_chunks)}/{total_chunks} valid chunks already rendered."
        )
        print(
            f"[render] Re-rendering {len(bad_chunks)} missing/bad chunks. Completed frames: {completed_frames}/{total_frames} ({100.0 * completed_frames / total_frames:.1f}%)"
        )
    else:
        print(f"[render] Starting fresh render of all {total_chunks} chunks.")

    print(
        f"[render] {len(timeline)} scenes, {total_seconds:.2f}s, "
        f"{total_frames} frames, {total_chunks} chunks x {chunk_frames}f, {num_workers} workers"
    )

    t0 = time.time()
    counter, lock = Value("i", 0), Lock()
    task_queue = Queue()
    for i in bad_chunks:
        task_queue.put(i)

    procs = []
    # Only spawn workers if there are chunks to render
    for _ in range(min(num_workers, len(bad_chunks))):
        p = Process(
            target=_worker_entry,
            args=(
                task_queue,
                counter,
                lock,
                t0,
                timeline,
                total_frames,
                bg_dur,
                chunk_frames,
                completed_frames,
                chunk_records,
            ),
        )
        p.start()
        procs.append(p)
    deadline = time.monotonic() + config.WORKER_TIMEOUT_SECONDS * max(
        1, len(bad_chunks)
    )
    try:
        while any(process.is_alive() for process in procs):
            if lease:
                lease.check()
            if time.monotonic() > deadline:
                raise TimeoutError("render workers exceeded their bounded deadline")
            for process in procs:
                process.join(timeout=0.2)
        failed = [process.exitcode for process in procs if process.exitcode != 0]
        if failed:
            raise RuntimeError(f"render worker failure: {failed}")
    finally:
        for process in procs:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            if process.is_alive():
                process.kill()
                process.join(timeout=5)
            process.close()
        task_queue.cancel_join_thread()
        task_queue.close()

    # lossless concat of chunks (robust: never silently truncate OR drift)
    missing = [i for i in range(total_chunks) if _bad(i)]
    if missing:
        raise RuntimeError(
            f"[render] {len(missing)}/{total_chunks} chunks missing/empty/short "
            f"(first few: {missing[:8]}); aborting rather than producing a gappy or "
            f"out-of-sync video. If this rises with more workers it is the NVENC session "
            f"cap dropping frames - lower NUM_WORKERS."
        )
    concat_list = os.path.join(config.DIR_OUTPUT, "_concat.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for i in range(total_chunks):
            f.write(f"file '_chunk_{i:05d}.mp4'\n")
    with atomic_output(out_path) as staged:
        run_process(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_list,
                "-c",
                "copy",
                staged,
            ],
            timeout=180,
        )
        got = _chunk_nframes(staged)
        if got != total_frames:
            raise RuntimeError(
                f"stitched track has {got} frames, expected {total_frames}"
            )
    os.remove(concat_list)
    # Verified chunks remain reusable; explicit cleanup removes this bounded cache.
    print(f"\n[render] done in {time.time() - t0:.1f}s -> {out_path}")
    return out_path


def render_timeline(
    scene_html_paths, durations, out_path=VIDEO_TRACK, num_workers=None
):
    from pipeline.gpu import gpu_lease

    with gpu_lease(config.VCODEC.endswith("_nvenc")) as lease:
        return _render_timeline(
            scene_html_paths, durations, out_path, num_workers, lease
        )
