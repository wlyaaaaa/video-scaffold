# -*- coding: utf-8 -*-
"""图文页：分镜表（JSON）→ 页面 → 有声、带字幕的可播放片子。

一张表管一段片子：用哪几段配音（可只取其中几句）、主题、每一页放什么、每个元素绑哪个词。
元素按念到的词一拍进来、进来就停住；页与页之间硬切。坐标不用手写：左栏文字自上而下排，
右栏放照片卡、抠图和气泡；个别元素可写 x/y 覆盖。写法见 docs/AUTHORING.md“图文页”。

    python -m pipeline.pages <表.json> plan            # 每页起止时间、各元素绑到的时刻
    python -m pipeline.pages <表.json> stills [秒 ...]  # 无头抽帧（默认每页最后一刻）
    python -m pipeline.pages <表.json> render          # 出片：4K 画面轨 → 1080p 可播放副本

绑词写原文里的字（显示的写法，如“846 亿”），不用写读法；同一页里第二次出现写“词#2”，
错开写“词+0.2”/“词-0.1”。不写 at 的元素在页面一开始就在。
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

PAGE_LEAD = 0.25     # 页面比它的第一个词早这么多秒切进来
MIN_PAGE = 0.6


# ---- 表和时间轴 ----------------------------------------------------------------------------
@dataclass
class Narration:
    audio: Path
    cut_start: float      # 在原音频里从哪秒取
    cut_end: float
    offset: float         # 放在成片的哪一秒
    text: str             # 显示的原文（这一部分）
    text_start: int       # 这一部分在全片原文里的起点
    words: list = field(default_factory=list)   # 成片时间


@dataclass
class Timeline:
    parts: list
    text: str             # 全片原文（各部分以换行相接）
    words: list           # 全片词，成片时间
    spans: list           # 原文每个字 → (首词, 末词) | None
    duration: float

    def char_time(self, pos):
        span = self.spans[pos]
        return self.words[span[0]]["start"] if span else None


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _resolve(base, p):
    p = Path(p)
    return p if p.is_absolute() else (base / p).resolve()


def _probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def load_timeline(spec, base):
    from pipeline.subtitles import align_text

    parts, texts, words, offset = [], [], [], 0.0
    text_pos = 0
    for item in spec["narration"]:
        audio = _resolve(base, item["audio"])
        raw = _read_json(_resolve(base, item.get("words", str(audio) + ".timestamps.json")))
        seg_words = raw["words"] if isinstance(raw, dict) else raw
        text_file = _resolve(base, item.get("text_file", str(audio).rsplit(".", 1)[0] + ".original.txt"))
        full = Path(text_file).read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
        take = item.get("take", full)
        at = full.find(take)
        if at < 0:
            raise ValueError(f"take text not found in {audio.name}: {take[:20]}…")
        spans = align_text(full, seg_words)
        used = [s for s in spans[at:at + len(take)] if s]
        if not used:
            raise ValueError(f"no spoken words for take in {audio.name}")
        w0, w1 = used[0][0], used[-1][1]
        dur = _probe_duration(audio)
        cut_start = 0.0 if w0 == 0 else (seg_words[w0 - 1]["end"] + seg_words[w0]["start"]) / 2
        cut_end = dur if w1 == len(seg_words) - 1 else (seg_words[w1]["end"] + seg_words[w1 + 1]["start"]) / 2
        cut_end = float(item.get("pad_end", 0.0)) + cut_end
        local = [dict(word=w["word"], start=round(w["start"] - cut_start + offset, 3),
                      end=round(w["end"] - cut_start + offset, 3)) for w in seg_words[w0:w1 + 1]]
        parts.append(Narration(audio, cut_start, cut_end, offset, take, text_pos, local))
        texts.append(take)
        words += local
        text_pos += len(take) + 1
        offset += cut_end - cut_start
    text = "\n".join(texts)
    duration = offset + float(spec.get("tail", 0.6))
    return Timeline(parts, text, words, align_text(text, words), duration)


_CUE = re.compile(r"^(?P<word>.+?)(?:#(?P<n>\d+))?(?P<off>[+-]\d+(?:\.\d+)?)?$")


def cue_time(tl, cue, after):
    """“词”“词#2”“词+0.2” → 成片秒数；从原文位置 after 往后找。返回 (秒, 原文位置)。"""
    m = _CUE.match(cue.strip())
    if not m:
        raise ValueError(f"bad cue {cue!r}")
    word, n, off = m.group("word"), int(m.group("n") or 1), float(m.group("off") or 0)
    pos = after - 1
    for _ in range(n):
        pos = tl.text.find(word, pos + 1)
        if pos < 0:
            raise ValueError(f"cue {cue!r} not found after “{tl.text[max(0, after - 6):after + 6]}”")
    t = next((tl.char_time(p) for p in range(pos, pos + len(word)) if tl.char_time(p) is not None), None)
    if t is None:
        raise ValueError(f"cue {cue!r} is never spoken")
    return t + off, pos


