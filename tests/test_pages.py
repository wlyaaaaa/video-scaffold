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
        t, _ = pages.cue_time(tl, "天#2+0.1s", 0)
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

    def test_page_builder_emits_smooth_elements_in_page_time(self) -> None:
        tl = _timeline(self.TEXT, self.SPOKEN)
        page = {"elements": [{"kicker": "开销", "at": "Claude"}, {"title": "烧掉的 *token*", "at": "烧了"},
                             {"bars": [{"label": "A", "value": 846, "text": "846 亿", "at": "846"},
                                       {"label": "B", "value": 3118.5, "accent": True}], "at":"846"},
                             {"old": "强得离谱", "at": "可我", "strike": "气到"},
                             {"bullets": [["一条", "天天"], ["二条", None]], "at": "天天"}]}
        frag = pages.PageBuilder(tl, page, 0.5, 0, None, progress=(5, 0, 0.2)).build()
        self.assertIn('data-step-fps="0"', frag)
        self.assertIn('data-delay="1.00"', frag)        # 烧 at 1.5s, page starts at 0.5s
        self.assertIn('data-dir="left"', frag)          # bar grows from the left, then holds
        self.assertNotIn("data-cue", frag)
        self.assertIn("#10A27E", frag.upper())

    def test_cues_never_fall_back_or_show_early(self) -> None:
        text = "GPT-6 发布的时候，总裁说，我们进入了 AGI 时代。"
        spoken = ["你", "好", "GPT", "6", "发", "布", "的", "时", "候", "总", "裁", "说", "我", "们", "进", "入", "了",
                  "AGI", "时", "代"]
        tl = _timeline(text, spoken[2:])
        self.assertAlmostEqual(0.0, pages.cue_time(tl, "GPT-6", 0)[0])   # 不再被读成“GPT”减 6 秒
        b = pages.PageBuilder(tl, {"elements": []}, 0.0, 0, None)
        with self.assertRaises(ValueError):
            b.element({"title": "没绑词"})
        with self.assertRaises(ValueError):
            b.element({"title": "找不到", "at": "没念过"})
        with self.assertRaises(ValueError):
            pages.cue_time(tl, "总裁-0.5s", 0)
        late = pages.PageBuilder(tl, {"elements": []}, 5.0, 0, None)
        with self.assertRaises(ValueError):
            late.element({"title": "上一页的词", "at": "GPT-6"})

    def test_subtitles_never_show_before_their_words(self) -> None:
        import re
        from pipeline.subtitles import karaoke_ass
        tl = _timeline(self.TEXT, self.SPOKEN)
        ass = karaoke_ass(tl.text, tl.words, duration=tl.duration, reveal=True)
        for line in [l for l in ass.splitlines() if l.startswith("Dialogue")]:
            start = line.split(",")[1]; h, m, sec = start.split(":")
            t = int(h) * 3600 + int(m) * 60 + float(sec)
            shown = re.sub(r"\{[^}]*\}", "", line.split(",,0,0,0,,", 1)[1])
            first = shown.strip()[0]
            spoken_at = tl.char_time(tl.text.find(first))
            self.assertGreaterEqual(t + 0.011, spoken_at)

    def test_speech_reveal_tracks_each_glyph_and_missing_cues_fail(self):
        import xml.etree.ElementTree as ET
        tl = _timeline("先说话，再出图。",list("先说话再出图"))
        frag = pages.PageBuilder(tl,{"elements":[{"title":"先说话","at":"先"}]},0,0,None).build()
        root = ET.fromstring('<svg>'+frag+'</svg>')
        text = root.find('.//text')
        self.assertEqual('type',text.get('data-anim'))
        self.assertEqual('[0.0, 0.5, 1.0]',text.get('data-glyph-times'))
        with self.assertRaises(ValueError):
            pages.cue_time(tl,'先-0.01s',0)

    def test_static_warning_ignores_progress_but_counts_real_motion(self):
        static = '<text data-anim="fade" data-delay="0" data-dur="0.5">A</text>'
        progress = '<rect data-anim="wipe" data-ease="linear" data-dur="10"/>'
        self.assertEqual([(0.5,10)],pages.motion_gaps(static+progress,10))
        self.assertEqual([],pages.motion_gaps(static+'<image data-anim="float"/>',10))

    def test_fragment_resolves_real_cues_without_fallback(self):
        import tempfile
        from pathlib import Path
        tl = _timeline('先说话，再出图。',list('先说话再出图'))
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'art.svg').write_text('<path data-anim="draw" data-cue="出图" data-dur="0.6" d="M0 0L10 10"/>')
            page = {'elements':[{'fragment':'art.svg','at':'先'}]}
            frag=pages.PageBuilder(tl,page,0,0,Path(tmp)).build()
            self.assertIn('data-delay="2.0"',frag)
            self.assertNotIn('data-cue=',frag)
            Path(tmp,'art.svg').write_text('<path data-anim="draw" data-cue="未说" d="M0 0L10 10"/>')
            with self.assertRaises(ValueError):
                pages.PageBuilder(tl,page,0,0,Path(tmp)).build()


if __name__ == "__main__":
    unittest.main()
