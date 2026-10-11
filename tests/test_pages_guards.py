"""出片前读最终 SVG：提前出字、未完成动画，以及 plan 的只读路径。"""
import json
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from pipeline import boards, pages
from pipeline.subtitles import align_text


def timeline(text, duration=8):
    words = [dict(word=ch, start=i, end=i + .7) for i, ch in enumerate(text) if ch.isalnum()]
    return pages.Timeline([], text, words, align_text(text, words), duration)


class PageGuardsTests(unittest.TestCase):
    def project(self, base, tl, elements, **extra):
        spec = {'narration': [], 'pages': [{'elements': elements}], 'transition': 0, **extra}
        path = Path(base, 'table.json'); path.write_text(json.dumps(spec), encoding='utf-8')
        with patch.object(pages, 'load_timeline', return_value=tl):
            return pages.Project(path)

    def test_seg06_future_phrase_regression_blocks_actual_output_entrypoints(self):
        tl = timeline('先开场后续细则')
        def old_wrong_glyphs(ctx, plain, cue=None, start=None):
            return [ctx.at(cue) + i * .035 for i in range(len(plain))]
        with tempfile.TemporaryDirectory() as tmp:
            p = self.project(tmp, tl, [{'head': '后续细则', 'at': '先'}], pages=[
                {'from': '先', 'elements': [{'head': '后续细则', 'at': '先'}]},
                {'from': '后', 'elements': [{'head': '后续细则', 'at': '后'}]}])
            with patch.object(boards.Ctx, 'glyphs', old_wrong_glyphs):
                for entry in (p.plan, p.scenes, p.stills, p.render):
                    with self.subTest(entry=entry.__name__), self.assertRaisesRegex(ValueError, 'page 1.*“后”.*念到'):
                        entry()
            self.assertFalse(p.work.exists())

    def test_plan_checks_unfinished_and_preserves_reviewed_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.project(tmp, timeline('甲', 1), [{'title': '概括', 'at': '甲', 'dur': 2}])
            for entry in (p.plan, p.scenes):
                with self.assertRaisesRegex(ValueError, 'page 1.*动画没放完'):
                    entry()
            p.spec['pages'][0]['elements'][0]['hold_check'] = 'warn'
            with self.assertWarnsRegex(UserWarning, '已审定'):
                p.plan()
            self.assertFalse(p.work.exists())

    def test_plan_does_not_generate_background_or_decode_screen(self):
        from pipeline import board_diagrams
        with tempfile.TemporaryDirectory() as tmp, patch('v2lib.page_background', side_effect=AssertionError('write')):
            p = self.project(tmp, timeline('甲乙丙', 8), [{'screen': [
                {'at': '甲', 'clip': 'unused.mp4', 'from': 0, 'to': 1, 'crop': [0, 0, 640, 480]}], 'at': '甲'}])
            with patch.object(board_diagrams, '_video_dims', return_value=(640, 480)), \
                 patch.object(board_diagrams, '_clip_frames', side_effect=AssertionError('decode')), warnings.catch_warnings():
                warnings.simplefilter('ignore'); p.plan()
            self.assertFalse(p.work.exists())

    def test_final_svg_mutation_and_second_occurrence_use_real_source(self):
        b = pages.PageBuilder(timeline('甲甲'), {'elements': [{'head': '甲', 'at': '甲#2'}]}, 0, 0, None)
        frag = b.build()
        self.assertEqual([('甲', 0.0, 1)], list(pages.early_glyphs(frag, b)))
        # 修改最终 SVG 仍关联同一次原文，时间不是关联键或期望值。
        safe = frag.replace('data-delay="0"', 'data-delay="1"').replace('[0.0]', '[1.0]')
        self.assertEqual([], list(pages.early_glyphs(safe, b)))

    def test_summary_punctuation_replay_and_parent_visibility(self):
        b = pages.PageBuilder(timeline('甲，乙'), {'elements': []}, 0, 0, None)
        ctx = boards.Ctx(b)
        times = [0, 0, 0]
        b.record_glyphs('“乙”', '乙', None, False, times)
        svg = boards.text(ctx, '“乙”', 0, 0, 100, times)
        self.assertEqual([('乙', 0.0, 2)], list(pages.early_glyphs(svg, b)))
        self.assertEqual([], list(pages.early_glyphs(boards.anim('fade', 3, .3, svg), b)))
        b.record_glyphs('甲乙', '甲', None, True, times := [0, .035])
        self.assertEqual([], list(pages.early_glyphs(boards.text(ctx, '甲乙', 0, 1, 100, times), b)))
        replay = pages.PageBuilder(timeline('甲乙甲'), {'elements': []}, 1, 1, None)
        self.assertEqual([0], replay.glyph_reference('甲'))

    def test_joined_cues_keep_occurrence_and_keys_hidden_intervals(self):
        b = pages.PageBuilder(timeline('甲乙乙'), {'elements': [
            {'head': '甲', 'at': '甲', 'sub': [['乙', '乙#2']]}]}, 0, 0, None)
        self.assertEqual([('乙', 1.0, 2)], list(pages.early_glyphs(b.build(), b)))
        b = pages.PageBuilder(timeline('甲乙', 12), {'elements': []}, 0, 0, None)
        b.tl.words[1]['start'] = 8
        svg = '<text data-anim="type" data-delay="6" data-glyph-times="[6]">乙</text>'
        hidden = boards.keys([[0, 0, 0, 1, 1], [1, 0, 0, 1, 0], [10, 0, 0, 1, 0], [11, 0, 0, 1, 1]], svg)
        self.assertEqual([], list(pages.early_glyphs(hidden, b)))
        self.assertEqual([('乙', 6.0, 8)], list(pages.early_glyphs(svg, b)))


if __name__ == '__main__':
    unittest.main()