# ---- 标记文字 ----------------------------------------------------------------------------------
def markup(s):
    """*重点* → 强调色，~旧说法~ → 灰色；返回 [(文字, 角色|None)]。"""
    out = []
    for part in re.split(r"(\*[^*]+\*|~[^~]+~)", s):
        if not part:
            continue
        if part[0] == "*" and part[-1] == "*":
            out.append((part[1:-1], "accent"))
        elif part[0] == "~" and part[-1] == "~":
            out.append((part[1:-1], "muted"))
        else:
            out.append((part, None))
    return out


def wrap(spans, size, width):
    """按估算字宽把分段文字折成几行（不拆英文单词和数字）。"""
    import v2lib as L
    tokens = []
    for text, role in spans:
        tokens += [(tok, role) for tok in re.findall(r"[A-Za-z0-9.+\-_%/]+|\s+|.", text)]
    lines, cur, w = [], [], 0.0
    for tok, role in tokens:
        tw = L._text_w(tok, size)
        if cur and w + tw > width and not tok.isspace() and tok not in "，。；：！？、,.;:!?）)》”":
            lines.append(cur); cur, w = [], 0.0
        if not cur and tok.isspace():
            continue
        if cur and cur[-1][1] == role:
            cur[-1] = (cur[-1][0] + tok, role)
        else:
            cur.append((tok, role))
        w += tw
    if cur:
        lines.append(cur)
    return lines


# ---- 一页 → SVG 片段 ---------------------------------------------------------------------------
SIZES = {"kicker": 52, "title": 220, "big": 150, "text": 96, "old": 120, "note": 96}
CONTENT_BOTTOM = 1840   # 往下留给字幕和进度条


