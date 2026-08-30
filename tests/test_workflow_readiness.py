# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock


os.environ["FISH_API_KEY"] = "test-only-placeholder"
_SECRET_STUB = types.ModuleType("secret_local")
_SECRET_STUB.FISH_API_KEY = "test-only-placeholder"
sys.modules["secret_local"] = _SECRET_STUB

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


class IndexedFileContractTests(unittest.TestCase):
    def test_indexed_files_accept_100_and_sort_numerically(self) -> None:
        from pipeline.indexed_files import indexed_files

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "script_100.txt").write_text("100", encoding="utf-8")
            (root / "script_99.txt").write_text("99", encoding="utf-8")

            indexed = indexed_files(str(root / "script_*.txt"))

            self.assertEqual([99, 100], list(indexed))
            self.assertEqual(
                ["script_99.txt", "script_100.txt"],
                [Path(path).name for path in indexed.values()],
            )

    def test_indexed_files_reject_noncanonical_or_unicode_names(self) -> None:
        from pipeline.indexed_files import indexed_files

        names = (
            "script_extra_03.txt",
            "script_2.txt",
            "script_001.txt",
            "script_٠١.txt",
            "script_00.txt",
        )
        for name in names:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / name).write_text("invalid", encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "indexed"):
                    indexed_files(str(root / "script_*.txt"))

    def test_indexed_files_reject_duplicate_indices(self) -> None:
        from pipeline.indexed_files import indexed_files

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "script_01.txt"
            path.write_text("one", encoding="utf-8")
            with mock.patch(
                "pipeline.indexed_files.glob.glob",
                return_value=[str(path), str(path)],
            ):
                with self.assertRaisesRegex(RuntimeError, "duplicate script index 01"):
                    indexed_files(str(path.parent / "script_*.txt"))

    def test_author_preflights_all_names_before_overwriting_prompts(self) -> None:
        from pipeline import author

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            timelines = root / "srt_data"
            prompts = root / "scene_html"
            scripts.mkdir()
            timelines.mkdir()
            prompts.mkdir()
            (scripts / "script_01.txt").write_text("valid", encoding="utf-8")
            (scripts / "script_001.txt").write_text("collision", encoding="utf-8")
            accepted = prompts / "prompt_01.txt"
            accepted.write_text("accepted prompt", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "non-canonical"):
                author.assemble_all(
                    str(scripts),
                    str(timelines),
                    assets=[],
                    out_dir=str(prompts),
                )

            self.assertEqual("accepted prompt", accepted.read_text(encoding="utf-8"))


