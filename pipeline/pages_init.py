"""在空目录开工；测试音仅用于验证流程，不是生产配音。"""
from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path


def test_audio(path, texts, seconds=4):
    words, lines = [], []
    for i, title in enumerate(texts):
        tokens = [(title, 0), ("开始", .3), ("继续", 1), ("完成", 2), ("收尾", 3)]
        lines.append("".join(t for t, _ in tokens))
        words.extend(dict(word=t, start=i * seconds + at, end=i * seconds + at + .25) for t, at in tokens)
    duration = len(texts) * seconds - .6
    rate = 24000
    with wave.open(str(path), "wb") as wav:
        wav.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        wav.writeframes(b"".join(struct.pack("<h", int(1200 * math.sin(2 * math.pi * 440 * i / rate)
                              * max(0, 1 - (i / rate % 1) * 8))) for i in range(round(rate * duration))))
    path.with_suffix(".original.txt").write_text("\n".join(lines), encoding="utf-8")
    Path(str(path) + ".timestamps.json").write_text(json.dumps(
        {"source": "synthetic-test-tone", "words": words}, ensure_ascii=False, indent=1), encoding="utf-8")


def initialize(target, *, atlas=False, render=False):
    from PIL import Image, ImageDraw
    target = Path(target).resolve()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ValueError(f"开工目录必须为空：{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    templates = Path(__file__).resolve().parents[1] / "templates" / "pages"
    name = "atlas" if atlas else "intro"
    with tempfile.TemporaryDirectory(prefix=".pages-init-", dir=target.parent) as tmp:
        stage = Path(tmp)
        for directory in ("pages", "art", "narration", "assets", "_samples/checkpoint"):
            (stage / directory).mkdir(parents=True, exist_ok=True)
        spec = json.loads((templates / f"{name}.json").read_text(encoding="utf-8"))
        titles = [p["from"] for p in spec["pages"]]
        test_audio(stage / "narration" / f"{name}.wav", titles, 4 if atlas else 6)
        (stage / "pages" / f"{name}.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
        image = Image.new("RGB", (320, 180), "white")
        draw = ImageDraw.Draw(image)
        for i, width in enumerate((100, 160, 250)):
            draw.rectangle((24, 25 + i * 48, 24 + width, 49 + i * 48), fill="#10A27E")
        image.save(stage / "assets" / "sample.png")
        (stage / "assets" / "example.svg").write_text(
            '<rect data-anim="grow-bar" data-grow="x" data-delay="0" data-dur="0.6" '
            'x="1000" y="800" width="1800" height="180" rx="30" fill="#10A27E"/>', encoding="utf-8")
        shutil.copyfile(templates / "README.md", stage / "README.md")
        if atlas:
            readme = stage / "README.md"
            readme.write_text(readme.read_text(encoding="utf-8").replace("intro", "atlas")
                              .replace("6 秒流程试片", f"{len(titles)} 页版式一览"), encoding="utf-8")
        if target.exists():
            target.rmdir()  # 已确认空目录，不覆盖任何已有工程
        stage.rename(target)
    path = target / "pages" / f"{name}.json"
    if render:
        from pipeline.pages import Project
        out = Project(path).render()
        if atlas:
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-vf",
                            "fps=1,scale=384:216,tile=8x8", "-fps_mode", "vfr",
                            str(target / "_samples" / "atlas-contacts-%02d.png")], check=True)
    return path
