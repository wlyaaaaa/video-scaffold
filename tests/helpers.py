"""Synthetic on-disk lineage graph for unit tests; never a real TTS acceptance."""

from contextlib import contextmanager, ExitStack
import json
from pathlib import Path
import shutil
import tempfile
from unittest import mock
import config
from pipeline import contracts, durations, fish_tts, transcribe, workflow
from pipeline.artifact_identity import write_output_record


@contextmanager
def project_graph(ids=(1, 4), duration=2.0):
    with tempfile.TemporaryDirectory() as temporary, ExitStack() as patches:
        root = Path(temporary)
        original = Path(config.ROOT)
        values = {
            "ROOT": str(root),
            "DIR_ASSETS": str(root / "assets"),
            "DIR_SCRIPTS": str(root / "scripts"),
            "DIR_AUDIO": str(root / "raw_audio"),
            "DIR_SRT": str(root / "srt_data"),
            "DIR_SCENE": str(root / "scene_html"),
            "DIR_OUTPUT": str(root / "output"),
            "DIR_RENDERED": str(root / "rendered"),
            "DURATIONS_JSON": str(root / "durations.json"),
            "BG_VIDEO": str(root / "background.mp4"),
            "BGM_PATH": str(root / "bgm.mp3"),
            "GPU_BROKER_URL": "",
            "PROJECT_TITLE": "Synthetic unit fixture",
            "FISH_MODEL": "unit-fixture",
            "FISH_REFERENCE_ID": "unit-fixture",
            "WHISPER_MODEL": "unit-fixture",
            "TIMING_SOURCE": "whisper",
        }
        for key, value in values.items():
            patches.enter_context(mock.patch.object(config, key, value))
        config.ensure_dirs()
        shutil.copytree(original / "templates", root / "templates")
        patches.enter_context(
            mock.patch.object(
                config, "TEMPLATE_BASE", str(root / "templates" / "scene_base.html")
            )
        )
        patches.enter_context(
            mock.patch.object(
                config, "TEMPLATE_COVER", str(root / "templates" / "cover_base.html")
            )
        )
        Path(config.BG_VIDEO).write_bytes(b"synthetic-background")
        for index in ids:
            text = f"测试{index}"
            (Path(config.DIR_SCRIPTS) / f"script_{index:02d}.txt").write_text(
                text, encoding="utf-8"
            )
            audio = str(Path(config.DIR_AUDIO) / f"audio_{index:02d}.mp3")
            Path(audio).write_bytes(f"synthetic-audio-{index}".encode())
            write_output_record(
                str(Path(config.DIR_AUDIO) / f"audio_{index:02d}.identity.json"),
                fish_tts._identity_record(
                    text, config.FISH_REFERENCE_ID, config.FISH_MODEL
                ),
                audio,
            )
            word = str(Path(config.DIR_SRT) / f"srt_{index:02d}.json")
            Path(word).write_text(
                json.dumps([{"word": text, "start": 0.2, "end": min(1.0, duration)}]),
                encoding="utf-8",
            )
            write_output_record(
                str(Path(config.DIR_SRT) / f"timing_{index:02d}.identity.json"),
                transcribe._identity_record(audio),
                word,
            )
            (Path(config.DIR_SCENE) / f"fragment_{index:02d}.svg").write_text(
                f'<text data-anim="fade" data-cue="{text}" data-delay="0" x="300" y="900">{text}</text>',
                encoding="utf-8",
            )
        with mock.patch.object(durations, "probe_seconds", return_value=duration):
            durations.build(config.DIR_AUDIO, config.DURATIONS_JSON)
        workflow.stage_build()
        video = str(root / "output" / "video_track.mp4")
        Path(video).write_bytes(b"synthetic-video")
        contracts.record_video(video, contracts.video_expected())
        final = str(root / "output" / "final_output.mp4")
        Path(final).write_bytes(b"synthetic-final")
        write_output_record(final + ".identity.json", contracts.final_expected(), final)
        cover = str(root / "output" / "cover.png")
        Path(cover).write_bytes(b"synthetic-cover")
        write_output_record(
            cover + ".identity.json",
            contracts.cover_expected(config.PROJECT_TITLE, "", "", None),
            cover,
        )
        (root / "chapters.json").write_text(
            json.dumps(
                [{"scene": ids[0], "title": "测试"}]
                + ([{"scene": ids[-1], "title": "末段"}] if len(ids) > 1 else [])
            ),
            encoding="utf-8",
        )
        workflow.stage_chapters()
        yield root


def media_probe(path, seconds=4.0, frames=240):
    if str(path).endswith(".png"):
        return {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "png",
                    "width": config.WIDTH,
                    "height": config.HEIGHT,
                }
            ],
            "format": {},
        }
    from pipeline.cleanup import _expected_codec

    return {
        "format": {"duration": str(seconds)},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": _expected_codec(),
                "width": config.WIDTH,
                "height": config.HEIGHT,
                "avg_frame_rate": f"{config.FPS}/1",
                "duration": str(seconds),
                "start_time": "0",
                "nb_read_packets": str(frames),
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "duration": str(seconds),
                "start_time": "0",
            },
        ],
    }
