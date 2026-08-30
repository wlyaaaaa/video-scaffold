# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


class CueAuditTests(unittest.TestCase):
    def test_missing_timeline_does_not_silently_drop_cues(self) -> None:
        from pipeline.build_scene import resolve_cues

        resolved = resolve_cues('<g data-cue="关键词" data-delay="0.4"></g>', [])

        self.assertIn('data-cue-missing="关键词"', resolved)
        self.assertIn('data-delay="0.4"', resolved)

    def test_missing_cue_remains_machine_auditable(self) -> None:
        from pipeline.build_scene import resolve_cues

        words = [{"word": "已经说出的词", "start": 0.0, "end": 1.0}]
        fragment = '<g data-cue="没有说出的词" data-delay="0.5"></g>'

        resolved = resolve_cues(fragment, words)

        self.assertIn('data-cue-missing="没有说出的词"', resolved)
        self.assertIn('data-delay="0.5"', resolved)


class DeliveryVerificationTests(unittest.TestCase):
    def _workspace(self, root: Path) -> tuple[Path, Path]:
        output = root / "output"
        scenes = root / "scene_html"
        output.mkdir()
        scenes.mkdir()
        (output / "final_output.mp4").write_bytes(b"video")
        (output / "cover.png").write_bytes(b"cover")
        (output / "chapters.txt").write_text("00:00 开场\n", encoding="utf-8")
        (scenes / "scene_01.html").write_text("<svg></svg>\n", encoding="utf-8")
        return output, scenes

    @staticmethod
    def _valid_probe(path: str) -> dict[str, object]:
        if path.endswith("cover.png"):
            return {
                "format": {"duration": None},
                "streams": [
                    {"codec_type": "video", "codec_name": "png", "width": 3840, "height": 2160}
                ],
            }
        return {
            "format": {"duration": "2.000000"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "av1",
                    "width": 3840,
                    "height": 2160,
                    "avg_frame_rate": "60/1",
                    "duration": "2.000000",
                },
                {"codec_type": "audio", "codec_name": "aac", "duration": "2.000000"},
            ],
        }

    def test_verify_accepts_a_complete_bilibili_delivery(self) -> None:
        from pipeline import cleanup

        with tempfile.TemporaryDirectory() as temporary:
            output, scenes = self._workspace(Path(temporary))
            with (
                mock.patch.object(cleanup.config, "DIR_OUTPUT", str(output)),
                mock.patch.object(cleanup.config, "DIR_SCENE", str(scenes)),
                mock.patch.object(cleanup.config, "PROJECT_TITLE", "Ready Video"),
                mock.patch.object(cleanup, "_ffprobe", side_effect=self._valid_probe, create=True),
            ):
                self.assertTrue(cleanup.verify())

    def test_verify_rejects_an_untitled_delivery(self) -> None:
        from pipeline import cleanup

        with tempfile.TemporaryDirectory() as temporary:
            output, scenes = self._workspace(Path(temporary))
            with (
                mock.patch.object(cleanup.config, "DIR_OUTPUT", str(output)),
                mock.patch.object(cleanup.config, "DIR_SCENE", str(scenes)),
                mock.patch.object(cleanup.config, "PROJECT_TITLE", "Untitled Video"),
                mock.patch.object(cleanup, "_ffprobe", side_effect=self._valid_probe, create=True),
            ):
                self.assertFalse(cleanup.verify())

    def test_verify_rejects_a_final_video_without_audio(self) -> None:
        from pipeline import cleanup

        def no_audio(path: str) -> dict[str, object]:
            probe = self._valid_probe(path)
            if path.endswith("final_output.mp4"):
                probe["streams"] = [probe["streams"][0]]  # type: ignore[index]
            return probe

        with tempfile.TemporaryDirectory() as temporary:
            output, scenes = self._workspace(Path(temporary))
            with (
                mock.patch.object(cleanup.config, "DIR_OUTPUT", str(output)),
                mock.patch.object(cleanup.config, "DIR_SCENE", str(scenes)),
                mock.patch.object(cleanup.config, "PROJECT_TITLE", "Ready Video"),
                mock.patch.object(cleanup, "_ffprobe", side_effect=no_audio, create=True),
            ):
                self.assertFalse(cleanup.verify())

    def test_verify_rejects_unresolved_cue_markers(self) -> None:
        from pipeline import cleanup

        with tempfile.TemporaryDirectory() as temporary:
            output, scenes = self._workspace(Path(temporary))
            (scenes / "scene_01.html").write_text(
                '<svg><g data-cue-missing="结果"></g></svg>\n', encoding="utf-8"
            )
            with (
                mock.patch.object(cleanup.config, "DIR_OUTPUT", str(output)),
                mock.patch.object(cleanup.config, "DIR_SCENE", str(scenes)),
                mock.patch.object(cleanup.config, "PROJECT_TITLE", "Ready Video"),
                mock.patch.object(cleanup, "_ffprobe", side_effect=self._valid_probe, create=True),
            ):
                self.assertFalse(cleanup.verify())