class PageBuilder:
    def __init__(self, tl, page, start, start_pos, base, progress=None):
        import v2lib as L
        self.L, self.tl, self.page, self.start, self.base = L, tl, page, start, base
        self.pos = start_pos
        th = L.theme()
        self.th = th
        media = any(k in el for el in page["elements"] for k in ("photo", "cutout", "bubble", "card"))
        self.left = th["margin"]
        self.width = (1760 if media else config.WIDTH - 2 * th["margin"])
        self.y = th["top"]
        self.out = []          # 左栏（排完后整体竖向居中）
        self.mout = []         # 右栏媒体
        self.marks = []      # (元素, 本页秒数)
        self.progress = progress
        self.media = {}

    def at(self, cue, default=0.0):
        if not cue:
            return default
        t, pos = cue_time(self.tl, cue, self.pos)
        return max(0.0, t - self.start)

    def text_block(self, s, size, delay, *, font="heavy", weight=900, fill=None, anim="fade", gap=0.32, x=None):
        L = self.L
        x = self.left if x is None else x
        lines = wrap(markup(s), size, self.width - (x - self.left))
        for line in lines:
            self.y += size
            self.out.append(L.page_text(line, x, self.y, size, delay=delay, dur=1 / 12, anim=anim, font=font,
                                        weight=weight, fill=fill, shift=20 if anim == "fade-up" else None))
            self.y += size * 0.22
        self.y += size * gap

    def element(self, el):
        L, th = self.L, self.th
        d = self.at(el.get("at"))
        if "y" in el:
            self.y = el["y"]
        if "gap" in el and len(el) == 1:
            self.y += el["gap"]; return
        if "kicker" in el:
            self.text_block(el["kicker"], el.get("size", SIZES["kicker"]), d, font="mono", weight=700,
                            fill="muted", gap=0.9)
        elif "title" in el:
            self.text_block(el["title"], el.get("size", SIZES["title"]), d, anim="fade-up", gap=0.25)
        elif "big" in el:
            self.text_block(el["big"], el.get("size", SIZES["big"]), d, anim="fade-up", gap=0.35)
        elif "text" in el:
            self.text_block(el["text"], el.get("size", SIZES["text"]), d, font="sans", weight=500,
                            fill=el.get("fill"), gap=0.5)
        elif "note" in el:   # 等宽小标签 + 一行粗体（新闻条、来源条）
            if el.get("label"):
                self.y += 46
                self.out.append(L.page_text(el["label"], self.left, self.y, 46, delay=d, dur=1 / 12, anim="fade",
                                            fill="muted", font="mono", weight=700, ls=4))
                self.y += 30
            self.text_block(el["note"], el.get("size", SIZES["note"]), d, font="sans", weight=700, gap=1.0)
        elif "old" in el:
            size = el.get("size", SIZES["old"]); self.y += size
            strike = self.at(el.get("strike"), None) if el.get("strike") else None
            self.out.append(L.old_text(el["old"], self.left, self.y, size, delay=d,
                                       strike_delay=strike if strike is not None else None))
            self.y += size * 0.6
        elif "bullets" in el:
            size = el.get("size", 96); gap = int(size * 1.55)
            items = [(markup(t), self.at(c, d) if c else d) for t, c in el["bullets"]]
            self.out.append(L.bullets(items, x=self.left, y=self.y + size, size=size, gap=gap))
            self.y += size + gap * len(items)
        elif "numbers" in el:
            size = el.get("size", 84); self.y += size
            labels = [f"{i + 1:02d}" for i in range(int(el["numbers"]))]
            self.out.append(L.number_row(labels, self.left, self.y, gap=int(size * 2.4), size=size, delay=d))
            if "mark" in el:
                i = int(el["mark"]) - 1
                self.out.append(L.mark_label(labels[i], self.left + i * int(size * 2.4), self.y, size=size,
                                             delay=self.at(el.get("mark_at"), d)))
            self.y += size * 0.9
        elif "figures" in el:
            size = el.get("size", 200); x = self.left; top = self.y + size * 1.25
            for f in el["figures"]:
                fd = self.at(f.get("at"), d)
                self.out.append(L.figure(f["value"], x, top, size=size, label=f.get("label"), unit=f.get("unit"),
                                         delay=fd, fill="accent" if f.get("accent") else None))
                x += L._text_w(f["value"], size) + (L._text_w(f.get("unit", ""), size * 0.36)) + size * 0.8
            self.y = top + size * 0.45
        elif "bars" in el:
            vmax = max(float(b["value"]) for b in el["bars"]); w = el.get("width", self.width - 700)
            for b in el["bars"]:
                self.y += 110
                self.out.append(L.hbar(b["label"], b.get("text", b["value"]), float(b["value"]) / vmax, self.left,
                                       self.y, w=w, delay=self.at(b.get("at"), d),
                                       fill="accent" if b.get("accent") else None))
                self.y += 56 + 70
        elif "meter" in el:
            self.y += 60
            steps = [self.at(c) for c in el.get("steps", [])]
            if el.get("label"):
                self.out.append(L.page_text(el["label"], self.left, self.y - 70, 40, delay=d, dur=1 / 12,
                                            anim="fade", fill="muted", font="mono", weight=700, ls=4))
            self.out.append(L.meter(int(el["meter"]), self.left, self.y, timings=steps, cell=60, gap=16,
                                    fill="accent", delay=d))
            self.y += 60
        elif "quote" in el:
            size = el.get("size", 76)
            self.out.append(L.quote_block(el["quote"], x=self.left, y=self.y + size, size=size,
                                          source=el.get("source"), delay=d))
            self.y += size * 1.5 * (len(el["quote"]) + 1)
        elif "tag" in el:
            self.out.append(L.tag(el["tag"], el.get("x", self.left), self.y, delay=d,
                                  filled=el.get("filled", False)))
            self.y += 110
        elif "photo" in el:
            p = str(_resolve(self.base, el["photo"]))
            w = el.get("w", 1180); h = el.get("h")
            cx, cy = el.get("cx", 2780), el.get("cy", 940)
            self.mout.append(L.photo_card(p, cx, cy, w, h=h, delay=d, align=el.get("align", "xMidYMid")))
            iw, ih = L.img_dims(p)
            self.media["photo"] = (cx, cy, w, h or w * ih / iw)
        elif "cutout" in el:
            p = str(_resolve(self.base, el["cutout"]))
            h = el.get("h", 1520); x, y = el.get("x", 2690), el.get("y", 940)
            self.mout.append(L.cutout(p, x, y, h, delay=d, dur=1 / 6))
            if "mouth" in el:
                self.media["mouth"] = L.image_point(p, x, y, h, *el["mouth"])
        elif "bubble" in el:
            mx, my = el.get("tip") or self.media["mouth"]
            tip = (mx - 18, my + 4); size = el.get("size", 84); tail = el.get("tail", 230)
            self.mout.append(L.speech_bubble(el["bubble"], *tip, size=size, tail=tail, delay=d, dur=1 / 6,
                                            type_dur=0.17))
            if el.get("box_at"):
                bx, by, bw, bh = L.bubble_bounds(el["bubble"], *tip, size=size, tail=tail)
                self.mout.append(L.hl_box(bx - 34, by - 34, bw + 68, bh + 68, delay=self.at(el["box_at"]),
                                         dur=0.25, color=th["accent"], sw=8))
                if el.get("box_label"):
                    self.mout.append(L.page_text(el["box_label"], bx - 60, by + bh / 2 + 62, 170,
                                                delay=self.at(el["box_at"]) + 0.25, dur=1 / 12, anim="fade",
                                                fill="accent", anchor="end"))
        else:
            raise ValueError(f"unknown page element {sorted(el)}")
        self.marks.append((el, d))

    def build(self):
        for el in self.page["elements"]:
            self.element(el)
        dy = 0 if self.page.get("align") == "top" else max(0.0, (CONTENT_BOTTOM - self.y) / 2)
        parts = [self.L.step_fps(self.page.get("step_fps", 12)),
                 f'<g transform="translate(0,{dy:.0f})">', *self.out, "</g>", *self.mout]
        if self.progress:
            parts.append(self.L.progress(*self.progress))
        return "".join(parts)