class GenericProjectTests(unittest.TestCase):
    def test_author_prompt_uses_a_real_file_uri_for_assets(self) -> None:
        from pipeline.author import build_prompt

        with tempfile.TemporaryDirectory() as temporary:
            asset = Path(temporary) / "hero image.png"
            asset.write_bytes(b"png")

            prompt = build_prompt("旁白", str(Path(temporary) / "missing.json"), str(asset))

            self.assertIn(asset.resolve().as_uri(), prompt)
            self.assertNotIn("file:///绝对路径", prompt)

    def test_author_maps_three_sparse_scenes_to_real_timelines_and_assets(self) -> None:
        from pipeline import author

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            timelines = root / "srt_data"
            prompts = root / "scene_html"
            scripts.mkdir()
            timelines.mkdir()
            prompts.mkdir()
            assets = [root / "asset-a.png", root / "asset-b.png"]
            for asset in assets:
                asset.write_bytes(b"png")
            for index in (1, 3, 100):
                suffix = f"{index:02d}"
                (scripts / f"script_{suffix}.txt").write_text(
                    f"SCRIPT_{suffix}",
                    encoding="utf-8",
                )
                (timelines / f"srt_{suffix}.json").write_text(
                    json.dumps(
                        [{"word": f"TIMELINE_{suffix}", "start": 0.0, "end": 1.0}]
                    ),
                    encoding="utf-8",
                )

            author.assemble_all(
                str(scripts),
                str(timelines),
                assets=[str(asset) for asset in assets],
                out_dir=str(prompts),
            )

            self.assertEqual(
                ["prompt_01.txt", "prompt_03.txt", "prompt_100.txt"],
                sorted(path.name for path in prompts.glob("prompt_*.txt")),
            )
            for position, index in enumerate((1, 3, 100)):
                suffix = f"{index:02d}"
                prompt = (prompts / f"prompt_{suffix}.txt").read_text(encoding="utf-8")
                self.assertIn(f"SCRIPT_{suffix}", prompt)
                self.assertIn(f"TIMELINE_{suffix}", prompt)
                self.assertIn(assets[position % 2].resolve().as_uri(), prompt)
            self.assertFalse((prompts / "prompt_02.txt").exists())

    def test_author_removes_only_canonical_stale_prompts_on_rerun(self) -> None:
        from pipeline import author

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            timelines = root / "srt_data"
            prompts = root / "scene_html"
            scripts.mkdir()
            timelines.mkdir()
            prompts.mkdir()
            asset = root / "asset.png"
            asset.write_bytes(b"png")
            for index in (1, 2, 3):
                suffix = f"{index:02d}"
                (scripts / f"script_{suffix}.txt").write_text(
                    f"SCRIPT_{suffix}", encoding="utf-8"
                )
                (timelines / f"srt_{suffix}.json").write_text(
                    json.dumps(
                        [{"word": f"TIMELINE_{suffix}", "start": 0.0, "end": 1.0}]
                    ),
                    encoding="utf-8",
                )
            author.assemble_all(
                str(scripts), str(timelines), assets=[str(asset)], out_dir=str(prompts)
            )
            noncanonical = prompts / "prompt_2.txt"
            unrelated = prompts / "notes.txt"
            noncanonical.write_text("keep noncanonical", encoding="utf-8")
            unrelated.write_text("keep unrelated", encoding="utf-8")

            (scripts / "script_02.txt").unlink()
            (timelines / "srt_02.json").unlink()
            author.assemble_all(
                str(scripts), str(timelines), assets=[str(asset)], out_dir=str(prompts)
            )

            self.assertFalse((prompts / "prompt_02.txt").exists())
            self.assertEqual("keep noncanonical", noncanonical.read_text(encoding="utf-8"))
            self.assertEqual("keep unrelated", unrelated.read_text(encoding="utf-8"))

    def test_numeric_order_is_shared_by_pipeline_consumers(self) -> None:
        from pipeline import durations, fish_tts, merge, transcribe, workflow

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            audio = root / "audio"
            timelines = root / "timelines"
            output = root / "output"
            scripts.mkdir()
            audio.mkdir()
            timelines.mkdir()
            output.mkdir()
            for index in (100, 99):
                (scripts / f"script_{index}.txt").write_text(
                    f"SCRIPT_{index}", encoding="utf-8"
                )
                (audio / f"audio_{index}.mp3").write_bytes(str(index).encode("ascii"))

            with mock.patch.object(fish_tts, "synth_one") as synth:
                tts_outputs = fish_tts.synth_batch(str(scripts), str(audio))
            synth.assert_not_called()
            self.assertEqual(
                ["audio_99.mp3", "audio_100.mp3"],
                [Path(path).name for path in tts_outputs],
            )

            transcript_calls = []

            def record_transcript(audio_path: str, out_path: str) -> None:
                transcript_calls.append((Path(audio_path).name, Path(out_path).name))

            with mock.patch.object(
                transcribe,
                "transcribe_one",
                side_effect=record_transcript,
            ):
                transcribe.transcribe_batch(str(audio), str(timelines), force=True)
            self.assertEqual(
                [("audio_99.mp3", "srt_99.json"), ("audio_100.mp3", "srt_100.json")],
                transcript_calls,
            )

            durations_path = root / "durations.json"
            with mock.patch.object(
                durations,
                "probe_seconds",
                side_effect=lambda path: float(Path(path).stem.split("_")[-1]),
            ):
                values = durations.build(str(audio), str(durations_path))
            self.assertEqual([99.0, 100.0], values)

            captured = {}

            def capture_concat(command, check):
                list_path = Path(command[command.index("-i") + 1])
                captured["list"] = list_path.read_text(encoding="utf-8")
                return mock.Mock(returncode=0)

            with (
                mock.patch.object(merge.config, "DIR_OUTPUT", str(output)),
                mock.patch.object(merge.subprocess, "run", side_effect=capture_concat),
            ):
                merge.concat_audio(str(audio), str(output / "_main_audio.mp3"))
            self.assertLess(
                captured["list"].index("audio_99.mp3"),
                captured["list"].index("audio_100.mp3"),
            )
            self.assertEqual(
                [99, 100],
                list(workflow._indexed(str(audio / "audio_*.mp3"))),
            )

    def test_preview_pairs_numeric_scene_order_with_durations(self) -> None:
        from pipeline import preview

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenes = root / "scene_html"
            output = root / "output"
            scenes.mkdir()
            output.mkdir()
            (scenes / "scene_100.html").write_text("100", encoding="utf-8")
            (scenes / "scene_99.html").write_text("99", encoding="utf-8")
            durations_path = root / "durations.json"
            durations_path.write_text(json.dumps([99.0, 100.0]), encoding="utf-8")
            out = output / "preview.html"
            with (
                mock.patch.object(preview.config, "DIR_SCENE", str(scenes)),
                mock.patch.object(preview.config, "DIR_OUTPUT", str(output)),
                mock.patch.object(preview.config, "DURATIONS_JSON", str(durations_path)),
                mock.patch.object(preview.config, "PROJECT_TITLE", "Numeric Preview"),
                mock.patch.object(preview, "PREVIEW_BG", str(output / "_preview_bg.jpg")),
                mock.patch.object(preview, "_ensure_bg", return_value=None),
            ):
                preview.build(out=str(out))

            html = out.read_text(encoding="utf-8")
            scene_99 = 'scene_99.html?dur=99.000'
            scene_100 = 'scene_100.html?dur=100.000'
            self.assertIn(scene_99, html)
            self.assertIn(scene_100, html)
            self.assertLess(html.index(scene_99), html.index(scene_100))

    def test_lint_direct_entry_uses_numeric_scene_order(self) -> None:
        from pipeline import lint

        with tempfile.TemporaryDirectory() as temporary:
            scenes = Path(temporary)
            (scenes / "scene_100.html").write_text("100", encoding="utf-8")
            (scenes / "scene_99.html").write_text("99", encoding="utf-8")
            with mock.patch.object(lint.config, "DIR_SCENE", str(scenes)):
                paths = lint._default_scene_paths()
            self.assertEqual(
                ["scene_99.html", "scene_100.html"],
                [Path(path).name for path in paths],
            )

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
            output = StringIO()
            with redirect_stdout(output):
                init_project.init(str(target))
            self.assertTrue((target / "run.ps1").is_file())
            self.assertTrue((target / "v2lib.py").is_file())
            self.assertTrue((target / "tests" / "test_workflow_readiness.py").is_file())
            self.assertFalse((target / "build_v2.py").exists())
            self.assertFalse((target / "templates" / "cover_md.html").exists())
            self.assertFalse((target / "templates" / "cover_md_43.html").exists())
            next_steps = output.getvalue()
            self.assertIn(r"next: run: pwsh -File .\run.ps1 test", next_steps)
            self.assertIn(r"then: run: pwsh -File .\run.ps1 doctor", next_steps)
            self.assertLess(next_steps.index("run.ps1 test"), next_steps.index("doctor-live"))
            self.assertLess(next_steps.index("run.ps1 doctor"), next_steps.index("doctor-live"))

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
