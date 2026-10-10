"""Optional global SRT/WebVTT sidecars (the delivery never burns subtitles in).

karaoke_ass() / playable_copy() are the opt-in extras for a burned-in review or
upload copy: an ASS file styled by the active page theme (config.PAGE_THEMES,
the word being spoken in the accent colour) and a 1080p H.264 copy that plays
everywhere. They do not touch final_output.mp4, delivery.json or its checks."""

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


PHRASE_BREAKS = "，。；：！？、,.;:!?…—"


def _ass_color(hex_color, alpha=0):
    c = hex_color.lstrip("#")
    return f"&H{alpha:02X}{c[4:6]}{c[2:4]}{c[0:2]}".upper()


def _ass_time(t):
    cs = max(0, round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _phrases(text, words):
    """Split the original text at punctuation and give each phrase its words.

    Words are matched to the text character by character (spaces and
    punctuation ignored on both sides), so multi-character TTS words work.
    """
    skip = set(PHRASE_BREAKS) | set(" 　\"'“”‘’（）()《》")
    chars = []  # (char, word index)
    for i, w in enumerate(words):
        chars += [(ch, i) for ch in w["word"] if ch not in skip]
    phrases, cur, k = [], [], 0
    for ch in text:
        if ch in PHRASE_BREAKS:
            if cur:
                phrases.append(cur)
            cur = []
            continue
        if ch in skip:
            cur.append((ch, None))
            continue
        if k >= len(chars) or chars[k][0] != ch:
            raise ValueError(f"subtitle text and words disagree at {ch!r} (word char {k})")
        cur.append((ch, chars[k][1]))
        k += 1
    if cur:
        phrases.append(cur)
    if k != len(chars):
        raise ValueError("subtitle text ends before the words do")
    return phrases


def karaoke_ass(text, words, duration=None, theme=None, play_res=(1920, 1080)):
    """ASS subtitles: one phrase (split at punctuation) at a time, the word being
    spoken in the theme's accent colour; styled only by the page theme.

    text keeps the original punctuation; words are [{word,start,end}] in the
    same clip's seconds. Each phrase stays until the next one starts (the last
    one until duration, or its own end).
    """
    th = theme if isinstance(theme, dict) else config.PAGE_THEMES[theme or config.PAGE_THEME]
    st = th["subtitle"]
    phrases = [p for p in _phrases(text, words) if any(i is not None for _, i in p)]
    on, off = _ass_color(st["active"]) + "&", _ass_color(st["color"]) + "&"
    events = []
    for n, ph in enumerate(phrases):
        ids = sorted({i for _, i in ph if i is not None})
        a = words[ids[0]]["start"]
        if n + 1 < len(phrases):
            b = words[min(i for _, i in phrases[n + 1] if i is not None)]["start"]
        else:
            b = duration if duration is not None else words[ids[-1]]["end"]
        cuts = sorted({a, b, *(min(max(words[i][k], a), b) for i in ids for k in ("start", "end"))})
        for x, y in zip(cuts, cuts[1:]):
            if y - x < 0.005:
                continue
            active = next((i for i in ids if words[i]["start"] <= x < words[i]["end"]), None)
            body = ""
            for ch, i in ph:
                ch = ch.replace("{", "(").replace("}", ")")
                hot = i is not None and i == active
                body += "{\\c" + on + "}" + ch + "{\\c" + off + "}" if hot else ch
            events.append(f"Dialogue: 0,{_ass_time(x)},{_ass_time(y)},Sub,,0,0,0,,{body}")
    w, h = play_res
    bold = -1 if st.get("bold") else 0
    head = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Sub,{st['font']},{st['size']},{_ass_color(st['color'])},{_ass_color(st['color'])},"
        f"{_ass_color(st['outline_color'])},{_ass_color(st['outline_color'], 0x73)},{bold},0,0,0,100,100,0,0,1,"
        f"{st['outline']},{st['shadow']},2,60,60,{st['margin_v']},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    return head + "\n".join(events) + "\n"


def playable_copy(video, out, ass=None, audio=None, crf=18):
    """1080p H.264 High@4.2 / yuv420p BT.709 / AAC / faststart copy that plays
    on any player; optionally burns an ASS file. audio defaults to the video's
    own track. Returns the ffmpeg argv for the caller to run."""
    vf = "scale=1920:1080:flags=lanczos"
    if ass:
        name = str(ass).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        vf += f",ass='{name}'"
    vf += ",setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv,format=yuv420p"
    argv = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(video)]
    if audio:
        argv += ["-i", str(audio)]
    argv += ["-map", "0:v:0", "-map", "1:a:0" if audio else "0:a:0?", "-vf", vf,
             "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-profile:v", "high",
             "-level:v", "4.2", "-pix_fmt", "yuv420p", "-color_primaries", "bt709",
             "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out)]
    return argv