class GenericProjectTests(unittest.TestCase):
    def test_author_prompt_uses_a_real_file_uri_for_assets(self) -> None:
        from pipeline.author import build_prompt

        with tempfile.TemporaryDirectory() as temporary:
            asset = Path(temporary) / "hero image.png"
            asset.write_bytes(b"png")

            prompt = build_prompt("旁白", str(Path(temporary) / "missing.json"), str(asset))

            self.assertIn(asset.resolve().as_uri(), prompt)
            self.assertNotIn("file:///绝对路径", prompt)

    def test_author_preserves_sparse_scene_indices_and_timelines(self) -> None:
        from pipeline import author

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            timelines = root / "srt_data"
            prompts = root / "scene_html"
            scripts.mkdir()
            timelines.mkdir()
            prompts.mkdir()
            asset = root / "hero.png"
            asset.write_bytes(b"png")
            (scripts / "script_01.txt").write_text("第一场", encoding="utf-8")
            (scripts / "script_03.txt").write_text("第三场", encoding="utf-8")
            (timelines / "srt_01.json").write_text(
                json.dumps([{"word": "第一场", "start": 0.0, "end": 1.0}]),
                encoding="utf-8",
            )
            (timelines / "srt_03.json").write_text(
                json.dumps([{"word": "第三场", "start": 0.0, "end": 1.0}]),
                encoding="utf-8",
            )

            author.assemble_all(
                str(scripts),
                str(timelines),
                assets=[str(asset)],
                out_dir=str(prompts),
            )

            self.assertEqual(
                ["prompt_01.txt", "prompt_03.txt"],
                sorted(path.name for path in prompts.glob("prompt_*.txt")),
            )
            self.assertIn(
                "第三场",
                (prompts / "prompt_03.txt").read_text(encoding="utf-8"),
            )
            self.assertFalse((prompts / "prompt_02.txt").exists())

    def test_preview_uses_project_title_from_config(self) -> None:
        from pipeline import preview

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            scenes = root / "scene_html"
            output.mkdir()
            scenes.mkdir()
            durations = root / "durations.json"
            durations.write_text(json.dumps([1.0]), encoding="utf-8")
            (scenes / "scene_01.html").write_text("<svg></svg>\n", encoding="utf-8")
            out = output / "preview.html"
            with (
                mock.patch.object(preview.config, "DIR_OUTPUT", str(output)),
                mock.patch.object(preview.config, "DIR_SCENE", str(scenes)),
                mock.patch.object(preview.config, "DURATIONS_JSON", str(durations)),
                mock.patch.object(preview.config, "PROJECT_TITLE", "Workflow Acceptance", create=True),
                mock.patch.object(preview, "PREVIEW_BG", str(output / "_preview_bg.jpg")),
                mock.patch.object(preview, "_ensure_bg", return_value=None),
            ):
                preview.build(out=str(out))
            html = out.read_text(encoding="utf-8")
            self.assertIn("Workflow Acceptance · 全场景动态预览", html)
            self.assertNotIn("游戏王MD氪金指南", html)

    def test_init_project_copies_runtime_entry_and_component_library(self) -> None:
        import init_project

        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "fresh"
            init_project.init(str(target))
            self.assertTrue((target / "run.ps1").is_file())
            self.assertTrue((target / "v2lib.py").is_file())
            self.assertFalse((target / "build_v2.py").exists())
            self.assertFalse((target / "templates" / "cover_md.html").exists())
            self.assertFalse((target / "templates" / "cover_md_43.html").exists())

    def test_active_guides_have_no_retired_root_path(self) -> None:
        for relative in ("README.md", "docs/AI_GUIDE.md", "docs/AUTHORING.md"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn(r"E:\video", text, relative)
            self.assertNotIn("E:/video", text, relative)

    def test_config_defaults_are_topic_neutral(self) -> None:
        import config

        self.assertEqual(os.environ.get("VIDEO_PROJECT_TITLE", "Untitled Video"), config.PROJECT_TITLE)
        self.assertEqual(os.environ.get("WHISPER_INITIAL_PROMPT", ""), config.WHISPER_INITIAL_PROMPT)

    def test_doctor_module_exposes_local_preflight(self) -> None:
        from pipeline import doctor

        self.assertTrue(callable(doctor.run_checks))

    def test_doctor_distinguishes_busy_gpu_from_missing_nvenc(self) -> None:
        from pipeline import doctor

        completed = mock.Mock(
            returncode=1,
            stderr="CreateInputBuffer failed: out of memory (10)",
        )
        with (
            mock.patch.object(doctor, "_run", return_value=completed),
            mock.patch.object(doctor, "_gpu_memory_detail", return_value="1252 MiB free"),
        ):
            check = doctor._nvenc_check()

        self.assertEqual("BUSY", check.status)
        self.assertIn("1252 MiB free", check.detail)

    def test_existing_tts_audio_is_reused_unless_force_is_requested(self) -> None:
        from pipeline import fish_tts

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            audio = root / "audio"
            scripts.mkdir()
            audio.mkdir()
            (scripts / "script_01.txt").write_text("测试旁白", encoding="utf-8")
            accepted = audio / "audio_01.mp3"
            accepted.write_bytes(b"accepted")

            with mock.patch.object(fish_tts, "synth_one") as synth:
                outputs = fish_tts.synth_batch(str(scripts), str(audio))

            synth.assert_not_called()
            self.assertEqual([str(accepted)], outputs)

            with mock.patch.object(fish_tts, "synth_one", return_value=True) as synth:
                fish_tts.synth_batch(str(scripts), str(audio), force=True)
            synth.assert_called_once()

    def test_existing_word_timing_is_reused_unless_force_is_requested(self) -> None:
        from pipeline import transcribe

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audio = root / "audio"
            timelines = root / "timelines"
            audio.mkdir()
            timelines.mkdir()
            (audio / "audio_01.mp3").write_bytes(b"audio")
            accepted = timelines / "srt_01.json"
            accepted.write_text("[]", encoding="utf-8")

            with mock.patch.object(transcribe, "transcribe_one") as transcribe_one:
                transcribe.transcribe_batch(str(audio), str(timelines))
                transcribe_one.assert_not_called()
                transcribe.transcribe_batch(str(audio), str(timelines), force=True)
                transcribe_one.assert_called_once()

    def test_generic_workflow_exposes_every_delivery_stage(self) -> None:
        from pipeline import workflow

        expected = {
            "tts", "timing", "prompts", "build", "lint", "preview",
            "render", "merge", "cover", "chapters", "verify", "cleanup",
        }
        self.assertTrue(expected.issubset(workflow.STAGES))

    def test_generic_workflow_builds_reviewed_fragments_with_word_timing(self) -> None:
        from pipeline import workflow

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            scenes = root / "scene_html"
            timelines = root / "srt_data"
            scripts.mkdir()
            scenes.mkdir()
            timelines.mkdir()
            (scripts / "script_01.txt").write_text("先说核心结论", encoding="utf-8")
            (scenes / "fragment_01.svg").write_text(
                '<text data-cue="核心结论" data-delay="0.4">核心结论</text>',
                encoding="utf-8",
            )
            (timelines / "srt_01.json").write_text(
                json.dumps([{"word": "核心结论", "start": 0.75, "end": 1.2}]),
                encoding="utf-8",
            )
            with (
                mock.patch.object(workflow.config, "DIR_SCRIPTS", str(scripts)),
                mock.patch.object(workflow.config, "DIR_SCENE", str(scenes)),
                mock.patch.object(workflow.config, "DIR_SRT", str(timelines)),
            ):
                self.assertTrue(workflow.stage_build())

            built = (scenes / "scene_01.html").read_text(encoding="utf-8")
            self.assertIn('data-delay="0.750"', built)
            self.assertNotIn("data-cue-missing", built)

    def test_layout_lint_runtime_failure_is_blocking(self) -> None:
        from pipeline import lint

        def fail(coroutine):
            coroutine.close()
            raise RuntimeError("browser unavailable")

        with mock.patch.object(lint.asyncio, "run", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "layout lint could not run"):
                lint.lint(["scene_01.html"], [1.0])

    def test_chapters_must_start_at_scene_one_and_be_strictly_ordered(self) -> None:
        from pipeline import workflow

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "chapters.json"
            path.write_text(
                json.dumps([
                    {"scene": 2, "title": "第二段"},
                    {"scene": 1, "title": "开场"},
                ]),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "start at scene 1"):
                workflow._chapter_groups(str(path))

    def test_merge_refuses_to_create_a_silent_final_delivery(self) -> None:
        from pipeline import workflow

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "video_track.mp4").write_bytes(b"video")
            with (
                mock.patch.object(workflow.config, "DIR_OUTPUT", str(output)),
                mock.patch.object(workflow.merge, "concat_audio", return_value=None),
            ):
                with self.assertRaisesRegex(RuntimeError, "narration audio is missing"):
                    workflow.stage_merge()


if __name__ == "__main__":
    unittest.main()
