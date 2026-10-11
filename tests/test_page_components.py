# -*- coding: utf-8 -*-
"""手册图文页零件（v2lib）、drop/定格运行时和纸页静图背景的回归测试。"""
from __future__ import annotations

import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def _png(path: Path, w: int = 40, h: int = 30) -> None:
    raw = b"".join(b"\x00" + b"\xff\xff\xff" * w for _ in range(h))
    chunk = lambda tag, data: struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class PageComponentTests(unittest.TestCase):
    WORDS = [{"word": c, "start": i * 0.2, "end": i * 0.2 + 0.2} for i, c in enumerate("下面同一个要求它还是照旧")]

    def test_runtime_declares_drop_and_step_cadence(self) -> None:
        source = (ROOT / "templates" / "scene_base.html").read_text(encoding="utf-8")
        self.assertIn('case "drop"', source)
        self.assertIn("data-step-fps", source)
        self.assertIn("rec.shift ?? 40", source)  # fade-up 默认位移不变

    def test_page_fragment_resolves_cues_and_offsets(self) -> None:
        import v2lib as L
        from pipeline.build_scene import resolve_cues

        with tempfile.TemporaryDirectory() as temp:
            photo, cut = Path(temp) / "photo.png", Path(temp) / "cut.png"
            _png(photo, 40, 30); _png(cut, 20, 30)
            mx, my = L.image_point(str(cut), 100, 200, 300, 0.5, 0.2)
            self.assertEqual((mx, my), (200.0, 260.0))
            bx, by, bw, bh = L.bubble_bounds("Hi there", mx, my, size=50, tail=100)
            self.assertAlmostEqual(bx + bw + 100, mx)  # 尾巴尖正好落在嘴上
            fragment = "".join([
                L.step_fps(12),
                L.page_text("标题", 0, 100, 120, cue="下面"),
                L.number_row(["01", "02"], 0, 200, cue="下面"),
                L.mark_label("01", 0, 200, cue="同一个"),
                L.hand_line("说中文。", 0, 300, cue="要求", offset=0.2),
                L.tally(3, 0, 400, timings=[("要求", 0.1), ("要求", 0.3), 1.5]),
                L.photo_card(str(photo), 500, 300, 200, rotate=-3, cue="要求"),  # 倾斜的卡默认“落下”
                L.cutout(str(cut), 100, 200, 300, cue="它还"),
                L.speech_bubble("Hi there", mx, my, size=50, tail=100, cue="还是"),
                L.pen_circle(bx + bw / 2, by + bh / 2, bw / 2 + 20, bh / 2 + 20, cue="照旧", square=4),
            ])
            resolved = resolve_cues(fragment, self.WORDS)
        self.assertNotIn("data-cue-missing", resolved)
        self.assertIn('data-anim="drop"', resolved)
        self.assertIn('data-step-fps="12"', resolved)
        self.assertIn('data-delay="1.200"', resolved)   # 要求 1.0 + offset 0.2
        self.assertEqual(resolved.count('data-anim="draw"'), 4)  # 三笔“正” + 一个圈

    def test_theme_switch_restyles_without_changing_components(self) -> None:
        import config
        import v2lib as L

        def page():
            return (L.page_title([("五种", None), ("麻烦", "accent")], kicker="手册")
                    + L.speech_bubble("Hi", 500, 500) + L.pen_circle(0, 0, 10, 10) + L.progress(5, 0, 0.2))

        saved = config.PAGE_THEME
        try:
            L.use_theme("white-green")
            green = page()
            L.use_theme("paper-red")
            red = page()
            L.use_theme(dict(L.theme("white-green"), accent="#123456"))
            custom = page()
        finally:
            config.PAGE_THEME = saved
        self.assertIn('fill="#10A27E"', green)
        self.assertIn("HarmonyOS Sans SC", green)
        self.assertIn('fill="#C42A1F"', red)
        self.assertIn("Source Han Serif SC Heavy", red)
        self.assertIn('fill="#123456"', custom)
        self.assertNotIn("#10A27E", red)
        with self.assertRaises(KeyError):
            L.theme("no-such-theme")

    def test_page_layout_components_cue_and_hold(self) -> None:
        import v2lib as L
        from pipeline.build_scene import resolve_cues

        fragment = "".join([
            L.tag("CONFIRMED", 0, 0, cue="下面"),
            L.old_text("旧说法", 0, 200, 80, cue="下面", strike_cue="要求"),
            L.nav_list(["甲", "乙"], active=1, cue="同一个", active_cue="要求"),
            L.bullets([("一条", ("还是", 0.1)), ([("重点", "accent")], 2.0)]),
            L.figure("500", 0, 900, label="PRICE", unit="美元", cue="照旧"),
            L.quote_block(["一句话"], source="出处", cue="它还"),
            L.meter(4, 0, 1200, timings=[("要求", 0.0), 1.5]),
            L.time_axis(0, 1500, 3000, ticks=[(0, "08:00"), (1, "19:00")], cue="下面"),
            L.time_block(300, 400, 1500, 200, style="hatch", label="分会场", sub="11:15", cue="同一个"),
            L.card(0, 0, 400, 300, inner=L.page_text("卡", 20, 100, 60), cue="还是"),
        ])
        resolved = resolve_cues(fragment, self.WORDS)
        self.assertNotIn("data-cue-missing", resolved)
        self.assertIn("<pattern", resolved)
        self.assertIn('data-dir="down"', resolved)  # 时间块从轴向上长出
        self.assertNotIn('data-anim="float"', resolved)

    def test_type_keeps_coloured_spans_and_lint_accepts_page_motion(self) -> None:
        source = (ROOT / "templates" / "scene_base.html").read_text(encoding="utf-8")
        self.assertIn('ts.setAttribute("fill", fill)', source)
        from pipeline.build_scene import parse_fragment
        parse_fragment('<g data-step-fps="0"/><g data-anim="float"/><g data-anim="push"/>')

    def test_karaoke_ass_follows_theme_and_multichar_words(self) -> None:
        import config
        from pipeline import subtitles

        words = [{"word": "下面", "start": 0.0, "end": 0.4}, {"word": "这些", "start": 0.4, "end": 0.8},
                 {"word": "同一个", "start": 1.0, "end": 1.5}]
        ass = subtitles.karaoke_ass("下面这些：同一个。", words, duration=2.0, theme="white-green")
        self.assertIn("Style: Sub,HarmonyOS Sans SC,54,&H000C0C0C", ass)
        self.assertIn("{\\c&H007EA210&}这{\\c&H000C0C0C&}", ass)
        events = [line for line in ass.splitlines() if line.startswith("Dialogue")]
        self.assertTrue(events[0].endswith("{\\c&H007EA210&}下{\\c&H000C0C0C&}{\\c&H007EA210&}面{\\c&H000C0C0C&}这些"))
        self.assertIn("0:00:01.50,0:00:02.00,Sub,,0,0,0,,同一个", events[-1])
        red = subtitles.karaoke_ass("下面这些", words[:2], theme="paper-red")
        self.assertIn(config.PAGE_THEMES["paper-red"]["subtitle"]["font"], red)
        with self.assertRaises(ValueError):
            subtitles.karaoke_ass("完全不同的字", words[:2])

    def test_playable_copy_is_h264_high_42_faststart(self) -> None:
        from pipeline import subtitles

        argv = subtitles.playable_copy("in.mp4", "out.mp4", ass=r"E:\a b\s.ass", audio="a.wav")
        joined = " ".join(argv)
        for part in ("libx264", "-profile:v high", "-level:v 4.2", "yuv420p", "+faststart", "aac",
                     "scale=1920:1080", "ass='E\\:/a b/s.ass'", "-map 1:a:0"):
            self.assertIn(part, joined)

    def test_page_background_is_flat_theme_colour(self) -> None:
        import v2lib as L
        from PIL import Image

        with tempfile.TemporaryDirectory() as temp:
            path = L.page_background(Path(temp) / "bg" / "page.png", color="#F6F6F3", size=(8, 4))
            with Image.open(path) as im:
                self.assertEqual((8, 4), im.size)
                self.assertEqual({(0xF6, 0xF6, 0xF3)}, {im.getpixel((x, y)) for x in range(8) for y in range(4)})

    def test_square_circle_encloses_bubble_corners(self) -> None:
        import re
        import v2lib as L

        path = L.pen_circle(0, 0, 100, 40, square=4, spiral=0, sweep=360, rotate=0)
        pts = [tuple(map(float, p.split(","))) for p in re.findall(r"-?\d+\.\d,-?\d+\.\d", path)]
        self.assertTrue(any(x > 90 and y > 30 for x, y in pts))  # 角上比椭圆饱满

    def test_still_background_is_cover_fit_without_offset(self) -> None:
        from pipeline import render

        with mock.patch.object(render.config, "BG_VIDEO", "paper-page.png"):
            self.assertEqual(1.0, render._bg_duration())
            cmd = render._chunk_cmd(0.0, 1.0, "out.mp4")
        self.assertEqual(["-loop", "1"], cmd[cmd.index("-loop"):cmd.index("-loop") + 2])
        graph = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("force_original_aspect_ratio=increase", graph)
        self.assertNotIn("trim=start", graph)
        with mock.patch.object(render.config, "BG_VIDEO", "loop.mp4"):
            cmd = render._chunk_cmd(2.5, 1.0, "out.mp4")
        self.assertIn("-stream_loop", cmd)
        self.assertIn("trim=start=2.500", cmd[cmd.index("-filter_complex") + 1])


if __name__ == "__main__":
    unittest.main()
