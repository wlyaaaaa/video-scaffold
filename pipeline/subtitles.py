"""Optional global SRT/WebVTT sidecars; never burn subtitles into the video."""

import json
import os
from pathlib import Path
import config
from pipeline.io_utils import safe_print as print
from pipeline import contracts
from pipeline.io_utils import atomic_text


def timestamp(seconds, comma=True):
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{',' if comma else '.'}{ms:03d}"


def segments(words, offset=0.0, max_chars=24):
    groups = []
    current = []
    for word in words:
        if current and (
            len("".join(w["word"] for w in current)) + len(word["word"]) > max_chars
            or word["start"] - current[-1]["end"] > 0.8
        ):
            groups.append(current)
            current = []
        current.append(word)
        if word["word"].strip().endswith(("。", "！", "？", "!", "?")):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return [
        (
            group[0]["start"] + offset,
            group[-1]["end"] + offset,
            "".join(w["word"] for w in group).strip(),
        )
        for group in groups
    ]


def export():
    audio, words, durations = contracts.require_timings()
    cues = []
    offset = 0.0
    for path, duration in zip(words.values(), durations):
        cues.extend(
            segments(json.loads(Path(path).read_text(encoding="utf-8")), offset)
        )
        offset += duration
    srt = []
    vtt = ["WEBVTT\n"]
    cues = [cue for cue in cues if cue[1] > cue[0]]
    import html

    for index, (start, end, text) in enumerate(cues, 1):
        text = html.escape(text, quote=False)
        srt.append(f"{index}\n{timestamp(start)} --> {timestamp(end)}\n{text}\n")
        vtt.append(f"{timestamp(start, False)} --> {timestamp(end, False)}\n{text}\n")
    if not srt:
        raise RuntimeError("no timed words to export")
    for name, body in (("subtitles.srt", srt), ("subtitles.vtt", vtt)):
        path = os.path.join(config.DIR_OUTPUT, name)
        atomic_text(path, "\n".join(body))
        from pipeline.artifact_identity import write_output_record

        write_output_record(
            path + ".identity.json", contracts.subtitles_expected(), path
        )
        print(f"[subtitles] -> {path}")
    return cues
