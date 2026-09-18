"""Regression tests for shared speech routing without changing accepted narration."""

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import config
from helpers import project_graph
from pipeline import contracts, fish_tts, transcribe, workflow
from pipeline.artifact_identity import (
    read_record,
    write_record,
    write_output_record,
    sha256_file,
    validation_session,
    python_code_hash,
)
from pipeline.io_utils import atomic_json


class SpeechLinkageTests(unittest.TestCase):
    def test_native_tts_does_not_depend_on_selected_timeline(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "clip.mp3"
            response = mock.MagicMock(status_code=200)
            response.iter_lines.return_value = []
            words = [{"word": "测试", "start": 0.0, "end": 0.8}]

            def decode(_, handle):
                handle.write(b"fixture-mp3")
                return words

            with (
                mock.patch.object(config, "TIMING_SOURCE", "chinese-asr"),
                mock.patch.object(config, "FISH_NATIVE_TIMESTAMPS", True),
                mock.patch.object(
                    config, "get_fish_api_key", return_value="synthetic-test-value"
                ),
                mock.patch.object(
                    fish_tts.requests, "post", return_value=response
                ) as post,
                mock.patch("pipeline.fish_native.decode", side_effect=decode),
                mock.patch("pipeline.durations.probe_seconds", return_value=1.0),
                mock.patch.object(fish_tts, "_pad_tail"),
            ):
                self.assertTrue(fish_tts.synth_one("测试", str(out)))
            self.assertTrue(post.call_args.args[0].endswith("/stream/with-timestamp"))
            self.assertTrue(Path(str(out) + ".timestamps.json").is_file())

    def test_legacy_audio_accepts_each_timing_selection_without_retts(self):
        with project_graph() as root:
            audio = root / "raw_audio/audio_01.mp3"
            record_path = root / "raw_audio/audio_01.identity.json"
            record = read_record(record_path)
            record["schema"] = "video-scaffold.tts-artifact-identity.v1"
            record["timing_source"] = "whisper"
            write_record(record_path, record)
            before = audio.read_bytes()
            for source in ("auto", "fish", "chinese-asr"):
                with mock.patch.object(config, "TIMING_SOURCE", source):
                    self.assertIn(1, contracts.require_audio())
            self.assertEqual(before, audio.read_bytes())
            (root / "scripts/script_01.txt").write_text("改变了旁白", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "stale"):
                contracts.require_audio()

    def test_legacy_whisper_result_readback_loads_no_model(self):
        with project_graph() as root:
            audio = root / "raw_audio/audio_01.mp3"
            out = root / "srt_data/srt_01.json"
            record = root / "srt_data/timing_01.identity.json"
            write_output_record(
                record,
                {
                    "schema": "video-scaffold.word-timing-identity.v1",
                    "audio_sha256": sha256_file(audio),
                    "model": "large-v3",
                    "device": "cuda",
                    "compute": "float16",
                    "language": "zh",
                    "word_timestamps": True,
                },
                out,
            )
            with mock.patch.object(transcribe, "transcribe_one") as generate:
                transcribe.transcribe_batch(config.DIR_AUDIO, config.DIR_SRT)
                generate.assert_not_called()
            self.assertTrue(transcribe.identity_matches(audio, out, record))
            with mock.patch.object(config, "TIMING_SOURCE", "chinese-asr"):
                self.assertFalse(transcribe.identity_matches(audio, out, record))

    def test_chapters_require_durations_not_word_timestamps(self):
        with project_graph() as root:
            for path in (root / "srt_data").iterdir():
                path.unlink()
            workflow.stage_chapters()
            self.assertEqual(
                [1, 4], [x["scene_id"] for x in contracts.require_chapters()["scenes"]]
            )
            with self.assertRaisesRegex(RuntimeError, "word timelines"):
                contracts.require_timings()

    def test_duration_stage_never_calls_asr(self):
        with (
            project_graph() as root,
            mock.patch.object(transcribe, "transcribe_batch") as asr,
        ):
            with mock.patch("pipeline.durations.probe_seconds", return_value=2.0):
                workflow.stage_durations()
            asr.assert_not_called()

    def test_explicit_alignment_switch_preserves_audio(self):
        with project_graph() as root:
            before = {
                p.name: sha256_file(p) for p in (root / "raw_audio").glob("*.mp3")
            }

            def align(audio, text, staged):
                atomic_json(
                    str(staged) + ".producer.json",
                    {
                        "model_identity": {"fixture": True},
                        "lexical_truth_verified": False,
                        "exact_text_coverage": True,
                    },
                )
                return [{"word": text, "start": 0.2, "end": 1.0}]

            with (
                mock.patch.object(
                    transcribe, "_shared_alignment", side_effect=align
                ) as shared,
                mock.patch.object(fish_tts, "synth_one") as tts,
                mock.patch("pipeline.durations.probe_seconds", return_value=2.0),
                mock.patch.object(config, "TIMING_SOURCE", "auto"),
            ):
                workflow.stage_timing(source="chinese-asr", force=True)
                self.assertEqual(2, shared.call_count)
                tts.assert_not_called()
                contracts.require_timings()
            self.assertEqual(
                before,
                {p.name: sha256_file(p) for p in (root / "raw_audio").glob("*.mp3")},
            )

    def test_cancelled_alignment_preserves_previous_timeline(self):
        with project_graph() as root:
            old = (root / "srt_data/srt_01.json").read_bytes()
            with (
                mock.patch.object(config, "TIMING_SOURCE", "chinese-asr"),
                mock.patch.object(
                    transcribe,
                    "_shared_alignment",
                    side_effect=subprocess.TimeoutExpired("fixture", 1),
                ),
                self.assertRaises(subprocess.TimeoutExpired),
            ):
                transcribe.transcribe_batch(force=True)
            self.assertEqual(old, (root / "srt_data/srt_01.json").read_bytes())
            self.assertFalse(list((root / "srt_data").glob(".timing-*")))

    def test_invalid_native_record_is_not_silently_replaced_by_local_model(self):
        with project_graph() as root:
            (root / "raw_audio/audio_01.mp3.timestamps.json").write_text(
                "{}", encoding="utf-8"
            )
            with mock.patch.object(transcribe, "_shared_alignment") as align:
                with self.assertRaises(RuntimeError):
                    transcribe.transcribe_batch(force=True)
                align.assert_not_called()

    def test_missing_shared_adapter_does_not_generate_narration(self):
        with project_graph() as root:
            with (
                mock.patch.object(config, "CHINESE_ASR_ROOT", ""),
                mock.patch.object(config, "CHINESE_ASR_PYTHON", ""),
                mock.patch.object(config, "TIMING_SOURCE", "chinese-asr"),
                mock.patch.object(fish_tts, "synth_one") as tts,
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "Configure the existing ChineseASR"
                ):
                    transcribe.transcribe_batch(force=True)
                tts.assert_not_called()

    def test_shared_adapter_verifies_audio_and_supplied_text_binding(self):
        with project_graph() as root:
            fake_python = root / "fixture-python"
            fake_python.write_text("not executed")

            def response(command, **kwargs):
                dest = Path(command[command.index("--output") + 1])
                atomic_json(
                    dest,
                    {
                        "schema": "zh_asr.alignment-entry.v1",
                        "status": "succeeded",
                        "exact_text_coverage": True,
                        "audio_sha256": "not-this-audio",
                        "text_sha256": "wrong",
                    },
                )

            with (
                mock.patch.object(config, "CHINESE_ASR_ROOT", str(root)),
                mock.patch.object(config, "CHINESE_ASR_PYTHON", str(fake_python)),
                mock.patch.object(transcribe, "run", side_effect=response),
            ):
                with self.assertRaisesRegex(RuntimeError, "different audio or text"):
                    transcribe._shared_alignment(
                        str(root / "raw_audio/audio_01.mp3"),
                        "测试",
                        root / "srt_data/staged.json",
                    )

    def test_speech_controls_removed_without_deleting_real_bracketed_text(self):
        self.assertEqual(
            "今天[API]测试",
            transcribe.speech_text("(excited)今天[API][pause]测试(/excited)"),
        )

    def test_hash_reads_are_scoped_and_observe_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "data"
            path.write_bytes(b"first")
            import builtins

            original = builtins.open
            with mock.patch("builtins.open", wraps=original) as opening:
                with validation_session():
                    a = sha256_file(path)
                    self.assertEqual(a, sha256_file(path))
                    self.assertEqual(1, opening.call_count)
                    path.write_bytes(b"longer change")
                    self.assertNotEqual(a, sha256_file(path))
                sha256_file(path)
                self.assertEqual(3, opening.call_count)

    def test_nonexecuting_python_edits_do_not_invalidate_media(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "render.py"
            path.write_text('def f():\n    "doc"\n    return 1\n')
            before = python_code_hash(path)
            path.write_text('# a comment\ndef f( ):\n    "new docs"\n    return 1\n')
            self.assertEqual(before, python_code_hash(path))
            path.write_text("def f():\n    return 2\n")
            self.assertNotEqual(before, python_code_hash(path))

    def test_plain_tts_regeneration_drops_only_obsolete_native_sidecar(self):
        with project_graph() as root:

            def synth(text, path, **kwargs):
                Path(path).write_bytes(b"new plain narration")
                return True

            with (
                mock.patch.object(config, "FISH_NATIVE_TIMESTAMPS", False),
                mock.patch.object(fish_tts, "synth_one", side_effect=synth),
            ):
                fish_tts.synth_batch(
                    config.DIR_SCRIPTS,
                    config.DIR_AUDIO,
                    reference_id=config.FISH_REFERENCE_ID,
                    model=config.FISH_MODEL,
                    force=True,
                )
            self.assertFalse(list((root / "raw_audio").glob("*.timestamps.json")))
            self.assertEqual(
                "chinese-asr",
                transcribe._choose_source(root / "raw_audio/audio_01.mp3"),
            )

    def test_tts_stage_passes_current_project_config(self):
        with project_graph(), mock.patch.object(fish_tts, "synth_batch") as synth:
            workflow.stage_tts()
            synth.assert_called_once_with(
                config.DIR_SCRIPTS,
                config.DIR_AUDIO,
                reference_id=config.FISH_REFERENCE_ID,
                model=config.FISH_MODEL,
                force=False,
            )

    def test_empty_but_hash_bound_timeline_is_not_accepted(self):
        with project_graph() as root:
            out = root / "srt_data/srt_01.json"
            out.write_text("[]", encoding="utf-8")
            record = root / "srt_data/timing_01.identity.json"
            value = read_record(record)
            value["output_sha256"] = sha256_file(out)
            write_record(record, value)
            with self.assertRaisesRegex(RuntimeError, "empty"):
                contracts.require_timings()

    def test_video_has_no_local_whisper_runtime_dependency(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "pipeline/transcribe.py").read_text(encoding="utf-8")
        for word in (
            "import faster_whisper",
            "WhisperModel(",
            "import ctranslate2",
            "add_dll_directory",
        ):
            self.assertNotIn(word, source)
        requirements = (root / "requirements.txt").read_text(encoding="utf-8")
        for name in ("faster-whisper", "ctranslate2", "nvidia-", "moderngl", "numpy"):
            self.assertNotIn(name, requirements)
        self.assertFalse((root / "build_v2.py").exists())


if __name__ == "__main__":
    unittest.main()
