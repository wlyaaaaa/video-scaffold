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
                      render, merge, chapters, cover, cleanup)


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
    return f"""
  <g transform="translate(280,520)">
    <text data-anim="type" data-cue="传说级武器" data-dur="1.4"
          font-family="'Source Han Serif CN','Georgia',serif" font-size="200"
          font-weight="bold" fill="{config.INK}" letter-spacing="6">传说级武器解禁</text>
    <text data-anim="fade-up" data-delay="0.6" data-dur="1.0"
          x="6" y="160" font-family="-apple-system,sans-serif" font-size="64"
          fill="{config.INK}" opacity="0" letter-spacing="10">LEGENDARY  GEAR  REVEAL</text>
    <line data-anim="draw" data-delay="0.4" data-dur="1.2"
          x1="6" y1="230" x2="1500" y2="230" stroke="url(#accent-grad)" stroke-width="10"/>
  </g>

  <g transform="translate(2500,560)">
    <g data-anim="float" data-cue="硬核装备" data-dur="1.4">
      <image href="{HERO}" xlink:href="{HERO}" width="980" height="1400"/>
    </g>
  </g>

  <line data-anim="draw" data-cue="核心部件" data-dur="0.9" fill="none"
        x1="1820" y1="980" x2="2440" y2="1060" stroke="{config.ACCENT}"
        stroke-width="7" marker-end="url(#arrow)"/>
  <text data-anim="fade" data-cue="核心部件" data-dur="0.6"
        x="1500" y="975" font-family="-apple-system,sans-serif" font-size="46"
        fill="{config.INK}" opacity="0" text-anchor="end">核心部件</text>
"""


def _bar(y, label, value, frac, cue):
    full = 1500 * frac
    return f"""
    <g transform="translate(0,{y})">
      <text data-anim="fade-up" data-cue="{cue}" data-dur="0.6" x="0" y="0"
            font-family="-apple-system,sans-serif" font-size="56" fill="{config.INK}" opacity="0">{label}</text>
      <line x1="0" y1="40" x2="1500" y2="40" stroke="{config.INK}" stroke-width="10"
            stroke-linecap="round" opacity="0.12"/>
      <line data-anim="draw" data-cue="{cue}" data-dur="1.0" x1="0" y1="40" x2="{full:.0f}" y2="40"
            stroke="url(#accent-grad)" stroke-width="10" stroke-linecap="round"/>
      <text data-anim="count" data-to="{value}" data-decimals="1" data-cue="{cue}" data-dur="1.0"
            x="1500" y="0" font-family="-apple-system,sans-serif" font-size="56" font-weight="bold"
            fill="{config.ACCENT}" text-anchor="end" opacity="0">0.0</text>
    </g>"""


def scene2_fragment():
    bars = _bar(0, "阻抗强度 / Disruption", "9.5", 0.95, "阻抗强度") \
         + _bar(220, "展开兼容 / Combo", "8.0", 0.80, "展开兼容") \
         + _bar(440, "续航能力 / Loop", "9.0", 0.90, "续航能力")
    return f"""
  <g transform="translate(300,440)">
    <text data-anim="type" data-cue="核心数据" data-dur="1.2"
          font-family="'Source Han Serif CN','Georgia',serif" font-size="150"
          font-weight="bold" fill="{config.INK}">核心数据全面解析</text>
    <line data-anim="draw" data-delay="0.4" data-dur="1.0" x1="6" y1="80" x2="1100" y2="80"
          stroke="url(#accent-grad)" stroke-width="8"/>
  </g>
  <g transform="translate(330,900)">{bars}</g>

  <g transform="translate(2650,520)">
    <g data-anim="float" data-delay="0.6" data-dur="1.6">
      <image href="{HERO}" xlink:href="{HERO}" width="820" height="1170" opacity="0.96"/>
    </g>
  </g>
"""


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
