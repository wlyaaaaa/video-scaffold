"""分类网格及窗口压缩的词轴、完成时间与原语契约。"""
import json
import unittest

from pipeline import pages
from pipeline.build_scene import parse_fragment
from pipeline.subtitles import align_text


class TileTimingTests(unittest.TestCase):
    def setUp(self):
        self.text = "原话。分类。禁令。要求。自动摆到眼前。旧话压缩。"
        chars = [c for c in self.text if c != "。"]
        words = [dict(word=c, start=i * .4, end=i * .4 + .3) for i, c in enumerate(chars)]
        self.tl = pages.Timeline([], self.text, words, align_text(self.text, words), 12)

    def build(self, element):
        return pages.PageBuilder(self.tl, {"elements": [element]}, 0, 0, None).build()

    def test_tiles_follow_spoken_glyphs_and_finish_before_exit(self):
        frag = self.build(dict(tiles=[
            dict(title="禁令", at="分类", title_at="禁令", dark=True, lock_at="禁令",
                 lines=[dict(text="要求", at="要求")], move_at="自动", move_to=[800, 600]),
            dict(title="原话", at="原话", strike_at="旧话", dim_at="旧话")], cols=2))
        root = parse_fragment(frag)
        for el in root.iter():
            if el.get("data-glyph-times"):
                s = "".join(el.itertext())
                at = self.text.index(s)
                for k, t in enumerate(json.loads(el.get("data-glyph-times"))):
                    self.assertGreaterEqual(t + 1e-6, self.tl.char_time(at + k))
        self.assertEqual([], list(pages.unfinished(frag, 12)))
        self.assertTrue(list(pages.unfinished(frag, 6)))

    def test_context_collapse_is_finite_and_cannot_be_cut_off(self):
        frag = self.build(dict(cards=[dict(at="原话", body=[dict(kind="context_stack",
            items=[dict(at="原话", text="原话"), dict(at="要求", text="要求")],
            window_at="眼前", collapse_at="压缩")])]))
        root = parse_fragment(frag)
        tracks = [json.loads(n.get("data-keys")) for n in root.iter() if n.get("data-keys")]
        self.assertTrue(any(t[-1][-1] == 0 for t in tracks))
        self.assertEqual([], list(pages.unfinished(frag, 12)))
        cut = pages.cue_time(self.tl, "压缩", 0)[0] + .2
        self.assertTrue(list(pages.unfinished(frag, cut)))

    def test_bad_cue_and_invalid_columns_are_rejected(self):
        for el in [dict(tiles=[dict(title="禁令", at="缺失")]),
                   dict(tiles=[dict(title="禁令", at="禁令-0.2s")]),
                   dict(tiles=[dict(title="禁令", at="禁令")], cols=0)]:
            with self.assertRaises(ValueError):
                self.build(el)