def plan_pages(spec, tl):
    """每页起止（成片秒）和起点原文位置。页面从它第一个绑词前 PAGE_LEAD 秒开始。"""
    starts, pos = [], 0
    for i, page in enumerate(spec["pages"]):
        first = page.get("from") or next((el.get("at") for el in page["elements"] if el.get("at")), None)
        t, p = cue_time(tl, first, pos) if first else (0.0, pos)
        t = 0.0 if i == 0 else max(t - PAGE_LEAD, starts[-1][0] + MIN_PAGE)
        starts.append((t, p)); pos = p
    bounds = [s for s, _ in starts] + [tl.duration]
    return [(bounds[i], bounds[i + 1], starts[i][1]) for i in range(len(spec["pages"]))]


# ---- 出片 --------------------------------------------------------------------------------------
class Project:
    def __init__(self, spec_path):
        self.spec_path = Path(spec_path).resolve()
        self.base = self.spec_path.parent
        self.spec = _read_json(self.spec_path)
        self.work = _resolve(self.base, self.spec.get("work", f"work/{self.spec_path.stem}"))
        for name in ("DIR_ASSETS", "DIR_SCRIPTS", "DIR_AUDIO", "DIR_SRT", "DIR_SCENE", "DIR_RENDERED", "DIR_OUTPUT"):
            setattr(config, name, str(self.work / name.split("_", 1)[1].lower()))
        config.CINEMATIC = False
        config.TRANSITION_SECONDS = 0.0
        if self.spec.get("encoder", "cpu") == "cpu":
            config.VCODEC = "libx264"
            config.NVENC_EXTRA = ["-preset", "medium", "-pix_fmt", "yuv420p"]
            config.CQ = "12"
        import v2lib as L
        L.use_theme(self.spec.get("theme", config.PAGE_THEME))
        config.BG_VIDEO = (str(_resolve(self.base, self.spec["background"])) if self.spec.get("background")
                           else L.page_background(self.work / "page.png"))
        self.tl = load_timeline(self.spec, self.base)
        self.pages = plan_pages(self.spec, self.tl)

    def scenes(self):
        from pipeline import build_scene
        out, durs = [], []
        prog = self.spec.get("progress")
        for i, (page, (t0, t1, pos)) in enumerate(zip(self.spec["pages"], self.pages)):
            progress = page.get("progress", prog)
            frag = PageBuilder(self.tl, page, t0, pos, self.base, progress).build()
            path = self.work / "scene" / f"scene_{i + 1:02d}.html"
            path.parent.mkdir(parents=True, exist_ok=True)
            (self.work / "scene" / f"fragment_{i + 1:02d}.svg").write_text(frag, encoding="utf-8")
            build_scene.build(frag, str(path), srt=[], strict=True)
            out.append(str(path)); durs.append(round(t1 - t0, 4))
        return out, durs

    def plan(self):
        rows = []
        for i, (page, (t0, t1, pos)) in enumerate(zip(self.spec["pages"], self.pages)):
            b = PageBuilder(self.tl, page, t0, pos, self.base)
            b.build()
            rows.append({"page": i + 1, "start": round(t0, 2), "end": round(t1, 2),
                         "elements": [[next(k for k in el if k not in ("at", "size", "y")), el.get("at"),
                                       round(t0 + d, 2)] for el, d in b.marks]})
        return {"duration": round(self.tl.duration, 3), "pages": rows}

    def stills(self, times=None):
        from playwright.sync_api import sync_playwright
        from PIL import Image
        scenes, durs = self.scenes()
        bg = Image.open(config.BG_VIDEO).convert("RGBA").resize((config.WIDTH, config.HEIGHT))
        times = times or [t0 + (t1 - t0) - 0.05 for t0, t1, _ in self.pages]
        bounds = [t0 for t0, _, _ in self.pages]
        shots = []
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            pg = b.new_page(viewport={"width": config.WIDTH, "height": config.HEIGHT})
            for t in times:
                i = max(k for k, s in enumerate(bounds) if s <= t)
                pg.goto(Path(scenes[i]).as_uri()); pg.wait_for_load_state("networkidle")
                pg.evaluate("document.fonts.ready")
                pg.evaluate(f"window.seekTime({t - bounds[i]})")
                png = self.work / f"still_{t:06.2f}.png"
                pg.screenshot(path=str(png), omit_background=True)
                im = bg.copy(); im.alpha_composite(Image.open(png).convert("RGBA"))
                im.convert("RGB").resize((1920, 1080)).save(png)
                shots.append(png)
            b.close()
        return shots

    def audio(self):
        wav = self.work / "narration.wav"
        inputs, chains = [], []
        for k, part in enumerate(self.tl.parts):
            inputs += ["-i", str(part.audio)]
            d = part.cut_end - part.cut_start
            chains.append(f"[{k}:a]atrim=start={part.cut_start:.4f}:end={part.cut_end:.4f},asetpts=PTS-STARTPTS,"
                          f"aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d=0.01,"
                          f"afade=t=out:st={max(0.0, d - 0.02):.4f}:d=0.02[a{k}]")
        n = len(self.tl.parts)
        graph = ";".join(chains) + ";" + "".join(f"[a{k}]" for k in range(n)) + \
            f"concat=n={n}:v=0:a=1,apad=whole_dur={self.tl.duration:.4f}[out]"
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", graph,
                        "-map", "[out]", str(wav)], check=True)
        return wav

    def render(self):
        from pipeline import lint, render, subtitles
        scenes, durs = self.scenes()
        if lint.lint(scenes, durs):
            raise SystemExit("layout lint found HARD overflow")
        track = self.work / "output" / "video_track.mp4"
        render.render_timeline(scenes, durs, out_path=str(track))
        wav = self.audio()
        ass = self.work / "subtitles.ass"
        ass.write_text(subtitles.karaoke_ass(self.tl.text, self.tl.words, duration=self.tl.duration),
                       encoding="utf-8")
        out = _resolve(self.base, self.spec["out"])
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(subtitles.playable_copy(track, out, ass=ass, audio=wav), check=True)
        print(f"[pages] -> {out}")
        return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__); return 2
    project = Project(argv[0])
    cmd = argv[1] if len(argv) > 1 else "plan"
    if cmd == "plan":
        print(json.dumps(project.plan(), ensure_ascii=False, indent=1))
    elif cmd == "stills":
        for p in project.stills([float(v) for v in argv[2:]] or None):
            print(p)
    elif cmd == "render":
        project.render()
    else:
        print(__doc__); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
