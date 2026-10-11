"""通用图解的词轴、不裁截图和跨片进度契约。"""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pipeline import boards, pages
from pipeline.build_scene import parse_fragment
from pipeline.subtitles import align_text


TEXT = "同一个要求，说了好几遍，还是照旧。最后一句，真正要的。一个小时，做着做着，一整天。毛病，看不出来。开始幻觉，流量、内存、磁盘，全打满。注意力，更全面。清手机，换电脑，真用过。"


def timeline():
    letters = [c for c in TEXT if c not in "，。、"]
    words = [{"word": c, "start": .1+i*.2, "end": .28+i*.2} for i, c in enumerate(letters)]
    return pages.Timeline([], TEXT, words, align_text(TEXT, words), len(words)*.2+1)


class DiagramTests(unittest.TestCase):
    def setUp(self):
        self.tl = timeline()

    def build(self, elements, base=None, progress=None, start=0, end=None):
        return pages.PageBuilder(self.tl, {"elements": elements}, start, 0, base,
                                 progress=progress, end=end).build()

    def test_all_diagrams_parse_and_spoken_labels_are_not_early(self):
        elements = [
            {"repeat_flow": {"input": "同一个要求", "repeats": ["好几遍", "遍"],
                             "result": "照旧", "result_at": "照旧"}, "at": "同一个要求"},
            {"focus_network": {"nodes": [{"label": "最后一句", "at": "最后一句"},
                                          {"label": "真正要的", "at": "真正要的"}],
                               "visits": [{"node": 0, "at": "最后一句"}],
                               "expand_at": "更全面"}, "at": "最后一句"},
            {"time_stretch": {"start_label": "一个小时", "stretch_at": "做着做着",
                              "end_label": "一整天", "end_at": "一整天"}, "at": "一个小时"},
            {"scan_grid": {"reveal_at": "毛病", "miss_at": "看不出来"}, "at": "毛病"},
            {"capacity_gauges": {"items": [{"label": x, "at": x} for x in ("流量", "内存", "磁盘")],
                                 "noise_at": "幻觉", "full_at": "全打满"}, "at": "开始幻觉"},
            {"device_flow": {"phone_label": "清手机", "computer_label": "换电脑",
                             "computer_at": "换电脑", "move_at": "清手机"}, "at": "清手机"},
        ]
        root = parse_fragment(self.build(elements))
        checked = 0
        for el in root.iter():
            if not el.get("data-glyph-times"):
                continue
            txt = "".join(el.itertext())
            idx = TEXT.find(txt)
            if idx < 0:
                continue
            for k, at in enumerate(json.loads(el.get("data-glyph-times"))):
                ct = self.tl.char_time(idx+k)
                if ct is not None:
                    self.assertGreaterEqual(at+1e-6, ct)
                    checked += 1
        self.assertGreater(checked, 25)

    def test_stamp_preserves_whole_image_aspect_and_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src = base / "original-panel.png"
            Image.new("RGB", (100, 60), "white").save(src)
            original = src.read_bytes()
            root = parse_fragment(self.build([
                {"screenshot": src.name, "at": "真用过", "w": 500,
                 "focus": [.5, .1, .4, .3]}], base=base))
            images = [el for el in root.iter() if el.tag.endswith("image")]
            self.assertEqual(len(images), 1)
            self.assertEqual(images[0].get("preserveAspectRatio"), "xMidYMid meet")
            self.assertEqual(float(images[0].get("height")), 300)
            self.assertEqual(images[0].get("href"), src.as_uri())
            self.assertEqual(src.read_bytes(), original)
            self.assertFalse(any(el.tag.endswith("clipPath") for el in root.iter()))

    def test_hub_is_above_connections(self):
        root = parse_fragment(self.build([{"focus_network": {"center": "注意力", "nodes": [{}, {}],
                "expand_at": "更全面"}, "at": "注意力"}]))
        text_nodes = [el for el in root.iter() if el.get("data-glyph-times")]
        self.assertEqual("".join(text_nodes[-1].itertext()), "注意力")

    def test_progress_continues_from_previous_part(self):
        import v2lib
        from unittest.mock import patch
        with patch.object(v2lib, "progress", return_value="") as progress:
            self.build([], progress=[10, 0, 1, .42], end=self.tl.duration/2)
            self.assertAlmostEqual(progress.call_args.args[2], .71)
            self.assertAlmostEqual(progress.call_args.kwargs["start_frac"], .42)

    def test_review_diagrams_keep_spoken_text_on_time_and_finish(self):
        """摘要压缩、对照核对、并行轨道、进度轨和卡片里的细看/任务单/水位条：原文字不早出，动画能放完。"""
        elements = [
            {"condense": {"rows": [{"at": "同一个要求", "user": True}, {"at": "说了"},
                                   {"at": "好几遍", "user": True, "keep": True}],
                          "collapse_at": "还是照旧", "summary_label": "最后一句", "stamp": {"text": "AI", "at": "真正"},
                          "worker": {"at": "真正要的", "label": "真正要的"}, "keep_at": "一个小时"}, "at": "同一个要求"},
            {"cross_check": {"left_label": "最后一句", "right_label": "真正要的",
                             "checker": {"label": "AI", "at": "最后一句"},
                             "rows": [{"at": "最后一句", "status": "ok"},
                                      {"at": "真正", "status": "missing", "status_at": "毛病", "note": "看不出来",
                                       "restore_at": "全打满"},
                                      {"at": "要的", "status": "changed", "status_at": "幻觉", "note": "开始幻觉"}]},
             "at": "最后一句"},
            {"lanes": {"lanes": [{"label": "流量", "at": "流量"}, {"label": "内存", "at": "内存"}],
                       "spawn": {"at": "内存", "node_text": "AI"}}, "at": "流量"},
            {"rail": [{"label": "清手机", "at": "清手机"}, "换电脑", "真用过"], "current": 0, "at": "清手机"},
            {"deck": [{"at": "毛病", "title": "看不出来", "body": [
                {"kind": "inspect", "rows": 3, "at": "毛病", "tick_at": "看不出来", "lens_at": "开始幻觉",
                 "wrong_at": "流量"},
                {"kind": "todo", "items": [{"text": "全打满", "at": "全打满", "tick_at": "注意力"},
                                           {"at": "流量", "absent": True, "ghost_at": "内存", "restore_at": "磁盘"}]},
                {"kind": "level", "steps": [["流量", .5], ["内存", .9, .4]], "limit": .9, "hit_at": "磁盘",
                 "blind_at": "全打满"}]}]},
        ]
        frag = self.build(elements, end=self.tl.duration)
        root = parse_fragment(frag)
        for el in root.iter():
            txt = "".join(el.itertext())
            if not el.get("data-glyph-times") or TEXT.find(txt) < 0:
                continue
            idx = TEXT.find(txt)
            for k, at in enumerate(json.loads(el.get("data-glyph-times"))):
                ct = self.tl.char_time(idx + k)
                if ct is not None:
                    self.assertGreaterEqual(at + 1e-6, ct, txt)
        late = [f for f in pages.unfinished(frag, self.tl.duration + 2) if not f[4]]
        self.assertEqual(late, [])

    def test_condense_kept_rows_wait_for_their_word(self):
        """挑中留进摘要的那几条，也要念到它才进来，不能一开页就挂在画面上。"""
        frag = self.build([{"condense": {"rows": [{"at": "同一个要求", "user": True},
                                                  {"at": "一整天", "user": True, "keep": True}],
                                         "collapse_at": "毛病",
                                         "worker": {"at": "看不出来", "label": "看不出来", "below": True}},
                            "at": "同一个要求"}])
        ins = [float(n.get("data-delay")) for n in parse_fragment(frag).iter() if n.get("data-anim") == "fade-up"]
        self.assertEqual(len(ins), 2)
        self.assertAlmostEqual(max(ins), pages.cue_time(self.tl, "一整天", 0)[0], places=3)

    def test_logo_replaces_side_dots_and_keeps_text_on_time(self):
        """代表某一方的圆点可换成标志图；名字照旧逐字、不早于念到，动画能放完；没写 logo 不出图。"""
        with tempfile.TemporaryDirectory() as d:
            Image.new("RGBA", (64, 64), (200, 100, 60, 255)).save(Path(d) / "brand.png")
            builder = pages.PageBuilder(self.tl, {"elements": []}, 0, 0, Path(d), end=self.tl.duration,
                                        brands={"x": "brand.png"})
            elements = [
                {"timeline": [{"label": "最后一句", "at": "最后一句", "logo": "x"}, {"label": "一个小时", "at": "一个小时"}],
                 "at": "最后一句"},
                {"tally": [{"label": "流量", "at": "流量", "value": 3, "logo": "x"}, {"label": "内存", "at": "内存", "value": 5}]},
                {"deck": [{"at": "毛病", "title": "看不出来", "title_at": "看不出来", "logo": "x",
                           "body": [{"kind": "comments", "items": [["流量", "流量", "x"], {"text": "内存", "at": "内存"}]}]}]},
                {"focus_network": {"nodes": [{"label": "真正要的", "at": "真正要的", "logo": "x"}],
                                   "visits": [{"node": 0, "at": "真正要的"}]}, "at": "最后一句"},
                {"cross_check": {"checker": {"label": "AI", "at": "最后一句", "logo": "x"},
                                 "rows": [{"at": "最后一句", "status": "ok"}]}, "at": "最后一句"},
                {"lanes": {"lanes": [{"label": "流量", "at": "流量"}, {"label": "内存", "at": "内存"}],
                           "spawn": {"at": "内存", "node_text": "AI", "logo": "x"}}, "at": "流量"},
                {"condense": {"rows": [{"at": "同一个要求", "user": True}], "collapse_at": "还是照旧",
                              "worker": {"at": "最后一句", "label": "最后一句", "logo": "x"}}, "at": "同一个要求"},
            ]
            for el in elements:
                builder.element(el)
            frag = "".join(builder.out + builder.mout)
        root = parse_fragment(frag)
        images = [n for n in root.iter() if n.tag.endswith("image")]
        self.assertEqual(len(images), 8)   # 时间线、条形、卡片、胶囊、网络、核对者、轨道、摘要工人各一
        for el in root.iter():
            txt = "".join(el.itertext())
            if not el.get("data-glyph-times") or TEXT.find(txt) < 0:
                continue
            idx = TEXT.find(txt)
            for k, at in enumerate(json.loads(el.get("data-glyph-times"))):
                ct = self.tl.char_time(idx + k)
                if ct is not None:
                    self.assertGreaterEqual(at + 1e-6, ct, txt)
        self.assertEqual([f for f in pages.unfinished(frag, self.tl.duration + 2) if not f[4]], [])
        plain = self.build([{"timeline": [{"label": "最后一句", "at": "最后一句"}], "at": "最后一句"}])
        self.assertNotIn("<image", plain)

    def test_missing_logo_fails(self):
        with self.assertRaises(FileNotFoundError):
            self.build([{"timeline": [{"label": "最后一句", "at": "最后一句", "logo": "no-such.png"}],
                         "at": "最后一句"}], base=Path(tempfile.gettempdir()))

    def test_rail_hides_labels_of_steps_not_reached(self):
        frag = self.build([{"rail": ["清手机", "换电脑", "真用过"], "current": 1, "at": "换电脑"}])
        shown = ["".join(el.itertext()) for el in parse_fragment(frag).iter() if el.get("data-glyph-times")]
        self.assertEqual(shown, ["清手机", "换电脑"])

    def test_tree_tiles_and_rail_logos_finish_and_stay_on_time(self):
        """分派树、卡片网格和进度轨的标志：字不早于念到，动画放完；讲过的步骤名不等后文同名字才出。"""
        with tempfile.TemporaryDirectory() as d:
            Image.new("RGBA", (64, 64), (200, 100, 60, 255)).save(Path(d) / "brand.png")
            builder = pages.PageBuilder(self.tl, {"elements": []}, 0, 0, Path(d), end=self.tl.duration,
                                        brands={"x": "brand.png"})
            for el in [
                {"tree": {"at": "同一个要求", "label": "注意力", "logo": "x", "children": [
                    {"at": "好几遍", "label": "最后一句", "logo": "x", "children": [{"at": "一个小时"}, {"at": "一整天"}]},
                    {"at": "毛病", "children": [{"at": "流量"}]}]},
                 "fold_at": "全打满", "return_at": "注意力", "result": {"text": "更全面", "at": "更全面"}},
                {"tiles": [{"title": "毛病", "at": "毛病", "logo": "x"}, {"title": "流量", "at": "流量"}]},
                {"rail": [{"label": "清手机", "logo": "x"}, {"label": "换电脑", "logo": "x"}], "current": 1,
                 "at": "毛病"},
            ]:
                builder.element(el)
            frag = "".join(builder.out + builder.mout)
        root = parse_fragment(frag)
        self.assertEqual(len([n for n in root.iter() if n.tag.endswith("image")]), 5)
        for el in root.iter():
            txt = "".join(el.itertext())
            if not el.get("data-glyph-times") or TEXT.find(txt) < 0:
                continue
            idx = TEXT.find(txt)
            for k, at in enumerate(json.loads(el.get("data-glyph-times"))):
                ct = self.tl.char_time(idx + k)
                if ct is not None and txt != "清手机":
                    self.assertGreaterEqual(at + 1e-6, ct, txt)
        done = next(el for el in root.iter() if el.get("data-glyph-times") and "".join(el.itertext()) == "清手机")
        self.assertLess(max(json.loads(done.get("data-glyph-times"))), pages.cue_time(self.tl, "清手机", 0)[0])
        self.assertEqual([f for f in pages.unfinished(frag, self.tl.duration + 2) if not f[4]], [])

    def test_bad_time_range_fails(self):
        with self.assertRaises(ValueError):
            self.build([{"time_stretch": {"start_label": "一个小时", "stretch_at": "一整天",
                         "end_label": "一整天", "end_at": "一个小时"}, "at": "一个小时"}])


if __name__ == "__main__":
    unittest.main()
