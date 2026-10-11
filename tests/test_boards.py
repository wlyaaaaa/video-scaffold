# -*- coding: utf-8 -*-
"""通用版式（pipeline.boards）：每种版式能出片段，原文字不早于被念到，动作原语都是运行时认识的。"""
from __future__ import annotations

import json
import re
import unittest
import xml.etree.ElementTree as ET

from pipeline import pages
from pipeline.build_scene import parse_fragment
from pipeline.subtitles import align_text

TEXT = "网上都说，AI 已经强得离谱了：上个月它解出了难题。可我天天用，还是常常被它气到。光 Claude 就烧了 846 亿 token，加上 Codex，累计 3118.5 亿。"
SPOKEN = ["网", "上", "都", "说", "AI", "已", "经", "强", "得", "离", "谱", "了", "上", "个", "月", "它", "解", "出",
          "了", "难", "题", "可", "我", "天", "天", "用", "还", "是", "常", "常", "被", "它", "气", "到", "光", "Claude",
          "就", "烧", "了", "八百四十六亿", "token", "加", "上", "Codex", "累", "计", "三千一百一十八点五亿"]


def _timeline():
    words = [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.35} for i, w in enumerate(SPOKEN)]
    return pages.Timeline([], TEXT, words, align_text(TEXT, words), len(words) * 0.4 + 0.6)


PAGE = {"elements": [
    {"head": "网上都说", "at": "网上", "tag": "热议", "sub": [["评论区", "AI"], ["官方", "上个月"]]},
    {"timeline": [{"label": "上个月", "at": "上个月", "x": 0.6}], "y": 1660,
     "trace": {"from": 0, "to": 0, "at": "上个月", "until": "难题"}},
    {"claims": [{"text": "AI 已经强得离谱", "at": "AI", "mark": "强得离谱", "strike": "可我"},
                {"text": "*常常被它气到*", "at": "常常"}]},
    {"deck": [{"at": "网上", "frame": False, "body": [{"kind": "comments", "items": ["一句话做个网站"]}]},
              {"at": "上个月", "title": "天天用", "icon": "math",
               "body": [{"kind": "grid", "n": 14, "at": "天天", "flip": [1, 3], "flip_at": "气到"},
                        {"kind": "wave", "at": "可我", "until": "气到"}]}]},
    {"checklist": [{"text": "天天用", "at": "天天", "icon": "bolt"},
                   {"text": "气到", "at": "气到", "icon": "burst", "pre": "常常被它", "pre_at": "常常"}]},
    {"tally": [{"label": "Claude", "value": 846, "at": "846", "unit": "亿 token", "unit_at": "亿"},
               {"label": "Codex", "value": 2272.5, "at": "Codex", "number": False}],
     "total": {"label": "累计", "at": "累计", "value": 3118.5, "count_at": "3118.5", "unit": "亿", "unit_at": "亿#2"}},
    {"wipe": "气到", "x": 900, "y": 900},
]}


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.tl = _timeline()
        self.frag = pages.PageBuilder(self.tl, PAGE, 0.0, 0, None).build()

    def test_every_board_builds_valid_known_primitives(self):
        root = parse_fragment(self.frag)          # 未知原语或非法片段会在这里报错
        kinds = {e.get("data-anim") for e in root.iter() if e.get("data-anim")}
        for k in ("type", "keys", "mark", "iris", "wave", "shake", "grow-bar", "count", "trace-dot", "pop"):
            self.assertIn(k, kinds)

    def test_spoken_glyphs_never_appear_before_their_words(self):
        root = ET.fromstring('<svg xmlns="http://www.w3.org/2000/svg">' + self.frag + "</svg>")
        checked = 0
        for el in root.iter():
            times = el.get("data-glyph-times")
            if not times:
                continue
            shown = "".join(el.itertext())
            ts = json.loads(times)
            core = shown.strip("“”")
            at = TEXT.find(core)
            if at < 0 or not core:
                continue
            lead = shown.find(core)
            for k in range(len(core)):
                spoken = self.tl.char_time(at + k)
                if spoken is not None and ts[lead + k] < 9000:
                    self.assertGreaterEqual(ts[lead + k] + 1e-6, spoken, (shown, k))
                    checked += 1
        self.assertGreater(checked, 20)

    def test_marks_follow_the_last_marked_glyph(self):
        mt = re.search(r'data-mode="band"[^>]*data-delay="([0-9.]+)"', self.frag)
        self.assertIsNotNone(mt)
        self.assertGreaterEqual(float(mt.group(1)), self.tl.char_time(TEXT.find("谱")))

    def test_unknown_parts_fail_loudly(self):
        b = pages.PageBuilder(self.tl, {"elements": []}, 0.0, 0, None)
        with self.assertRaises(ValueError):
            b.element({"checklist": [{"text": "天天用", "at": "天天", "icon": "nope"}]})
        with self.assertRaises(ValueError):
            b.element({"claims": [{"text": "天天用", "at": "天天", "mark": "没有"}]})


if __name__ == "__main__":
    unittest.main()
