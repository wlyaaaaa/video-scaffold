# -*- coding: utf-8 -*-
"""
Stage 5 - audio concat + final mux.

Because every clip came from the same TTS batch they share a codec profile, so
the narration concatenates without re-encoding. We then mux it onto the rendered
4K video track to produce output/final_output.mp4.
"""

import os
import sys
import glob
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

FINAL = os.path.join(config.DIR_OUTPUT, "final_output.mp4")
TEMP_AUDIO = os.path.join(config.DIR_OUTPUT, "_main_audio.mp3")


def concat_audio(audio_dir=config.DIR_AUDIO, out_path=TEMP_AUDIO):
    audios = sorted(glob.glob(os.path.join(audio_dir, "audio_*.mp3")))
    if not audios:
        return None
    list_path = os.path.join(config.DIR_OUTPUT, "_audio_list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for a in audios:
            f.write(f"file '{os.path.abspath(a)}'\n")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", list_path,
                    "-c", "copy", out_path], check=True)
    os.remove(list_path)
    return out_path


def _probe_seconds(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=noprint_wrappers=1:nokey=1", path],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def mux(video_track, audio_track, out_path=FINAL, bgm_path=None):
    """Mux narration onto the video. If bgm_path is given (you supply the file),
    loop it under the narration with sidechain ducking so music dips while the
    voice speaks, plus a tail fade-out."""
    if bgm_path is None and os.path.exists(config.BGM_PATH):
        bgm_path = config.BGM_PATH

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", video_track]

    if audio_track and bgm_path:
        dur = _probe_seconds(audio_track)
        fade_st = max(0.0, dur - 1.2)
        # 0:v video, 1:a narration, 2:a music
        filt = (
            f"[2:a]aformat=channel_layouts=stereo,aloop=loop=-1:size=2147483647,"
            f"volume={config.BGM_VOLUME}[m];"
            f"[m][1:a]sidechaincompress=threshold=0.03:ratio=8:attack=5:release=300[md];"
            f"[1:a][md]amix=inputs=2:duration=first:normalize=0,"
            f"afade=t=out:st={fade_st:.2f}:d=1.2[aout]"
        )
        cmd += ["-i", audio_track, "-i", bgm_path,
                "-filter_complex", filt, "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    elif audio_track:
        cmd += ["-i", audio_track, "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    else:
        cmd += ["-c:v", "copy"]
    cmd.append(out_path)
    subprocess.run(cmd, check=True)
    tag = " + BGM(ducked)" if (audio_track and bgm_path) else ""
    print(f"[merge]{tag} -> {out_path}")
    return out_path


if __name__ == "__main__":
    audio = concat_audio()
    mux(os.path.join(config.DIR_OUTPUT, "video_track.mp4"), audio)
