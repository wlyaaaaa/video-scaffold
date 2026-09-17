"""Sample-aligned narration assembly and atomic, non-truncating final mux."""

from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile
import config
from pipeline.io_utils import safe_print as print
from pipeline.indexed_files import indexed_files
from pipeline.io_utils import atomic_output, concat_entry, positive, run

FINAL = os.path.join(config.DIR_OUTPUT, "final_output.mp4")
TEMP_AUDIO = os.path.join(config.DIR_OUTPUT, "_main_audio.wav")


def _probe_seconds(path):
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        timeout=30,
    )
    return positive(float(result.stdout.strip()), "media duration")


def _normalize_audio(source, target, seconds):
    samples = round(positive(seconds, "narration duration") * 48000)
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            source,
            "-vn",
            "-af",
            f"aresample=48000,apad,atrim=end_sample={samples},asetpts=PTS-STARTPTS",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            target,
        ]
    )


def concat_audio(audio_dir=None, out_path=None):
    audio_dir = audio_dir or config.DIR_AUDIO
    out_path = out_path or os.path.join(config.DIR_OUTPUT, "_main_audio.wav")
    audios = indexed_files(os.path.join(audio_dir, "audio_*.mp3"))
    if not audios:
        return None
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".audio-", dir=Path(out_path).parent
    ) as temporary:
        clips = []
        for index, source in audios.items():
            target = str(Path(temporary) / f"audio_{index:02d}.wav")
            _normalize_audio(source, target, _probe_seconds(source))
            clips.append(target)
        listing = Path(temporary) / "concat.txt"
        listing.write_text(
            "".join(concat_entry(path) for path in clips), encoding="utf-8"
        )
        with atomic_output(out_path) as staged:
            codec = (
                ["-c:a", "pcm_s16le"]
                if Path(out_path).suffix.lower() == ".wav"
                else ["-c:a", "libmp3lame", "-q:a", "2"]
            )
            run(
                [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(listing),
                    *codec,
                    staged,
                ]
            )
    return out_path


def mux(video_track, audio_track, out_path=None, bgm_path=None):
    if not audio_track:
        raise RuntimeError("narration audio is missing; refusing silent delivery")
    out_path = out_path or os.path.join(config.DIR_OUTPUT, "final_output.mp4")
    video_seconds = _probe_seconds(video_track)
    audio_seconds = _probe_seconds(audio_track)
    if abs(video_seconds - audio_seconds) > max(0.05, 2 / config.FPS):
        raise RuntimeError(
            f"video/narration duration mismatch: {video_seconds:.3f}s vs {audio_seconds:.3f}s"
        )
    if bgm_path is None and os.path.isfile(config.BGM_PATH):
        bgm_path = config.BGM_PATH
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        video_track,
        "-i",
        audio_track,
    ]
    if bgm_path:
        fade = max(0.0, video_seconds - 1.2)
        filter_graph = (
            "[1:a]aformat=channel_layouts=stereo,asplit=2[nar][key];"
            f"[2:a]aformat=channel_layouts=stereo,volume={config.BGM_VOLUME}[music];"
            "[music][key]sidechaincompress=threshold=0.03:ratio=8:attack=5:release=300[duck];"
            "[nar][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95,"
            f"afade=t=out:st={fade:.6f}:d=1.2,apad,atrim=duration={video_seconds:.9f}[out]"
        )
        command += [
            "-stream_loop",
            "-1",
            "-i",
            bgm_path,
            "-filter_complex",
            filter_graph,
            "-map",
            "0:v:0",
            "-map",
            "[out]",
        ]
    else:
        command += [
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-af",
            f"apad,atrim=duration={video_seconds:.9f}",
        ]
    command += [
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
    ]
    with atomic_output(out_path) as staged:
        run(command + [staged], timeout=180)
    print(f"[merge] -> {out_path}")
    return out_path


if __name__ == "__main__":
    from pipeline.workflow import stage_merge
    from pipeline.io_utils import project_lock

    with project_lock(config.ROOT):
        stage_merge()
