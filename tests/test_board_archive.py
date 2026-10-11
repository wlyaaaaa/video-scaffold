"""原话档案、分叉、翻档案三种图解，以及分类卡片的重现和恢复：词轴、完成时间与原语契约。"""
import json
import unittest

from pipeline import pages
from pipeline.build_scene import parse_fragment
from pipeline.subtitles import align_text


class ArchiveLayoutTests(unittest.TestCase):
    def setUp(self):
        self.text = "原样存档。只往后加。不改一个字。按月分卷。出了问题再翻。同样一句不要。意思完全不一样。派活。翻档案。自动摆到眼前。分类出处。项目规矩。禁令排前。随口问问。改掉。不算。看见了。"
        chars = [c for c in self.text if c != "。"]
        words = [dict(word=c, start=i * .3, end=i * .3 + .25) for i, c in enumerate(chars)]
        self.tl = pages.Timeline([], self.text, words, align_text(self.text, words), len(chars) * .3 + 2)

    def build(self, element):
        return pages.PageBuilder(self.tl, {"elements": [element]}, 0, 0, None).build()

    def glyphs_not_early(self, frag):
        for el in parse_fragment(frag).iter():
            if el.get("data-glyph-times"):
                s = "".join(el.itertext())
                at = self.text.find(s)
                if at < 0:
                    continue
                for k, t in enumerate(json.loads(el.get("data-glyph-times"))):
                    ct = self.tl.char_time(at + k)
                    if ct is not None:
                        self.assertGreaterEqual(t + 1e-6, ct, s)

    def test_archive_appends_locks_and_shelves(self):
        frag = self.build(dict(archive=dict(
            page_label="原样存档", entries=[dict(at="原样"), dict(at="只往后加"), dict(at="加")],
            lock_at="不改一个字", volumes=["8月", "9月", "10月"], volumes_at="按月分卷",
            pull=dict(index=1, at="出了问题")), at="原样存档"))
        kinds = {e.get("data-anim") for e in parse_fragment(frag).iter() if e.get("data-anim")}
        self.assertTrue({"keys", "grow-bar", "draw", "fade-up"} <= kinds)
        self.glyphs_not_early(frag)
        self.assertEqual([], list(pages.unfinished(frag, self.tl.duration)))
        cut = pages.cue_time(self.tl, "出了问题", 0)[0] + .1
        self.assertTrue(list(pages.unfinished(frag, cut)))

    def test_fork_copies_answer_and_shows_meanings(self):
        frag = self.build(dict(fork=dict(answer="“不要”", answer_at="不要", branches=[
            dict(at="同样", result="禁令", result_at="完全", accent=True),
            dict(at="意思", result="偏好", result_at="完全+0.2s")]), at="同样"))
        self.glyphs_not_early(frag)
        self.assertEqual([], list(pages.unfinished(frag, self.tl.duration)))

    def test_recall_sorts_strikes_and_drops(self):
        el = dict(recall=dict(
            actions=[dict(text="派活", at="派活")], task=dict(label="派活", at="派活"),
            archive=dict(at="翻档案", match_at="自动", exit_at="看见"),
            query=dict(at="翻档案", until="自动摆到"),
            items=[dict(tag="要求", src="出处", at="自动摆到", tag_at="分类", volume=2),
                   dict(tag="询问", at="自动摆到+0.2s", strike_at="随口问问", volume=1),
                   dict(tag="禁令", accent=True, at="自动摆到+0.4s", volume=0),
                   dict(kind="rules", text="项目规矩", at="项目规矩")],
            order=[2, 0, 1, 3], sort_at="禁令排前", drop_at="不算", seen_at="看见"), at="派活")
        frag = self.build(el)
        self.glyphs_not_early(frag)
        tracks = [json.loads(n.get("data-keys")) for n in parse_fragment(frag).iter() if n.get("data-keys")]
        self.assertTrue(any(t[-1][-1] == 0 for t in tracks))      # 划掉的那条最后掉出去
        self.assertEqual([], list(pages.unfinished(frag, self.tl.duration)))
        el["recall"]["sort_at"] = "派活"           # 排序早于原话飞到：时间倒走，直接报错
        with self.assertRaises(ValueError):
            self.build(el)

    def test_tiles_replay_and_undim(self):
        frag = self.build(dict(tiles=[
            dict(title="原样存档", at="不改一个字", accent=True),
            dict(title="只往后加", at="不改一个字", dim_at="按月分卷", undim_at="出了问题")], replay=True, cols=2))
        texts = [e for e in parse_fragment(frag).iter() if e.get("data-glyph-times")]
        first = pages.cue_time(self.tl, "不改一个字", 0)[0]
        for e in texts:     # 已经完整念过的原文，从新的 at 重现
            self.assertLess(max(json.loads(e.get("data-glyph-times"))), first + 1)
        tracks = [json.loads(n.get("data-keys")) for n in parse_fragment(frag).iter() if n.get("data-keys")]
        self.assertTrue(any(t[-1][-1] == 1 and len(t) > 3 for t in tracks))
        with self.assertRaises(ValueError):
            self.build(dict(tiles=[dict(title="要求", at="原样", dim_at="按月分卷", undim_at="只往后加")]))


if __name__ == "__main__":
    unittest.main()
