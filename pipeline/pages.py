# -*- coding: utf-8 -*-
"""图文页：分镜表（JSON）→ 页面 → 有声、带字幕的可播放片子。

一张表管一段片子：用哪几段配音（可只取其中几句）、主题、每一页放什么、每个元素绑哪个词。
元素按念到的词逐字揭示或平滑入场；图表和照片复用既有动画原语。坐标不用手写：左栏文字自上而下排，
右栏放照片卡、抠图和气泡；个别元素可写 x/y 覆盖。写法见 docs/AUTHORING.md“图文页”。

    python -m pipeline.pages <表.json> plan            # 每页起止时间、各元素绑到的时刻
    python -m pipeline.pages <表.json> stills [秒 ...]  # 无头抽帧（默认每页最后一刻）
    python -m pipeline.pages <表.json> render          # 出片：4K 画面轨 → 1080p 可播放副本

绑词写原文里的字（显示的写法，如“846 亿”），不用写读法；同一页里第二次出现写“词#2”，
错开写“词+0.2s”。每个元素都必须绑词；绑的词找不到、没被念到，或会比念到早出现，都直接报错。
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import warnings
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

PAGE_LEAD = 0.08     # 只给换页留少量空白，内容仍从词轴时刻开始
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


_CUE = re.compile(r"^(?P<word>.+?)(?:#(?P<n>\d+))?(?:(?P<off>[+-]\d*\.\d+|[+-]\d+)s)?$")
EARLY_TOLERANCE = 0.0   # 内容不得早于所绑定的词；页面空白可提前切入


def cue_time(tl, cue, after):
    """“词”“词#2”“词+0.2s” → 成片秒数；从原文位置 after 往后找。返回 (秒, 原文位置)。

    偏移必须带 s（“GPT-6”“3-5 年”这类原文不会被误读成偏移）；整串在原文里能找到时一律按原文找。
    找不到或这几个字没被念到都直接报错，不退回页首。
    """
    raw = cue.strip()
    word, n, off = raw, 1, 0.0
    if tl.text.find(raw, after) < 0:
        m = _CUE.match(raw)
        if not m:
            raise ValueError(f"bad cue {cue!r}")
        word, n, off = m.group("word"), int(m.group("n") or 1), float(m.group("off") or 0)
    if off < -EARLY_TOLERANCE:
        raise ValueError(f"cue {cue!r} would show {-off:.2f}s before the word is spoken")
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
SIZES = config.PAGE_MOTION["sizes"]
CONTENT_BOTTOM = 1840   # 往下留给字幕和进度条


class PageBuilder:
    def __init__(self, tl, page, start, start_pos, base, progress=None, end=None):
        import v2lib as L
        self.L, self.tl, self.page, self.start, self.base = L, tl, page, start, base
        self.pos = start_pos
        self.end = tl.duration if end is None else end
        th = L.theme()
        self.th = th
        media = any(k in el for el in page["elements"] for k in ("photo", "cutout", "bubble", "card", "fragment"))
        self.left = page.get("x", th["margin"])
        self.width = page.get("width", 1640 if media else config.WIDTH - 2 * th["margin"])
        self.y = page.get("top", th["top"])
        self.out = []          # 左栏（排完后整体竖向居中）
        self.mout = []         # 右栏媒体
        self.marks = []      # (元素, 本页秒数)
        self.progress = progress
        self.media = {}
        self.options = {}

    def at(self, cue, default=None):
        """绑词 → 本页秒数。没写绑词时只接受调用方给的默认（同一元素里已绑好的时刻）。"""
        if not cue:
            if default is None:
                raise ValueError("every page element needs an `at` cue (elements may not appear before "
                                 "their words are spoken)")
            return default
        t, pos = cue_time(self.tl, cue, self.pos)
        if t < self.start - EARLY_TOLERANCE:
            raise ValueError(f"cue {cue!r} is spoken at {t:.2f}s, before its page starts ({self.start:.2f}s)")
        return max(0.0, t - self.start)

    def glyph_times(self, s, delay):
        """逐字词轴。原文逐字揭示；概括标题必须显式绑一个已念到的词。"""
        plain = "".join(t for t, _ in markup(s))
        pos = self.tl.text.find(plain, self.pos)
        if pos < 0:
            return None
        times, last = [], delay
        for p in range(pos, pos + len(plain)):
            at = self.tl.char_time(p)
            last = max(delay, at - self.start) if at is not None else last
            times.append(round(last, 4))
        return times

    def text_block(self, s, size, delay, *, font="heavy", weight=900, fill=None, anim="fade-up", gap=0.32, x=None):
        L = self.L
        x = self.left if x is None else x
        x = self.options.get("x",x)
        minimum = config.PAGE_MOTION["min_label" if font == "mono" else "min_text"]
        if size < minimum:
            warnings.warn(f"text size {size} is below the suggested readable size {minimum}")
        lines = wrap(markup(s), size, self.width - (x - self.left))
        offset = 0
        glyphs = self.glyph_times(s, delay)
        dur = self.options.get("dur", config.PAGE_MOTION["entrance"])
        for line in lines:
            count = sum(len(t) for t, _ in line)
            self.y += size
            self.out.append(L.page_text(line, x, self.y, size, delay=delay, dur=dur,
                                        anim=self.options.get("anim", anim), font=font,
                                        weight=weight, fill=fill, shift=self.options.get("shift", config.PAGE_MOTION["shift"]),
                                        glyph_times=glyphs[offset:offset+count] if glyphs is not None else None))
            offset += count
            self.y += size * 0.22
        self.y += size * gap

    def element(self, el):
        L, th = self.L, self.th
        if "gap" in el and len(el) == 1:
            self.y += el["gap"]; return
        from pipeline import boards
        board = next((k for k in boards.KINDS if k in el), None)
        before_out, before_media = len(self.out), len(self.mout)
        if board:     # 通用版式（pipeline/boards.py）：绝对定位，自己按词轴安排每一个动作
            d = self.at(el["at"]) if el.get("at") else 0.0
            self.mout.append(boards.KINDS[board](boards.Ctx(self), el))
        else:
            d = self.at(el.get("at"))
            self.flow_element(el, d)
        self.marks.append((el, d))
        if el.get("hold_check") == "warn":    # 已审定的旧页：退场检查只提示，不拦出片
            for out, first in ((self.out, before_out), (self.mout, before_media)):
                content = "".join(out[first:]); del out[first:]
                out.append(f'<g data-hold-check="warn">{content}</g>')
        if el.get("exit_at"):
            when = self.at(el["exit_at"])
            for out, first in ((self.out, before_out), (self.mout, before_media)):
                content = "".join(out[first:]); del out[first:]
                out.append(f'<g data-anim="fade-out" data-delay="{when}" data-dur="{el.get("exit_dur", 0.3)}">'
                           f'{content}</g>')

    def flow_element(self, el, d):
        L, th = self.L, self.th
        self.options = el
        if "y" in el:
            self.y = el["y"]
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
                self.y += 84
                self.out.append(L.page_text(el["label"], self.left, self.y, 84, delay=d, anim="fade-up",
                                            fill="muted", font="mono", weight=700, ls=4))
                self.y += 30
            self.text_block(el["note"], el.get("size", SIZES["note"]), d, font="sans", weight=700, gap=1.0)
        elif "old" in el:
            size = el.get("size", SIZES["old"]); self.y += size
            strike = self.at(el["strike"]) if el.get("strike") else None
            self.out.append(L.old_text(el["old"], self.left, self.y, size, delay=d,
                                       strike_delay=strike if strike is not None else None))
            self.y += size * 0.6
        elif "bullets" in el:
            size = el.get("size", SIZES["text"])
            for text, cue in el["bullets"]:
                self.text_block(text, size, self.at(cue, d), font="sans", weight=600, anim="fade-left", gap=0.45)
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
            vmax = el.get("max", max(float(b["value"]) for b in el["bars"]))
            w = el.get("width", self.width - 700)
            for b in el["bars"]:
                self.y += el.get("row_gap", 220)
                self.out.append(L.hbar(b["label"], b.get("text", b["value"]), float(b["value"]) / vmax, self.left,
                                       self.y, w=w, h=el.get("h", 88), delay=self.at(b.get("at"), d),
                                       dur=b.get("dur", config.PAGE_MOTION["count"]),
                                       fill="accent" if b.get("accent") else None, size=el.get("size", 84),
                                       numeric=b["value"], decimals=1 if float(b["value"])%1 else 0,
                                       suffix=b.get("suffix", ""),
                                       label_delay=self.at(b["label_at"]) if b.get("label_at") else None))
                self.y += el.get("h", 88) + el.get("after", 100)
        elif "meter" in el:
            self.y += 60
            steps = [self.at(c, d) for c in el.get("steps", [])]
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
            w = el.get("w", 1560); h = el.get("h")
            cx, cy = el.get("cx", 2820), el.get("cy", 1000)
            hold = max(0.01,self.end-self.start-d) if el.get("hold", True) else 0
            self.mout.append(L.photo_card(p, cx, cy, w, h=h, delay=d, align=el.get("align", "xMidYMid"),
                                         dur=el.get("dur"), anim=el.get("anim"), shift=el.get("shift",100),
                                         hold=hold, zoom=el.get("zoom",1.035)))
            iw, ih = L.img_dims(p)
            self.media["photo"] = (cx, cy, w, h or w * ih / iw)
        elif "cutout" in el:
            p = str(_resolve(self.base, el["cutout"]))
            h = el.get("h", 1520); x, y = el.get("x", 2690), el.get("y", 940)
            self.mout.append(L.cutout(p, x, y, h, delay=d, dur=el.get("dur"), ambient=el.get("ambient",True)))
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
        elif "fragment" in el:
            from pipeline.build_scene import parse_fragment
            root = parse_fragment(_resolve(self.base,el["fragment"]).read_text(encoding="utf-8"))
            for node in root.iter():
                if "data-cue" in node.attrib:
                    cue = node.attrib.pop("data-cue")
                    index = node.attrib.pop("data-cue-index",None)
                    off = float(node.attrib.pop("data-cue-offset",0))
                    cue += (f"#{index}" if index else "") + (f"{off:+g}s" if off else "")
                    node.set("data-delay",str(self.at(cue)))
                elif "data-anim" in node.attrib:
                    node.set("data-delay",str(d+float(node.get("data-delay",0))))
            self.mout.append((root.text or "")+"".join(ET.tostring(n,encoding="unicode") for n in root))
        else:
            raise ValueError(f"unknown page element {sorted(el)}")

    def build(self):
        for el in self.page["elements"]:
            self.element(el)
        dy = 0 if self.page.get("align") == "top" else max(0.0, (CONTENT_BOTTOM - self.y) / 2)
        parts = [self.L.step_fps(self.page.get("step_fps", 0)),
                 f'<g transform="translate(0,{dy:.0f})">', *self.out, "</g>", *self.mout]
        if self.progress:
            n,current,frac = self.progress[:3]
            begin = self.progress[3] if len(self.progress) > 3 else 0.0
            parts.append(self.L.progress(n,current,begin+(frac-begin)*self.end/self.tl.duration,
                                         duration=self.end-self.start,
                                         start_frac=begin+(frac-begin)*self.start/self.tl.duration))
        return "".join(parts)


AMBIENT = ("pulse", "float", "drift", "flow-blob", "wave", "push", "fade-out", "xfade")


def unfinished(fragment, duration, transition=0.0, hold=None):
    """退场前没放完的动画。返回 [(动作, 本页结束秒, 退场秒, 说明)]。

    每个有限的动画（入场、描线、滚动、移动……）都要在它所在的组退场（fade-out/xfade 开始）、
    整页被圆形擦除盖住或换页（扣掉换页淡出）之前放完，并且停够 hold 秒。持续的环境运动
    （呼吸、漂浮、循环流动、声波、照片推近）和进度条不算。
    """
    import json as _json
    from pipeline.build_scene import parse_fragment
    hold = config.PAGE_MOTION["hold"] if hold is None else hold
    root = parse_fragment(fragment)
    page_end = duration - transition
    covers = [float(n.get("data-delay", 0)) for n in root.iter() if n.get("data-cover") == "1"]
    for n in root.iter():
        if n.get("data-cover") == "1":
            end = float(n.get("data-delay", 0)) + float(n.get("data-dur", 1))
            if end > duration + 1e-3:
                yield ("wipe", round(end, 3), round(duration, 3), "圆形擦除在换页前没盖完", False)
    cover = min(covers) if covers else None
    bad = []

    def walk(node, exit_t, warn=False):
        warn = warn or node.get("data-hold-check") == "warn"
        kind = node.get("data-anim")
        if kind in ("fade-out", "xfade"):
            exit_t = min(exit_t, float(node.get("data-delay", 0)))
        if kind and kind not in AMBIENT and node.get("data-ambient") != "1" and node.get("data-cover") != "1":
            a = float(node.get("data-delay", 0))
            if node.get("data-glyph-times"):
                ts = [t for t in _json.loads(node.get("data-glyph-times")) if t < 9000]
                end = (max(ts) if ts else a) + float(node.get("data-glyph-fade", 0.12))
            elif kind == "keys":
                end = max(k[0] for k in _json.loads(node.get("data-keys")))
            elif kind == "shake":
                end = a + 0.5
            else:
                end = a + float(node.get("data-dur", 1))
            if end + hold > exit_t + 1e-3:
                txt = "".join(node.itertext()).strip()[:16]
                bad.append((kind, round(end, 3), round(exit_t, 3), txt, warn))
        for ch in node:
            walk(ch, exit_t, warn)

    top = page_end if cover is None else min(page_end, cover)
    for ch in root:
        walk(ch, top if ch.get("data-cover") != "1" else page_end)
    yield from bad


def motion_gaps(fragment, duration, limit=None):
    """按可见主内容的动作时段找长停顿；进度条不算主内容动画。"""
    from pipeline.build_scene import parse_fragment
    limit = config.PAGE_MOTION["static_warning"] if limit is None else limit
    intervals = []
    for node in parse_fragment(fragment).iter():
        kind = node.get("data-anim")
        if not kind or node.get("data-ease") == "linear" and node.tag.endswith("rect"):
            continue
        a = float(node.get("data-delay",0)); b = a+float(node.get("data-dur",1))
        if node.get("data-glyph-times"):
            intervals.extend((float(t),float(t)+config.PAGE_MOTION["glyph_fade"]) for t in json.loads(node.get("data-glyph-times")))
        elif kind in ("float","drift","pulse","flow-blob"):
            intervals.append((a,duration))
        else: intervals.append((a,b))
    gaps, end = [], 0.0
    for a,b in sorted(intervals)+[(duration,duration)]:
        a,b = max(0,min(a,duration)),max(0,min(b,duration))
        if a-end>limit: gaps.append((round(end,3),round(a,3)))
        end=max(end,b)
    return gaps


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
        config.TRANSITION_SECONDS = float(self.spec.get("transition",config.PAGE_MOTION["transition"]))
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
            frag = PageBuilder(self.tl, page, t0, pos, self.base, progress, t1).build()
            found = list(unfinished(frag, t1 - t0, config.TRANSITION_SECONDS))
            for k, e, x, txt, _ in [f for f in found if f[4]]:
                warnings.warn(f"page {i + 1}（已审定，只提示）: {k} 到 {t0 + e:.2f}s 才放完、{t0 + x:.2f}s 就退场“{txt}”")
            late = [f for f in found if not f[4]]
            if late:
                rows = "; ".join(f"{k} 到 {t0 + e:.2f}s 才放完、{t0 + x:.2f}s 就退场“{txt}”" for k, e, x, txt, _ in late[:8])
                raise ValueError(f"page {i + 1}: {len(late)} 个动画没放完就退场或换页（要停够 "
                                 f"{config.PAGE_MOTION['hold']}s）：{rows}")
            for a,b in motion_gaps(frag,t1-t0):
                warnings.warn(f"page {i+1}: main content static for {b-a:.2f}s ({t0+a:.2f}–{t0+b:.2f}s)")
            path = self.work / "scene" / f"scene_{i + 1:02d}.html"
            path.parent.mkdir(parents=True, exist_ok=True)
            (self.work / "scene" / f"fragment_{i + 1:02d}.svg").write_text(frag, encoding="utf-8")
            build_scene.build(frag, str(path), srt=[], strict=True)
            out.append(str(path)); durs.append(round(t1 - t0, 4))
        return out, durs

    def plan(self):
        rows = []
        for i, (page, (t0, t1, pos)) in enumerate(zip(self.spec["pages"], self.pages)):
            b = PageBuilder(self.tl, page, t0, pos, self.base, end=t1)
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
            b = p.chromium.launch(headless=True,channel="chrome")
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
        ass.write_text(subtitles.karaoke_ass(self.tl.text, self.tl.words, duration=self.tl.duration,reveal=True),
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
