"""CPU postproduction for independently captured web works.

Narration is an existing audio file. This module never invokes or simulates TTS.
All clip and font paths are resolved relative to the timeline JSON.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import shutil
from fractions import Fraction

from PIL import Image, ImageDraw, ImageFont

from .common import probe, read_json, run, sha256, temp_workspace, tool, write_json


LOUDNESS = {"I": -14, "TP": -1.5, "LRA": 11}
_MEASURED = {"measured_I": "input_i", "measured_TP": "input_tp", "measured_LRA": "input_lra",
             "measured_thresh": "input_thresh", "offset": "target_offset"}


def _number(value, name, *, positive=False):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not math.isfinite(number) or number < 0 or (positive and number == 0):
        raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'} and finite")
    return number


def _input_path(value, base):
    if not isinstance(value, (str, os.PathLike)) or not str(value).strip():
        raise ValueError("media path must be nonempty")
    path = Path(value)
    path = (base / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _duration(info):
    candidates = [info.get("format", {}).get("duration")]
    candidates += [item.get("duration") for item in info.get("streams", [])]
    for value in candidates:
        try:
            seconds = float(value)
            if math.isfinite(seconds) and seconds > 0:
                return seconds
        except (ValueError, TypeError):
            pass
    raise ValueError("media has no finite positive duration")


def _streams(info, kind):
    return [stream for stream in info.get("streams", []) if stream.get("codec_type") == kind]


def _ffmpeg(*args, timeout=3600):
    return run([tool("ffmpeg"), "-hide_banner", "-nostdin", "-y", *map(str, args)], timeout=timeout)


def _frame_count(path):
    result = run([tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-count_frames",
                  "-show_entries", "stream=nb_read_frames", "-of", "json", str(path)], timeout=3600)
    try:
        return int(json.loads(result.stdout)["streams"][0]["nb_read_frames"])
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise RuntimeError(f"could not count decoded video frames: {path}") from error


def _frame_clock(path):
    result = run([tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_frames",
                  "-show_entries", "frame=best_effort_timestamp_time,duration_time,pkt_duration_time",
                  "-of", "json", str(path)], timeout=3600)
    frames = json.loads(result.stdout).get("frames", [])
    clock = []
    for frame in frames:
        try:
            timestamp = float(frame["best_effort_timestamp_time"])
            duration = float(frame.get("duration_time", frame.get("pkt_duration_time", 0)))
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"self-exported video has no usable frame timestamps: {path}") from error
        if not math.isfinite(timestamp) or not math.isfinite(duration) or duration < 0:
            raise ValueError(f"self-exported video has invalid frame timestamps: {path}")
        clock.append({"time": timestamp, "duration": duration})
    if not clock:
        raise ValueError(f"self-exported video has no decoded frames: {path}")
    origin = clock[0]["time"]
    for frame in clock:
        frame["time"] -= origin
    if any(second["time"] <= first["time"] for first, second in zip(clock, clock[1:])):
        raise ValueError(f"self-exported video frame timestamps must increase: {path}")
    return clock


def _audio_measure(path):
    result = _ffmpeg("-i", path, "-vn", "-af",
                     "volumedetect,loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-",
                     timeout=3600)
    stderr = result.stderr.decode("utf-8", "replace") if isinstance(result.stderr, bytes) else result.stderr
    blocks = re.findall(r"\{[^{}]*\}", stderr, re.S)
    loudness = None
    for block in reversed(blocks):
        try:
            candidate = json.loads(block)
        except ValueError:
            continue
        if "input_i" in candidate:
            loudness = candidate
            break
    if loudness is None:
        raise RuntimeError("FFmpeg did not return loudnorm measurement")
    volume = {}
    for key in ("mean_volume", "max_volume"):
        match = re.search(rf"{key}:\s*(-?inf|[-+\d.]+)\s*dB", stderr)
        if match:
            volume[key + "_db"] = match.group(1)
    return {"target": dict(LOUDNESS), "volume": volume, "loudnorm": loudness}


def _second_pass(measurement):
    values = measurement["loudnorm"]
    if all(math.isfinite(float(values[key])) for key in _MEASURED.values()):
        options = ":".join(f"{name}={values[key]}" for name, key in _MEASURED.items())
        return f"loudnorm=I=-14:TP=-1.5:LRA=11:{options}:linear=true:print_format=json"
    # Silence has -inf integrated loudness. A second dynamic pass preserves it,
    # instead of inventing finite measurements or claiming narration exists.
    return "loudnorm=I=-14:TP=-1.5:LRA=11:linear=false:print_format=json"


def _available_directory(path):
    path = Path(path).resolve()
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise FileExistsError(f"refusing to overwrite existing deliverables: {path}")
    return path


def _publish_directory(staged, target):
    _available_directory(target)
    target.mkdir(parents=True, exist_ok=True)
    for item in staged.iterdir():
        item.rename(target / item.name)


def _source(path, info=None):
    return {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size,
            **({"probe": info} if info is not None else {})}


def review(video, output_dir):
    """Create a complete review video, 12-frame sheet, waveform and audio report."""
    source = _input_path(video, Path.cwd())
    output = _available_directory(output_dir)
    info = probe(source)
    if not _streams(info, "video"):
        raise ValueError("review requires a video stream")
    duration = _duration(info)
    has_audio = bool(_streams(info, "audio"))
    source_record = _source(source, info)
    with temp_workspace(output.parent, ".webfilm-review-") as workspace:
        workspace = Path(workspace)
        staged = workspace / "delivery"
        staged.mkdir()
        try:
            source_fps = float(Fraction(_streams(info, "video")[0].get("avg_frame_rate", "0/1")))
        except (ValueError, ZeroDivisionError):
            source_fps = 0
        last_sample = max(0, duration - (1 / source_fps if source_fps > 0 else 0.05) - 0.000001)
        timestamps = [min((index + 0.5) * duration / 12, last_sample) for index in range(12)]
        sheet = Image.new("RGB", (4 * 480, 3 * 296), "#111820")
        drawing = ImageDraw.Draw(sheet)
        for index, timestamp in enumerate(timestamps):
            frame = workspace / f"frame-{index:02d}.png"
            _ffmpeg("-loglevel", "error", "-ss", f"{timestamp:.9f}", "-i", source,
                     "-frames:v", "1", "-vf", "scale=480:270:force_original_aspect_ratio=decrease,"
                     "pad=480:270:(ow-iw)/2:(oh-ih)/2:color=black", frame)
            with Image.open(frame) as extracted:
                sheet.paste(extracted.convert("RGB"), ((index % 4) * 480, (index // 4) * 296))
            drawing.text(((index % 4) * 480 + 10, (index // 4) * 296 + 275),
                         f"{index + 1:02d}  {timestamp:.3f} s", fill="white")
        sheet.save(staged / "contact-sheet.jpg", quality=92)
        if has_audio:
            audio = {"present": True, **_audio_measure(source)}
            _ffmpeg("-loglevel", "error", "-i", source, "-filter_complex",
                     "aformat=channel_layouts=stereo,showwavespic=s=1920x360:split_channels=1:colors=0x168256",
                     "-frames:v", "1", staged / "waveform.png")
        else:
            audio = {"present": False, "reason": "source has no audio stream"}
            waveform = Image.new("RGB", (1920, 360), "#f5f7f6")
            ImageDraw.Draw(waveform).text((24, 24), "Source has no audio stream", fill="#253d31")
            waveform.save(staged / "waveform.png")
        copied_video = staged / ("full-video" + source.suffix.lower())
        try:
            os.link(source, copied_video)
            copy_mode = "hardlink"
        except OSError:
            shutil.copy2(source, copied_video)
            copy_mode = "copy"
        write_json(staged / "audio.json", audio)
        record = {"schema": "webfilm.review.v1", "source": source_record, "duration": duration,
                  "frame_samples": timestamps, "full_video": copied_video.name, "copy_mode": copy_mode,
                  "audio": audio, "frame_count": _frame_count(source),
                  "outputs": {item.name: sha256(item) for item in staged.iterdir() if item.is_file()}}
        (staged / "review.md").write_text(
            f"# 视频审阅包\n\n完整视频：[{copied_video.name}]({copied_video.name})\n\n"
            f"时长：{duration:.3f} 秒；解码帧数：{record['frame_count']}。\n\n"
            "![十二帧拼图](contact-sheet.jpg)\n\n![声音波形](waveform.png)\n\n"
            f"声音：{'存在源音轨；测量结果见 audio.json。' if has_audio else '原视频没有声音轨。'}\n\n"
            "请完整播放视频并检查声音、字幕与前后衔接。自动测量只说明媒体结构与响度，不能替代人工观看和听音。\n"
            "此目录是本地审阅包，尚未投稿或发布。\n", encoding="utf-8")
        record["outputs"]["review.md"] = sha256(staged / "review.md")
        write_json(staged / "identity.json", record)
        if sha256(source) != source_record["sha256"]:
            raise RuntimeError("review source changed during extraction")
        _publish_directory(staged, output)
    return {"output_dir": str(output), "report": str(output / "review.md"), "identity": record}


def _font(path, base):
    if path:
        return _input_path(path, base)
    candidates = [os.environ.get("WEBFILM_FONT"), r"C:\Windows\Fonts\msyh.ttc",
                  r"C:\Windows\Fonts\simhei.ttf", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    raise FileNotFoundError("subtitle font not found; set timeline.subtitle_font to an existing font")


def _subtitle_png(text, target, width, height, font_path):
    font_size = max(12, round(height * 0.043))
    stroke = max(1, round(height * 0.002))
    while font_size >= 8:
        font = ImageFont.truetype(str(font_path), font_size)
        lines = []
        for paragraph in text.split("\n"):
            current = ""
            for char in paragraph:
                if current and font.getlength(current + char) > width * 0.88:
                    lines.append(current)
                    current = char
                else:
                    current += char
            lines.append(current)
        spacing = max(2, font_size // 5)
        band_height = len(lines) * (font_size + spacing) + stroke * 4 + 8
        if band_height <= height * 0.35:
            break
        font_size -= 1
    else:
        raise ValueError("subtitle text cannot fit in the subtitle area")
    canvas = Image.new("RGBA", (width, band_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    for index, line in enumerate(lines):
        draw.text((width // 2, stroke * 2 + 4 + index * (font_size + spacing)), line,
                  font=font, anchor="mt", fill="white", stroke_width=stroke, stroke_fill="black")
    canvas.save(target)
    return band_height


def _label_png(text, target, width, height, font_path):
    font_size = max(10, round(height * 0.022))
    font = ImageFont.truetype(str(font_path), font_size)
    while font.getlength(text) > width * 0.96 and font_size > 6:
        font_size -= 1
        font = ImageFont.truetype(str(font_path), font_size)
    if font.getlength(text) > width * 0.96:
        raise ValueError("clip label cannot fit in the header")
    band = max(font_size + 6, round(height * 0.045))
    canvas = Image.new("RGBA", (width, band), (0, 0, 0, 155))
    ImageDraw.Draw(canvas).text((round(width * 0.02), band // 2), text, font=font, anchor="lm", fill="white")
    canvas.save(target)


def _prepare_timeline(timeline, base, fps):
    if not isinstance(timeline, dict) or not isinstance(timeline.get("clips"), list) or not timeline["clips"]:
        raise ValueError("timeline.clips must be a nonempty list")
    result, sources, frame_clocks = [], {}, {}
    for index, clip in enumerate(timeline["clips"]):
        if not isinstance(clip, dict):
            raise ValueError(f"clip {index + 1} must be an object")
        duration = _number(clip.get("duration"), f"clip {index + 1} duration", positive=True)
        self_exported = clip.get("self_exported", False)
        if not isinstance(self_exported, bool):
            raise ValueError("clip.self_exported must be boolean")
        frames = round(duration * fps)
        if frames < 1 and not self_exported:
            raise ValueError(f"clip {index + 1} is shorter than one output frame")
        effective = frames / fps
        start = _number(clip.get("start", 0), "clip start")
        if "path" in clip and ("left" in clip or "right" in clip):
            raise ValueError("a clip must have either path or left and right")
        if "path" in clip:
            raw_views = [clip["path"]]
        elif "left" in clip and "right" in clip:
            raw_views = [clip["left"], clip["right"]]
        else:
            raise ValueError("a clip must provide path or both left and right")
        if self_exported and len(raw_views) != 1:
            raise ValueError("self_exported clips preserve one source frame clock; use a single path")
        views = []
        source_frame_times, native_fps = None, None
        for value in raw_views:
            source_start = start
            if isinstance(value, dict):
                source_start = _number(value.get("start", start), "view start")
                value = value.get("path")
            path = _input_path(value, base)
            info = probe(path)
            if not _streams(info, "video"):
                raise ValueError(f"clip source has no video stream: {path}")
            if source_start + (duration if self_exported else effective) > _duration(info) + 1 / fps:
                raise ValueError(f"clip duration exceeds source video: {path}")
            if self_exported:
                stream = _streams(info, "video")[0]
                try:
                    native_rate = Fraction(stream.get("avg_frame_rate", "0/1"))
                except (ValueError, ZeroDivisionError) as error:
                    raise ValueError(f"self-exported video has invalid frame rate: {path}") from error
                native_fps = str(native_rate)
                if str(path) not in frame_clocks:
                    frame_clocks[str(path)] = _frame_clock(path)
                selected = [frame for frame in frame_clocks[str(path)]
                            if frame["time"] >= source_start - 0.000001
                            and frame["time"] < source_start + duration - 0.000001]
                if not selected:
                    raise ValueError("self-exported clip interval contains no source frames")
                frames = len(selected)
                origin = selected[0]["time"]
                source_frame_times = [frame["time"] - origin for frame in selected]
                tail_duration = selected[-1]["duration"]
                if tail_duration <= 0:
                    tail_duration = (source_frame_times[-1] - source_frame_times[-2] if frames > 1
                                     else float(1 / native_rate) if native_rate > 0 else 0)
                if tail_duration <= 0:
                    raise ValueError("self-exported last frame has no duration")
                # Source timestamps are retained on a shared 1/60000 clock.
                effective = round((source_frame_times[-1] + tail_duration) * 60000) / 60000
            sources[str(path)] = _source(path, info)
            views.append({"path": path, "start": source_start, "audio": bool(_streams(info, "audio"))})
        narration = None
        if clip.get("narration") is not None:
            value = clip["narration"]
            narration_start = 0
            if isinstance(value, dict):
                narration_start = _number(value.get("start", 0), "narration start")
                value = value.get("path")
            path = _input_path(value, base)
            info = probe(path)
            if not _streams(info, "audio"):
                raise ValueError(f"narration has no audio stream: {path}")
            narration_duration = _duration(info)
            if narration_start >= narration_duration:
                raise ValueError(f"narration start is outside its audio duration: {path}")
            remaining = narration_duration - narration_start
            sources[str(path)] = _source(path, info)
            narration = {"path": path, "start": narration_start, "source_duration": narration_duration,
                         "remaining_duration": remaining, "padding_seconds": max(0, effective - remaining)}
        cues = clip.get("subtitles", clip.get("cues", clip.get("subtitle", [])))
        if isinstance(cues, str):
            cues = [{"start": 0, "end": effective, "text": cues}]
        if isinstance(cues, dict):
            cues = cues["cues"] if "cues" in cues else [cues]
        if cues is None:
            cues = []
        if not isinstance(cues, list):
            raise ValueError("clip subtitles must be a list of cues")
        parsed_cues = []
        for cue in cues:
            if not isinstance(cue, dict) or not isinstance(cue.get("text"), str) or not cue["text"].strip():
                raise ValueError("subtitle cue requires nonempty text")
            cue_start = _number(cue.get("start"), "subtitle start")
            cue_end = _number(cue.get("end"), "subtitle end", positive=True)
            if cue_end <= cue_start or cue_end > effective + 1 / fps:
                raise ValueError("subtitle cue must have start < end within the clip")
            parsed_cues.append({"start": cue_start, "end": min(cue_end, effective), "text": cue["text"]})
        label = clip.get("label")
        if label is None and self_exported:
            label = "模型自行导出"
        if label is not None and (not isinstance(label, str) or not label.strip()):
            raise ValueError("clip.label must be nonempty text")
        result.append({"views": views, "narration": narration, "cues": parsed_cues, "frames": frames,
                       "duration": effective, "requested_duration": duration, "label": label,
                       "self_exported": self_exported, "native_fps": native_fps,
                       "source_frame_times": source_frame_times})
    return result, list(sources.values())


def _render_segment(clip, index, workspace, width, height, fps, font_path):
    command, graph = [], []
    duration = clip["duration"]
    for view in clip["views"]:
        command += ["-ss", f"{view['start']:.9f}", "-i", str(view["path"])]
    panes = [width] if len(clip["views"]) == 1 else [(width // 4) * 2, width - (width // 4) * 2]
    if 0 in panes:
        raise ValueError("side-by-side output width must be at least four pixels")
    for source_index, pane_width in enumerate(panes):
        rate_filter = "" if clip["self_exported"] else f"fps={fps},"
        graph.append(f"[{source_index}:v:0]trim=duration={duration:.9f},setpts=PTS-STARTPTS,"
                     f"{rate_filter}scale={pane_width}:{height}:force_original_aspect_ratio=decrease,"
                     f"pad={pane_width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[v{source_index}]")
    if len(panes) == 2:
        graph.append("[v0][v1]hstack=inputs=2[base]")
        video_label = "base"
    else:
        video_label = "v0"
    next_input = len(clip["views"])
    audio_inputs = [i for i, view in enumerate(clip["views"]) if view["audio"]]
    if clip["narration"]:
        narration = clip["narration"]
        command += ["-ss", f"{narration['start']:.9f}", "-i", str(narration["path"])]
        audio_inputs = [next_input]
        next_input += 1
    if clip["label"]:
        png = workspace / f"label-{index:04d}.png"
        _label_png(clip["label"], png, width, height, font_path)
        command += ["-loop", "1", "-framerate", str(fps), "-i", str(png)]
        graph.append(f"[{video_label}][{next_input}:v:0]overlay=x=0:y=0:shortest=1[header]")
        video_label = "header"
        next_input += 1
    for cue_index, cue in enumerate(clip["cues"]):
        png = workspace / f"subtitle-{index:04d}-{cue_index:04d}.png"
        band = _subtitle_png(cue["text"], png, width, height, font_path)
        command += ["-loop", "1", "-framerate", str(fps), "-i", str(png)]
        target = f"sub{cue_index}"
        graph.append(f"[{video_label}][{next_input}:v:0]overlay=x=0:y={height - band - round(height * 0.05)}:"
                     f"enable='gte(t,{cue['start']:.9f})*lt(t,{cue['end']:.9f})':shortest=1[{target}]")
        video_label = target
        next_input += 1
    samples = round(duration * 48000)
    for audio_index, source_index in enumerate(audio_inputs):
        graph.append(f"[{source_index}:a:0]aresample=48000,aformat=sample_fmts=s16:channel_layouts=stereo,"
                     f"apad,atrim=end_sample={samples},asetpts=PTS-STARTPTS[a{audio_index}]")
    if len(audio_inputs) > 1:
        graph.append("".join(f"[a{i}]" for i in range(len(audio_inputs))) +
                     f"amix=inputs={len(audio_inputs)}:normalize=1:duration=longest[audio]")
        audio_label = "audio"
    elif audio_inputs:
        audio_label = "a0"
    else:
        graph.append(f"anullsrc=r=48000:cl=stereo,atrim=end_sample={samples},asetpts=PTS-STARTPTS[audio]")
        audio_label = "audio"
    video = workspace / f"segment-{index:04d}.mp4"
    audio = workspace / f"segment-{index:04d}.wav"
    copy_video = False
    if len(clip["views"]) == 1 and not clip["self_exported"] and not clip["cues"] and not clip["label"]:
        view = clip["views"][0]
        source_info = probe(view["path"])
        source_video = _streams(source_info, "video")[0]
        try:
            copy_video = (view["start"] == 0 and source_video.get("codec_name") == "h264"
                          and source_video.get("pix_fmt") == "yuv420p"
                          and (source_video.get("width"), source_video.get("height")) == (width, height)
                          and Fraction(source_video.get("avg_frame_rate", "0/1")) == fps
                          and Fraction(source_video.get("r_frame_rate", "0/1")) == fps
                          and abs(float(source_video.get("start_time", 0))) < 1 / 60000
                          and abs(float(source_video.get("duration", _duration(source_info))) - duration) < 1 / 60000)
        except (ValueError, TypeError, ZeroDivisionError):
            copy_video = False
    if copy_video:
        _ffmpeg("-loglevel", "error", "-i", clip["views"][0]["path"], "-map", "0:v:0", "-an",
                 "-c:v", "copy", "-video_track_timescale", "60000", "-movflags", "+faststart", video)
        # One undecorated view contributes exactly the graph's first item.
        # Exclude that item so this invocation decodes only the audio streams.
        _ffmpeg("-loglevel", "error", *command, "-filter_complex", ";".join(graph[1:]),
                 "-map", f"[{audio_label}]", "-vn", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
                 "-t", f"{duration:.9f}", audio)
        clip["video_processing"] = "stream_copy"
    else:
        _ffmpeg("-loglevel", "error", *command, "-filter_complex", ";".join(graph),
                 "-map", f"[{video_label}]", "-an", "-frames:v", str(clip["frames"]),
                 "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                 "-fps_mode", "passthrough", "-enc_time_base", "1/60000", "-video_track_timescale", "60000",
                 "-movflags", "+faststart", video, "-map", f"[{audio_label}]", "-vn",
                 "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", "-t", f"{duration:.9f}", audio)
        clip["video_processing"] = "encoded"
    if _frame_count(video) != clip["frames"]:
        raise RuntimeError(f"segment {index + 1} frame count differs from the timeline")
    if clip["self_exported"]:
        encoded_clock = _frame_clock(video)
        if any(abs(frame["time"] - expected) > 2 / 60000
               for frame, expected in zip(encoded_clock, clip["source_frame_times"])):
            raise RuntimeError(f"segment {index + 1} changed the self-exported source frame clock")
        video_info = probe(video)
        encoded_duration = float(_streams(video_info, "video")[0].get("duration", _duration(video_info)))
        if abs(encoded_duration - duration) > 3 / 60000:
            raise RuntimeError(f"segment {index + 1} could not preserve the self-exported last frame duration")
    if abs(_duration(probe(audio)) - duration) > 2 / 48000:
        raise RuntimeError(f"segment {index + 1} audio duration differs from the timeline")
    return video, audio


def _concat_listing(paths, target):
    # Paths are generated simple filenames inside this workspace. Relative entries
    # avoid FFmpeg's platform-dependent escaping of drive letters and apostrophes.
    target.write_text("".join(f"file '{path.name}'\n" for path in paths), encoding="utf-8")


def compose(timeline_path, output_path, *, width=3840, height=2160, fps=60, encoder="cpu"):
    """Compose clips and two-pass R128 audio, without overwriting source assets."""
    for name, value in (("width", width), ("height", height), ("fps", fps)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if width % 2 or height % 2:
        raise ValueError("H264 yuv420p output width and height must be even")
    if encoder != "cpu":
        raise ValueError("compose currently supports encoder='cpu'; no GPU lease is acquired")
    output = Path(output_path).resolve()
    sidecar = Path(str(output) + ".identity.json")
    if output.exists() or sidecar.exists():
        raise FileExistsError(f"refusing to overwrite existing deliverables: {output}")
    if output.suffix.lower() != ".mp4":
        raise ValueError("compose output must have .mp4 extension")
    timeline_file = _input_path(timeline_path, Path.cwd())
    timeline_record = _source(timeline_file)
    timeline = read_json(timeline_file)
    clips, sources = _prepare_timeline(timeline, timeline_file.parent, fps)
    font_path = _font(timeline.get("subtitle_font"), timeline_file.parent) if any(c["cues"] or c["label"] for c in clips) else None
    if font_path:
        sources.append(_source(font_path))
    frame_count = sum(clip["frames"] for clip in clips)
    duration = sum(clip["duration"] for clip in clips)
    variable_frame_rate = any(clip["self_exported"] for clip in clips)
    with temp_workspace(output.parent, ".webfilm-compose-") as workspace:
        workspace = Path(workspace)
        pairs = [_render_segment(clip, index, workspace, width, height, fps, font_path)
                 for index, clip in enumerate(clips)]
        video_list, audio_list = workspace / "video-concat.txt", workspace / "audio-concat.txt"
        _concat_listing([pair[0] for pair in pairs], video_list)
        _concat_listing([pair[1] for pair in pairs], audio_list)
        merged_video, merged_audio = workspace / "assembled.mp4", workspace / "assembled.wav"
        _ffmpeg("-loglevel", "error", "-f", "concat", "-safe", "0", "-i", video_list,
                 "-map", "0:v:0", "-c:v", "copy", "-video_track_timescale", "60000", merged_video)
        _ffmpeg("-loglevel", "error", "-f", "concat", "-safe", "0", "-i", audio_list,
                 "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", merged_audio)
        measurement = _audio_measure(merged_audio)
        staged = workspace / "final.mp4"
        # loudnorm needs its three-second analysis window even for a very short
        # silent clip; FFmpeg can otherwise emit NaNs. Padding is inside the
        # filter only, then removed to the exact original sample duration.
        measured_finite = all(math.isfinite(float(measurement["loudnorm"][key])) for key in _MEASURED.values())
        padding_seconds = max(0, 3 - duration) if not measured_finite else 0
        normalization_filter = (("apad=whole_dur=3," if padding_seconds else "") +
                                _second_pass(measurement) + f",atrim=duration={duration:.9f}")
        _ffmpeg("-loglevel", "info", "-i", merged_video, "-i", merged_audio,
                 "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-af", normalization_filter,
                 "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                 "-t", f"{duration:.9f}", "-video_track_timescale", "60000", "-movflags", "+faststart", staged)
        info = probe(staged)
        videos, audios = _streams(info, "video"), _streams(info, "audio")
        if len(videos) != 1 or len(audios) != 1:
            raise RuntimeError("composed video must have exactly one video and one audio stream")
        video, audio = videos[0], audios[0]
        if (video.get("width"), video.get("height"), video.get("codec_name"), video.get("pix_fmt")) != (width, height, "h264", "yuv420p"):
            raise RuntimeError("composed video resolution or codec does not match the requested output")
        if (not variable_frame_rate and Fraction(video.get("avg_frame_rate", "0/1")) != fps) or _frame_count(staged) != frame_count:
            raise RuntimeError("composed video frame rate or decoded frame count is incorrect")
        if variable_frame_rate:
            if abs(float(video.get("duration", duration)) - duration) > 3 / 60000:
                raise RuntimeError("composition changed the self-exported final frame duration")
            output_clock = _frame_clock(staged)
            frame_offset, time_offset = 0, 0.0
            for clip in clips:
                expected_times = (clip["source_frame_times"] if clip["self_exported"]
                                  else [index / fps for index in range(clip["frames"])])
                section = output_clock[frame_offset:frame_offset + clip["frames"]]
                if any(abs(frame["time"] - (time_offset + expected)) > 3 / 60000
                       for frame, expected in zip(section, expected_times)):
                    raise RuntimeError("composition changed a clip's frame timestamps")
                frame_offset += clip["frames"]
                time_offset += clip["duration"]
        if audio.get("codec_name") != "aac" or str(audio.get("sample_rate")) != "48000" or audio.get("channels") != 2:
            raise RuntimeError("composed audio must be AAC 48 kHz stereo")
        if abs(float(audio.get("duration", duration)) - duration) > max(1 / fps, 0.03):
            raise RuntimeError("composed audio duration differs from the timeline")
        if abs(_duration(info) - duration) > max(1 / fps, 0.03):
            raise RuntimeError("composed video duration differs from the timeline")
        for source in [timeline_record, *sources]:
            if sha256(Path(source["path"])) != source["sha256"]:
                raise RuntimeError(f"compose source changed during encoding: {source['path']}")
        record = {"schema": "webfilm.compose.v1", "timeline": timeline_record, "sources": sources,
                  "settings": {"width": width, "height": height, "fps": fps, "encoder": encoder,
                               "variable_frame_rate": variable_frame_rate, "time_base": "1/60000"},
                  "clips": [{"frames": clip["frames"], "duration": clip["duration"],
                             "requested_duration": clip["requested_duration"],
                             "self_exported": clip["self_exported"], "native_fps": clip["native_fps"],
                             "source_frame_times": clip["source_frame_times"], "label": clip["label"],
                             "narration": str(clip["narration"]["path"]) if clip["narration"] else None,
                             "narration_start": clip["narration"]["start"] if clip["narration"] else None,
                             "narration_source_duration": clip["narration"]["source_duration"] if clip["narration"] else None,
                             "narration_remaining_duration": clip["narration"]["remaining_duration"] if clip["narration"] else None,
                             "narration_padding_seconds": clip["narration"]["padding_seconds"] if clip["narration"] else 0,
                             "video_processing": clip["video_processing"],
                             "source_audio": [view["audio"] for view in clip["views"]],
                             "subtitle_cues": clip["cues"]} for clip in clips],
                  "audio_normalization": {"passes": 2, **measurement,
                                          "processing_padding_seconds": padding_seconds,
                                          "output": _audio_measure(staged)},
                  "output": {"path": str(output), "sha256": sha256(staged), "bytes": staged.stat().st_size,
                             "duration": duration, "frame_count": frame_count, "probe": info}}
        staged_sidecar = workspace / "final.identity.json"
        write_json(staged_sidecar, record)
        if output.exists() or sidecar.exists():
            raise FileExistsError(f"output appeared during composition: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        staged.rename(output)
        staged_sidecar.rename(sidecar)
    return {"output": str(output), "sidecar": str(sidecar), "identity": record}
