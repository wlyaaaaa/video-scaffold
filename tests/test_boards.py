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


class HoldCheckTests(unittest.TestCase):
    def test_unfinished_animation_before_exit_is_reported(self):
        frag = ('<g data-anim="fade-out" data-delay="2.0" data-dur="0.3">'
                '<rect data-anim="grow-bar" data-delay="1.5" data-dur="0.6" width="10" height="10"/></g>')
        rows = list(pages.unfinished(frag, 5.0))
        self.assertEqual(1, len(rows))
        self.assertEqual("grow-bar", rows[0][0])
        ok = frag.replace('data-delay="1.5"', 'data-delay="1.0"')
        self.assertEqual([], list(pages.unfinished(ok, 5.0)))

    def test_page_end_wipe_and_ambient(self):
        frag = ('<text data-anim="type" data-delay="0" data-dur="0.3" data-glyph-times="[0, 4.9]" '
                'data-glyph-fade="0.14">ab</text><g data-anim="pulse" data-delay="0" data-dur="0.4"/>')
        self.assertEqual(1, len(list(pages.unfinished(frag, 5.0))))          # 页尾前没停够
        self.assertEqual(0, len(list(pages.unfinished(frag, 5.4))))
        warn = '<g data-hold-check="warn">' + frag + '</g>'
        self.assertTrue(all(r[4] for r in pages.unfinished(warn, 5.0)))     # 已审定：只提示
        cover = '<circle data-anim="iris" data-cover="1" data-delay="3" data-dur="0.4"/>'
        self.assertEqual(1, len(list(pages.unfinished(
            '<rect data-anim="fade" data-delay="2.9" data-dur="0.3"/>' + cover, 5.0))))

    def test_new_bodies_build(self):
        tl = _timeline()
        page = {"elements": [{"deck": [
            {"at": "网上", "title": "天天用", "body": [
                {"kind": "chat", "items": [{"side": "user", "text": "天天用", "at": "天天", "ring_at": "气到"},
                                           {"side": "ai", "lines": 2, "at": "常常", "note": "常常", "note_at": "常常"}]},
                {"kind": "dial", "at": "天天", "label": "天天用", "label_at": "天天", "grow_at": "常常",
                 "label2": "气到", "label2_at": "气到"}]},
            {"at": "光", "title": "烧了", "body": [
                {"kind": "scan", "circle_at": "Claude", "scan_at": "烧了"},
                {"kind": "gauges", "items": [{"label": "加上", "at": "加上"}], "full_at": "累计"},
                {"kind": "ring", "nodes_at": "光", "narrow_at": "Claude", "wide_at": "烧了"},
                {"kind": "bar", "at": "光", "change_at": "烧了"}, {"kind": "flow", "at": "光"},
                {"kind": "terminal", "at": "光"}]}]},
            {"cards": [{"at": "Codex", "title": "Codex", "icon": "laptop"}]}]}
        frag = pages.PageBuilder(tl, page, 0.0, 0, None).build()
        parse_fragment(frag)


class Seg06BodyTests(unittest.TestCase):
    """终端真字、开关拨动、截图多个强调框、卡片行划线，以及本页之后才念到的名字按概括字样打出。"""

    def setUp(self):
        self.tl = _timeline()

    def build(self, elements, end=None):
        return pages.PageBuilder(self.tl, {"elements": elements}, 0.0, 0, None, end=end).build()

    def test_terminal_rows_toggle_and_tile_strike_finish(self):
        frag = self.build([
            {"cards": [{"at": "网上", "title": "天天用", "body": [
                {"kind": "terminal", "at": "天天", "rows": [{"text": "run check", "prompt": True},
                                                          {"text": "status=pass", "at": "常常", "color": "#7FD8B0"}]},
                {"kind": "toggle", "at": "网上", "off_at": "气到", "label": "记忆"}]}]},
            {"tiles": [{"title": "天天用", "at": "天天", "lines": [{"text": "离谱", "at": "离谱", "strike_at": "可我"}]}]}])
        root = parse_fragment(frag)
        texts = ["".join(e.itertext()) for e in root.iter() if e.get("data-glyph-times")]
        self.assertIn("› run check", texts)
        self.assertIn("status=pass", texts)
        self.assertTrue(any(e.get("data-mode") == "strike" for e in root.iter()))
        keys = [json.loads(e.get("data-keys")) for e in root.iter() if e.get("data-keys")]
        self.assertTrue(any(k[-1][1] < 0 for k in keys))          # 圆钮滑到左边
        self.assertEqual([], list(pages.unfinished(frag, self.tl.duration)))

    def test_screenshot_focus_boxes_follow_their_own_cues(self):
        import tempfile
        from pathlib import Path
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "panel.png"
            Image.new("RGB", (100, 20), "white").save(src)
            b = pages.PageBuilder(self.tl, {"elements": [{"screenshot": src.name, "at": "网上",
                "focus": [[0, 0, .5, 1, "天天"], [.5, 0, .5, 1, "气到"]]}]}, 0.0, 0, Path(tmp))
            root = parse_fragment(b.build())
            delays = sorted(float(e.get("data-delay")) for e in root.iter()
                            if e.tag.endswith("rect") and e.get("data-anim") == "draw")
            want = [self.tl.char_time(TEXT.find("天天")), self.tl.char_time(TEXT.find("气到"))]
            for got, exp in zip(delays, want):
                self.assertAlmostEqual(got, exp, places=3)

    def test_name_spoken_only_after_this_page_types_from_its_cue(self):
        end = self.tl.char_time(TEXT.find("光")) - 0.1      # 本页在“Claude”被念到之前结束
        frag = self.build([{"focus_network": {"nodes": [{"label": "Claude", "at": "天天"}]}, "at": "网上"}], end=end)
        root = parse_fragment(frag)
        el = next(e for e in root.iter() if e.get("data-glyph-times") and "".join(e.itertext()) == "Claude")
        self.assertLess(max(json.loads(el.get("data-glyph-times"))), end)
