# -*- coding: utf-8 -*-
"""
Central, declarative configuration for the video scaffold.

Everything that the AI or a human might tweak per-project lives here so the
pipeline modules stay generic. Read this file first to understand a project.

Universal (committed) parts:
    config.py / pipeline/ / templates/ / docs/ / run_demo.py
    background/     the seamless 4K loop + its shader/generator (reused by all videos)
    examples/       placeholder art for the demo

Per-project workspace (generated, git-ignored, created on demand):
    assets/        game art / images, named freely and referenced by scenes
    scripts/       script_01.txt .. script_NN.txt  (one paragraph per scene)
    raw_audio/     audio_01.mp3 .. audio_NN.mp3     (TTS output)
    srt_data/      srt_01.json .. srt_NN.json       (whisper word timing)
    scene_html/    scene_01.html .. scene_NN.html   (built from the base board)
    rendered/      per-scene overlay video (optional intermediate)
    output/        final_output.mp4, cover.png, chapters.txt
"""

import os

ROOT = os.path.dirname(os.path.abspath(__file__))


def _p(*parts):
    return os.path.join(ROOT, *parts)


# --- canvas -----------------------------------------------------------------
WIDTH = 3840
HEIGHT = 2160
FPS = 60

# --- background -------------------------------------------------------------
# Universal seamless-loop clip (regenerate with background/render_background.py).
# The renderer loops it to cover any duration.
BG_VIDEO = _p("background", "background_4k.mp4")

# --- encode (RTX 5080 hardware AV1) -----------------------------------------
# Chunks ARE the final quality (concat is stream-copy), so invest here.
# p6 + spatial/temporal AQ + lookahead = near-transparent 4K at a small size.
VCODEC = "av1_nvenc"
CQ = "22"                 # constant quality; lower = better/bigger (18-24 sane)
NVENC_EXTRA = ["-preset", "p6", "-tune", "hq", "-rc", "constqp",
               "-spatial-aq", "1", "-temporal-aq", "1", "-rc-lookahead", "32",
               "-pix_fmt", "yuv420p10le"]
NUM_WORKERS = 8           # 9950X3D physical cores for the render pool
CHUNK_FRAMES = 300        # max frames per ffmpeg chunk (5 s @ 60fps); the
                          # renderer shrinks this so short videos still use all cores

# --- design system (the global visual contract) -----------------------------
# Dark celadon text on transparent foreground; no cards/borders/shadows.
INK = "#0C2B1B"           # 深黛绿 primary text
ACCENT = "#1F7A4D"        # 流光浅绿 accent for lines / arrows
FADE_SECONDS = 0.5        # per-scene fade in / out

# --- Fish Audio TTS ---------------------------------------------------------
# SECURITY: the key is read from env var FISH_API_KEY, or secret_local.py
# (git-ignored). Never hard-code it here - this file is committed to GitHub.
FISH_API_KEY = os.getenv("FISH_API_KEY", "")
try:
    from secret_local import FISH_API_KEY as _LOCAL_KEY  # git-ignored file
    FISH_API_KEY = _LOCAL_KEY or FISH_API_KEY
except Exception:
    pass

FISH_ENDPOINT = "https://api.fish.audio/v1/tts"
# 央视配音 (CCTV male voice). The free model `s2.1-pro-free` accepts this
# reference_id with NO API credit required - verified working.
FISH_MODEL = "s2.1-pro-free"
FISH_REFERENCE_ID = "59cb5986671546eaa6ca8ae6f29f6d22"
FISH_FORMAT = "mp3"

# Fish inline markup the AI may sprinkle into scripts for delivery/SFX.
# Emotion tones wrap the phrase that should carry the emotion; SFX/pauses are
# inserted at the point they occur. See docs/VOICE.md.
FISH_EMOTION_TAGS = ["angry", "sad", "embarrassed", "emphasis", "whispering",
                     "soft", "breathy", "excited"]
FISH_SFX_TAGS = ["laughing", "chuckling", "moaning", "clear throat", "sobbing",
                 "crying loudly", "sighing", "panting", "groaning",
                 "crowd laughing", "background laughter", "audience laughing",
                 "pause", "long pause"]

# --- faster-whisper (best local quality, max GPU/CPU utilisation) -----------
WHISPER_MODEL = "large-v3"   # best accuracy
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE = "float16"  # 5080 has the VRAM; keeps quality high
WHISPER_LANGUAGE = "zh"
WHISPER_BATCH_SIZE = 16      # BatchedInferencePipeline throughput on the 5080
WHISPER_CPU_THREADS = 16     # 9950X3D feeds the GPU (feature extraction / VAD)

# --- chapters (Bilibili) ----------------------------------------------------
# Bilibili reads "MM:SS Title" / "HH:MM:SS Title" lines; first MUST be 00:00.
# Keep titles short; ~3-10 chapters is ideal (warn past this).
CHAPTER_MAX = 12

# --- directories ------------------------------------------------------------
DIR_ASSETS = _p("assets")
DIR_SCRIPTS = _p("scripts")
DIR_AUDIO = _p("raw_audio")
DIR_SRT = _p("srt_data")
DIR_SCENE = _p("scene_html")
DIR_RENDERED = _p("rendered")
DIR_OUTPUT = _p("output")
DURATIONS_JSON = _p("durations.json")
TEMPLATE_BASE = _p("templates", "scene_base.html")
TEMPLATE_COVER = _p("templates", "cover_base.html")


def ensure_dirs():
    for d in (DIR_ASSETS, DIR_SCRIPTS, DIR_AUDIO, DIR_SRT,
              DIR_SCENE, DIR_RENDERED, DIR_OUTPUT):
        os.makedirs(d, exist_ok=True)
