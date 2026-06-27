# -*- coding: utf-8 -*-
"""
Stage 4b - GPU frame-grab compositor.

Drives each scene HTML through window.seekTime(t), screenshots every frame with
a transparent background, and overlays it onto the 4K background. The background
is LOOPED (stream_loop -1 + modulo seek) so it covers any total duration - this
is the fix for "set 15 min, only 1 min of background" where the 60 s clip used
to run out and leave blank frames.

Architecture (proven on 9950X3D x RTX 5080):
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
import subprocess
from collections import OrderedDict
from multiprocessing import Process, Value, Lock, Queue

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

VIDEO_TRACK = os.path.join(config.DIR_OUTPUT, "video_track.mp4")


def _bg_duration():
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", config.BG_VIDEO],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def build_timeline(scene_html_paths, durations):
    """[{html, start, end, fade_in_end, fade_out_start}] in global seconds."""
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
    return op, ""   # "fade"


def _chunk_cmd(bg_offset, chunk_dur, chunk_out):
    vfilter = "[0:v][1:v]overlay=0:0:shortest=1"
    if config.CINEMATIC:
        if config.VIGNETTE_ANGLE > 0:
            vfilter += f",vignette=angle={config.VIGNETTE_ANGLE}"
        if config.GRAIN > 0:
            vfilter += f",noise=alls={config.GRAIN}:allf=t"
    return [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-stream_loop", "-1", "-ss", f"{bg_offset:.3f}", "-t", f"{chunk_dur:.3f}",
        "-i", config.BG_VIDEO,
        "-f", "image2pipe", "-vcodec", "png", "-r", str(config.FPS), "-i", "-",
        "-filter_complex", vfilter,
        "-c:v", config.VCODEC, *config.NVENC_EXTRA, "-cq", config.CQ,
        "-an", "-threads", "2", chunk_out,
    ]


async def _worker_loop(task_queue, counter, lock, t0, timeline, total_frames, bg_dur, chunk_frames):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True, channel="chrome",
                                              args=["--force-gpu-rasterization", "--enable-zero-copy"])
        except Exception:
            browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": config.WIDTH, "height": config.HEIGHT})

        # LRU of warm pages: cap memory at MAX_PAGES per worker instead of one
        # page per scene (the all-scenes preload was the OOM driver).
        cache = OrderedDict()   # html -> {"page", "cdp"}

        async def get_entry(html):
            if html in cache:
                cache.move_to_end(html)
                return cache[html]
            page = await ctx.new_page()
            await page.goto(f"file://{html}")
            cdp = None
            if config.SCREENSHOT_FAST:
                try:    # transparent bg so CDP captureScreenshot keeps alpha
                    cdp = await ctx.new_cdp_session(page)
                    await cdp.send("Emulation.setDefaultBackgroundColorOverride",
                                   {"color": {"r": 0, "g": 0, "b": 0, "a": 0}})
                except Exception:
                    cdp = None
            cache[html] = {"page": page, "cdp": cdp}
            cache.move_to_end(html)
            while len(cache) > max(1, config.MAX_PAGES_PER_WORKER):
                _, old = cache.popitem(last=False)
                try: await old["page"].close()
                except Exception: pass
            return cache[html]

        async def grab(entry):
            if entry["cdp"] is not None:
                try:   # optimizeForSpeed: lighter PNG -> faster encode AND decode
                    r = await entry["cdp"].send("Page.captureScreenshot",
                                                {"format": "png", "optimizeForSpeed": True,
                                                 "captureBeyondViewport": False})
                    return base64.b64decode(r["data"])
                except Exception:
                    entry["cdp"] = None
            return await entry["page"].screenshot(type="png", omit_background=True)

        async def render_chunk(chunk_idx):
            start_idx = chunk_idx * chunk_frames
            end_idx = min(start_idx + chunk_frames, total_frames)
            frames = list(range(start_idx, end_idx))
            if not frames:
                return True
            chunk_dur = len(frames) / float(config.FPS)
            bg_offset = (frames[0] / float(config.FPS)) % bg_dur   # loop the background
            chunk_out = os.path.join(config.DIR_OUTPUT, f"_chunk_{chunk_idx:05d}.mp4")

            proc = subprocess.Popen(_chunk_cmd(bg_offset, chunk_dur, chunk_out),
                                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE)
            for idx in frames:
                t = idx / float(config.FPS)
                scene = _scene_at(timeline, t)
                entry = await get_entry(scene["html"])
                op, tf = _envelope_at(scene, t)
                await entry["page"].evaluate(
                    f"if(window.seekTime) window.seekTime({t - scene['start']});"
                    f"document.body.style.opacity={op};"
                    f"document.body.style.transform='{tf}';")
                proc.stdin.write(await grab(entry))
                proc.stdin.flush()
                with counter.get_lock():
                    counter.value += 1
                    c = counter.value
                if c % 30 == 0:
                    with lock:
                        el = time.time() - t0
                        print(f"\r  render {c}/{total_frames} "
                              f"({100*c/total_frames:5.1f}%)  {c/el:5.1f} fps", end="", flush=True)
            proc.stdin.close()
            rc = proc.wait(timeout=600)   # NVENC contention under many workers needs headroom
            ok = (rc == 0 and os.path.exists(chunk_out) and os.path.getsize(chunk_out) > 0)
            if not ok:
                with counter.get_lock():    # rewind the progress for the retry
                    counter.value -= len(frames)
            return ok

        while True:
            try:
                chunk_idx = task_queue.get_nowait()
            except queue.Empty:
                break
            for attempt in range(config.CHUNK_RETRIES + 1):
                try:
                    if await render_chunk(chunk_idx):
                        break
                except Exception as e:
                    print(f"\n  [worker] chunk {chunk_idx} attempt {attempt+1} error: {e}")
                if attempt < config.CHUNK_RETRIES:
                    await asyncio.sleep(1.0)   # let transient NVENC pressure clear

        for entry in cache.values():
            try: await entry["page"].close()
            except Exception: pass
        await browser.close()


def _worker_entry(task_queue, counter, lock, t0, timeline, total_frames, bg_dur, chunk_frames):
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(_worker_loop(task_queue, counter, lock, t0, timeline, total_frames, bg_dur, chunk_frames))


def render_timeline(scene_html_paths, durations, out_path=VIDEO_TRACK, num_workers=None):
    config.ensure_dirs()
    if not os.path.exists(config.BG_VIDEO):
        raise FileNotFoundError(f"background not found: {config.BG_VIDEO}")

    num_workers = num_workers or config.NUM_WORKERS
    bg_dur = _bg_duration()
    timeline, total_seconds = build_timeline(scene_html_paths, durations)
    total_frames = int(round(total_seconds * config.FPS))

    # Shrink the chunk so EVERY worker gets work even on short videos
    # (a 13s clip was making only 3 of 8 cores busy). Long videos keep 300.
    import math
    chunk_frames = max(1, min(config.CHUNK_FRAMES, math.ceil(total_frames / num_workers)))
    total_chunks = (total_frames + chunk_frames - 1) // chunk_frames

    print(f"[render] {len(timeline)} scenes, {total_seconds:.2f}s, "
          f"{total_frames} frames, {total_chunks} chunks x {chunk_frames}f, {num_workers} workers")

    t0 = time.time()
    counter, lock = Value("i", 0), Lock()
    task_queue = Queue()
    for i in range(total_chunks):
        task_queue.put(i)

    procs = []
    for _ in range(min(num_workers, total_chunks)):
        p = Process(target=_worker_entry,
                    args=(task_queue, counter, lock, t0, timeline, total_frames, bg_dur, chunk_frames))
        p.start()
        procs.append(p)
    for p in procs:
        p.join()

    # lossless concat of chunks (robust: never silently truncate at a bad chunk)
    def _bad(i):
        path = os.path.join(config.DIR_OUTPUT, f"_chunk_{i:05d}.mp4")
        return (not os.path.exists(path)) or os.path.getsize(path) == 0
    missing = [i for i in range(total_chunks) if _bad(i)]
    if missing:
        raise RuntimeError(
            f"[render] {len(missing)}/{total_chunks} chunks missing or empty "
            f"(first few: {missing[:8]}); aborting rather than producing a gappy/truncated "
            f"video. If this rises with more workers it is likely the NVENC session cap - "
            f"lower NUM_WORKERS.")
    concat_list = os.path.join(config.DIR_OUTPUT, "_concat.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for i in range(total_chunks):
            f.write(f"file '_chunk_{i:05d}.mp4'\n")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", concat_list,
                    "-c", "copy", out_path], check=True)

    os.remove(concat_list)
    for i in range(total_chunks):
        try: os.remove(os.path.join(config.DIR_OUTPUT, f"_chunk_{i:05d}.mp4"))
        except OSError: pass

    print(f"\n[render] done in {time.time()-t0:.1f}s -> {out_path}")
    return out_path
