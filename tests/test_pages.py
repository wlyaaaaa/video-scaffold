# -*- coding: utf-8 -*-
"""图文页分镜表（pipeline.pages）：绑词、标记、折行、分页和整页片段。"""
from __future__ import annotations

import unittest

from pipeline import pages
from pipeline.subtitles import align_text


def _timeline(text, spoken):
    words = [{"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4} for i, w in enumerate(spoken)]
    return pages.Timeline([], text, words, align_text(text, words), len(words) * 0.5 + 0.6)


class PagesTests(unittest.TestCase):
    TEXT = "光 Claude 就烧了 846 亿 token。可我天天用，还是被它气到。"
    SPOKEN = ["光", "Claude", "就", "烧", "了", "八百四十六亿", "token", "可", "我", "天", "天", "用",
              "还", "是", "被", "它", "气", "到"]

    def test_cue_uses_shown_text_even_when_read_differently(self) -> None:
        tl = _timeline(self.TEXT, self.SPOKEN)
        self.assertEqual((2.5, self.TEXT.find("846")), pages.cue_time(tl, "846", 0))
        t, _ = pages.cue_time(tl, "天#2+0.1", 0)
        self.assertAlmostEqual(5.1, t)
        with self.assertRaises(ValueError):
            pages.cue_time(tl, "没说过", 0)

    def test_markup_and_wrap(self) -> None:
        spans = pages.markup("可我*天天用*，~旧说法~")
        self.assertEqual([("可我", None), ("天天用", "accent"), ("，", None), ("旧说法", "muted")], spans)
        lines = pages.wrap(pages.markup("Claude Code 一口气*写了很多很多*代码"), 100, 700)
        self.assertGreater(len(lines), 1)
        self.assertTrue(lines[0][0][0].startswith("Claude Code"))   # 英文单词不拆开
        self.assertEqual("Claude Code 一口气写了很多很多代码", "".join(t for ln in lines for t, _ in ln))

    def test_pages_split_before_first_cue_and_cover_the_whole_clip(self) -> None:
        tl = _timeline(self.TEXT, self.SPOKEN)
        spec = {"pages": [{"elements": [{"title": "烧掉的 token", "at": "烧了"}]},
                          {"elements": [{"big": "可我*天天用*", "at": "天天"}]}]}
        plan = pages.plan_pages(spec, tl)
        self.assertEqual(0.0, plan[0][0])
        self.assertAlmostEqual(4.5 - pages.PAGE_LEAD, plan[1][0])
        self.assertEqual(tl.duration, plan[-1][1])

    def test_page_builder_emits_held_elements_in_page_time(self) -> None:
        tl = _timeline(self.TEXT, self.SPOKEN)
        page = {"elements": [{"kicker": "开销"}, {"title": "烧掉的 *token*", "at": "烧了"},
                             {"bars": [{"label": "A", "value": 846, "text": "846 亿", "at": "846"},
                                       {"label": "B", "value": 3118.5, "accent": True}]},
                             {"old": "强得离谱", "at": "可我", "strike": "气到"},
                             {"bullets": [["一条", "天天"], ["二条", None]]}]}
        frag = pages.PageBuilder(tl, page, 1.0, 0, None, progress=(5, 0, 0.2)).build()
        self.assertIn('data-step-fps="12"', frag)
        self.assertIn('data-delay="0.50"', frag)        # 烧 at 1.5s, page starts at 1.0s
        self.assertIn('data-dir="left"', frag)          # bar grows from the left, then holds
        self.assertNotIn("data-cue", frag)
        self.assertIn("#10A27E", frag.upper())


if __name__ == "__main__":
    unittest.main()
