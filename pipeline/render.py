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
import asyncio
import subprocess
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
        timeline.append({
            "html": os.path.abspath(html),
            "start": acc,
            "end": acc + d,
            "fade_in_end": acc + min(config.FADE_SECONDS, d / 2),
            "fade_out_start": acc + d - min(config.FADE_SECONDS, d / 2),
        })
        acc += d
    return timeline, acc


def _scene_at(timeline, t):
    for s in timeline:
        if s["start"] <= t < s["end"]:
            return s
    return timeline[-1]


def _opacity_at(scene, t):
    fi0, fi1 = scene["start"], scene["fade_in_end"]
    fo0, fo1 = scene["fade_out_start"], scene["end"]
    if t < fi1 and fi1 > fi0:
        return max(0.0, (t - fi0) / (fi1 - fi0))
    if t >= fo0 and fo1 > fo0:
        return max(0.0, 1.0 - (t - fo0) / (fo1 - fo0))
    return 1.0


async def _worker_loop(task_queue, counter, lock, t0, timeline, total_frames, bg_dur, chunk_frames):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True, channel="chrome",
                                              args=["--force-gpu-rasterization", "--enable-zero-copy"])
        except Exception:
            browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": config.WIDTH, "height": config.HEIGHT})

        pages = {}
        for s in timeline:
            if s["html"] not in pages:
                page = await ctx.new_page()
                await page.goto(f"file://{s['html']}")
                pages[s["html"]] = page

        while True:
            try:
                chunk_idx = task_queue.get_nowait()
            except queue.Empty:
                break

            start_idx = chunk_idx * chunk_frames
            end_idx = min(start_idx + chunk_frames, total_frames)
            frames = list(range(start_idx, end_idx))
            if not frames:
                continue

            chunk_start_t = frames[0] / float(config.FPS)
            chunk_dur = len(frames) / float(config.FPS)
            bg_offset = chunk_start_t % bg_dur          # <-- loop the background
            chunk_out = os.path.join(config.DIR_OUTPUT, f"_chunk_{chunk_idx:05d}.mp4")

            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-stream_loop", "-1", "-ss", f"{bg_offset:.3f}", "-t", f"{chunk_dur:.3f}",
                "-i", config.BG_VIDEO,
                "-f", "image2pipe", "-vcodec", "png", "-r", str(config.FPS), "-i", "-",
                "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=1",
                "-c:v", config.VCODEC, *config.NVENC_EXTRA, "-cq", config.CQ,
                "-an", "-threads", "2", chunk_out,
            ]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                for idx in frames:
                    t = idx / float(config.FPS)
                    scene = _scene_at(timeline, t)
                    t_local = t - scene["start"]
                    page = pages[scene["html"]]
                    op = _opacity_at(scene, t)
                    await page.evaluate(
                        f"if(window.seekTime) window.seekTime({t_local}); document.body.style.opacity={op};")
                    png = await page.screenshot(type="png", omit_background=True)
                    proc.stdin.write(png)
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
                proc.wait(timeout=60)
            except Exception as e:
                try: proc.kill()
                except Exception: pass
                print(f"\n  [worker] chunk {chunk_idx} failed: {e}")
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

    # lossless concat of chunks
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
