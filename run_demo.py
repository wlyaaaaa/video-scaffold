# -*- coding: utf-8 -*-
"""
End-to-end DEMO of the scaffold (deliberately small) - now with frame-perfect
narration sync via the Whisper word-timeline.

Chain exercised:
  TTS (央视 voice, free model) -> ffprobe durations -> faster-whisper word
  timeline -> build scenes from the base board (data-cue resolved to exact word
  times) -> render onto the LOOPING 4K background -> mux audio -> final_output.mp4

Watch scene 2: each stat bar grows on the exact frame the narrator names it.
"""

import os
import sys
import shutil
import pathlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from pipeline import (fish_tts, durations as dur_mod, transcribe, build_scene,
                      render, merge, chapters, cover, cleanup, components as C)


def file_uri(path):
    return pathlib.Path(os.path.abspath(path)).as_uri()


# Scripts deliberately SPEAK the phrases we cue animations to, and use Fish
# inline tags (see docs/VOICE.md) for delivery. Tags are parsed, not spoken.
DEMO_SCRIPTS = [
    "传说级武器，正式解禁！[excited] 今天，带你拆解这件硬核装备的核心部件。",
    "先看阻抗强度，接着是展开兼容，最后是续航能力。[emphasis] 三项核心数据，全面拉满。",
]

HERO = file_uri(os.path.join(config.DIR_ASSETS, "weapon_01.png"))


def scene1_fragment():
    # built from reusable components (see pipeline/components.py)
    return (
        C.title_block("传说级武器解禁", kicker="LEGENDARY  GEAR  REVEAL",
                      x=280, y=520, cue="传说级武器")
        + C.hero(HERO, x=2500, y=560, w=980, h=1400, cue="硬核装备")
        + C.pointer(1820, 980, 2440, 1060, "核心部件", cue="核心部件")
    )


def scene2_fragment():
    return (
        C.title_block("核心数据全面解析", x=300, y=440, cue="核心数据", size=150)
        + C.stat_panel([
            ("阻抗强度 / Disruption", "9.5", 0.95, "阻抗强度"),
            ("展开兼容 / Combo", "8.0", 0.80, "展开兼容"),
            ("续航能力 / Loop", "9.0", 0.90, "续航能力"),
        ], x=330, y=900)
        + C.hero(HERO, x=2650, y=520, w=820, h=1170, cue="续航能力")
    )


def _ensure_demo_hero():
    """Self-contained demo: seed a copyright-free placeholder hero if assets/ is
    empty (e.g. a fresh git clone, since assets/ is git-ignored)."""
    dst = os.path.join(config.DIR_ASSETS, "weapon_01.png")
    if not os.path.exists(dst):
        shutil.copy(os.path.join(config.ROOT, "examples", "sample_hero.png"), dst)


def main():
    config.ensure_dirs()
    _ensure_demo_hero()

    # stage 1: scripts -> TTS (央视 voice via free model)
    for i, text in enumerate(DEMO_SCRIPTS, 1):
        with open(os.path.join(config.DIR_SCRIPTS, f"script_{i:02d}.txt"), "w", encoding="utf-8") as f:
            f.write(text)
    audios = fish_tts.synth_batch()  # uses config 央视 voice
    if len(audios) != len(DEMO_SCRIPTS):
        print("[demo] TTS did not produce all clips; aborting.")
        sys.exit(1)

    # stage 2: exact durations + word-level timeline
    durs = dur_mod.build()
    transcribe.transcribe_batch()

    # stage 4a: build scenes, resolving data-cue against each scene's word timeline
    scenes = []
    for i, frag in enumerate([scene1_fragment(), scene2_fragment()], 1):
        srt = os.path.join(config.DIR_SRT, f"srt_{i:02d}.json")
        scenes.append(build_scene.build(frag, os.path.join(config.DIR_SCENE, f"scene_{i:02d}.html"), srt=srt))

    # stage 4b + 5: render onto looping background, then mux audio
    video_track = render.render_timeline(scenes, durs)
    audio = merge.concat_audio()
    final = merge.mux(video_track, audio)

    # stage 6: cover + Bilibili chapters + ready check
    cover.build("极客配装", subtitle="RTX 5080 硬核攻略", kicker="HARDCORE GUIDE")
    chapters.write(chapters.from_scene_groups(durs, [(0, "传说级武器解禁"), (1, "核心数据解析")]))
    cleanup.verify()
    print(f"\n[demo] DONE -> {final}")


if __name__ == "__main__":
    main()
