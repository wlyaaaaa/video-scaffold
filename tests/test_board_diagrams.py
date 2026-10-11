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

    def test_bad_time_range_fails(self):
        with self.assertRaises(ValueError):
            self.build([{"time_stretch": {"start_label": "一个小时", "stretch_at": "一整天",
                         "end_label": "一整天", "end_at": "一个小时"}, "at": "一个小时"}])


if __name__ == "__main__":
    unittest.main()
