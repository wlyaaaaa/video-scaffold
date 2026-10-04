"""Exact frame clock, code-generated offline audio, and scripted page interaction."""
from __future__ import annotations

import base64
from fractions import Fraction
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import shutil
import threading
import time

from PIL import Image

from .browser import work_page, seek, assert_runtime, evaluate
from .check import check_work, load_work
from .common import NO_WINDOW, new_output, probe, read_json, run, sha256, temp_workspace, tool, write_json

SAMPLE_RATE = 48000


def reusable_soundtrack(parent, report, config, width, height, actions_hash, chrome, generic):
    """Reuse a byte-bound offline master made from exactly the same work.

    Chrome's floating-point DSP can differ by one PCM least-significant bit.
    Generated sound is therefore a source-bound master, just like narration.
    Never reuse an unrelated/stale audio file or ignore changed work inputs.
    """
    mode = "external webpage clock" if generic else "optional explicit-time work API"
    for sidecar in sorted(Path(parent).glob("*.mp4.json")):
        try:
            identity = read_json(sidecar)
            if identity.get("schema") != "webfilm.render.v1":
                continue
            if identity.get("capture_mode", "optional explicit-time work API") != mode:
                continue
            if identity.get("width") != width or identity.get("height") != height or identity.get("duration") != config["duration"]:
                continue
            if generic and identity.get("seed") != config.get("seed", 829):
                continue
            if generic and identity.get("entrypoint") != config.get("entry", "index.html"):
                continue
            if identity.get("action_script_sha256") != actions_hash or identity.get("work", {}).get("files") != report["files"]:
                continue
            if identity.get("work", {}).get("pass") is not True:
                continue
            if identity.get("work", {}).get("runtime", {}).get("chrome") != chrome:
                continue
            original = Path(str(sidecar)[:-5])
            wav = Path(str(original) + ".wav")
            if not original.is_file() or not wav.is_file() or sha256(original) != identity.get("output_sha256"):
                continue
            if sha256(wav) != identity.get("audio", {}).get("sha256"):
                continue
            evidence = dict(identity["audio"])
            evidence["reused_from"] = {"render_identity": str(sidecar), "render_identity_sha256": sha256(sidecar),
                                       "soundtrack": str(wav), "soundtrack_sha256": sha256(wav)}
            return wav, evidence
        except (OSError, ValueError, KeyError):
            continue
    return None

AUDIO_RENDER = r"""async ({duration, rate}) => {
  if (typeof window.webfilm.audio !== 'function') throw new Error('Generated audio requires webfilm.audio(ctx)');
  const length = Math.round(duration*rate);
  const context = new OfflineAudioContext(2,length,rate);
  await window.webfilm.audio(context);
  const result = await context.startRendering();
  const bytes = new Uint8Array(44 + length*4), view = new DataView(bytes.buffer);
  const ascii=(at,str)=>{for(let i=0;i<str.length;i++)bytes[at+i]=str.charCodeAt(i);};
  ascii(0,'RIFF');view.setUint32(4,36+length*4,true);ascii(8,'WAVE');ascii(12,'fmt ');
  view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,2,true);
  view.setUint32(24,rate,true);view.setUint32(28,rate*4,true);view.setUint16(32,4,true);view.setUint16(34,16,true);
  ascii(36,'data');view.setUint32(40,length*4,true);
  const left=result.getChannelData(0),right=result.getChannelData(1);
  let peak=0,energy=0;
  for(let i=0;i<length;i++) for(let c=0;c<2;c++) {
    const value=(c===0?left:right)[i];
    if(!Number.isFinite(value)) throw new Error('Nonfinite generated audio sample');
    peak=Math.max(peak,Math.abs(value));energy+=value*value;
    const limited=Math.max(-1,Math.min(1,value));
    view.setInt16(44+i*4+c*2,Math.round(limited*(limited<0?32768:32767)),true);
  }
  let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
  return {wav:btoa(binary),length,rate,channels:2,peak,rms:Math.sqrt(energy/(length*2)),clipped:peak>1};
}"""


def frame_count(duration, fps):
    frames = duration * fps
    if not math.isfinite(frames) or not math.isclose(frames, round(frames), abs_tol=1e-7):
        raise ValueError("duration must span an exact integer number of frames")
    return round(frames)


def dimensions(width, height, fps):
    if (width, height) not in ((3840, 2160), (1920, 1080)):
        raise ValueError("Render resolution must be 3840x2160 or 1920x1080")
    if fps != 60:
        raise ValueError("This production contract uses 60 fps")


def load_actions(path, duration):
    if not path:
        return []
    value = read_json(path)
    if value.get("schema") != 1 or not isinstance(value.get("actions"), list):
        raise ValueError("Action script requires schema 1 and an actions array")
    last = -1
    for action in value["actions"]:
        at = action.get("at")
        if isinstance(at, bool) or not isinstance(at, (float, int)) or not math.isfinite(at) or not 0 <= at < duration or at < last:
            raise ValueError("Actions must be sorted and have times inside the work duration")
        if action.get("type") not in ("move", "click", "hover", "scroll", "wait"):
            raise ValueError("Unknown action type")
        if action["type"] in ("click", "hover") and not isinstance(action.get("selector"), str):
            raise ValueError("click/hover requires a selector")
        if action["type"] == "move" and not all(isinstance(action.get(k), (float, int)) and math.isfinite(action[k]) for k in ("x", "y")):
            raise ValueError("move requires finite x and y")
        if action["type"] == "scroll":
            if not isinstance(action.get("y"), (float, int)) or not math.isfinite(action["y"]):
                raise ValueError("scroll requires a finite target y")
            length = action.get("duration", 0)
            if not isinstance(length, (int, float)) or not math.isfinite(length) or length < 0 or at + length > duration:
                raise ValueError("Scroll transition must end inside the work duration")
        last = at
    return value["actions"]


CURSOR = r"""() => {
  const cursor=document.createElement('div');cursor.id='__webfilm_cursor';
  cursor.style.cssText='position:fixed;left:0;top:0;width:42px;height:52px;z-index:2147483647;pointer-events:none;filter:drop-shadow(0 2px 3px #0008);transform:translate(-100px,-100px);';
  cursor.innerHTML='<svg viewBox="0 0 42 52"><path d="M4 3 L4 40 L14 31 L22 48 L30 44 L22 27 L36 25 Z" fill="white" stroke="#17241d" stroke-width="3"/></svg>';
  document.body.append(cursor);
  const ring=document.createElement('div');ring.id='__webfilm_click';ring.style.cssText='position:fixed;width:48px;height:48px;border:4px solid #f3a03b;border-radius:50%;pointer-events:none;z-index:2147483646;opacity:0;';document.body.append(ring);
}"""


class Actions:
    def __init__(self, page, actions):
        self.page, self.actions = page, actions
        self.index, self.scroll = 0, None
        self.position = (80, 80)
        self.click_time = -10
        self.log = []
        if actions:
            evaluate(page, CURSOR)

    def tick(self, t):
        while self.index < len(self.actions) and self.actions[self.index]["at"] <= t + 1e-9:
            action = self.actions[self.index]
            kind = action["type"]
            if kind == "move":
                self.position = action["x"], action["y"]
                self.page.mouse.move(*self.position)
            elif kind in ("click", "hover"):
                locator = self.page.locator(action["selector"])
                if locator.count() != 1:
                    raise ValueError(f"Action selector must match exactly one visible target: {action['selector']}")
                box = locator.bounding_box()
                if not box:
                    raise ValueError(f"Action target is invisible: {action['selector']}")
                self.position = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                self.page.mouse.move(*self.position)
                if kind == "click":
                    self.page.mouse.down()
                    self.page.mouse.up()
                    self.click_time = t
            elif kind == "scroll":
                current = evaluate(self.page, "() => window.scrollY")
                self.scroll = {"from": current, "to": action["y"], "at": action["at"], "duration": action.get("duration", 0)}
            self.log.append({"index": self.index, "at": action["at"], "frame_time": t, "type": kind, "pointer": self.position})
            self.index += 1
        if self.scroll:
            s = self.scroll
            progress = min(1, max(0, (t-s["at"]) / s["duration"])) if s["duration"] else 1
            y = s["from"] + (s["to"]-s["from"]) * progress
            evaluate(self.page, "y => window.scrollTo({top:y,left:0,behavior:'instant'})", y)
        if self.actions:
            evaluate(self.page, """({x,y,age}) => {
              document.getElementById('__webfilm_cursor').style.transform=`translate(${x}px,${y}px)`;
              const ring=document.getElementById('__webfilm_click');ring.style.left=(x-24)+'px';ring.style.top=(y-24)+'px';ring.style.opacity=String(Math.max(0,1-age/.35));ring.style.transform=`scale(${1+Math.max(0,age)*2})`;
            }""", {"x": self.position[0], "y": self.position[1], "age": t-self.click_time})


def encode_arguments(fps, output):
    return [tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-f", "image2pipe",
            "-vcodec", "png", "-framerate", str(fps), "-i", "pipe:0", "-an", "-c:v", "libx264",
            "-preset", "fast", "-crf", "18", "-threads", "4", "-pix_fmt", "yuv420p",
            "-r", str(fps), "-movflags", "+faststart", str(output)]


def render_work(folder, output_path, *, width=3840, height=2160, fps=60, actions_path=None, max_duration=120,
                generic=False, entry=None, duration=20, seed=829):
    dimensions(width, height, fps)
    if generic:
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 0xffffffff:
            raise ValueError("Capture seed must be a 32-bit unsigned integer")
        from .input import choose_page
        root, selected, discovered = choose_page(folder, entry)
        config = {"entry": selected, "duration": duration, "seed": seed, "audio": "generated", "accepted_exports": discovered["videos"]}
        report = check_work(root, max_duration=max_duration, config=config)
    else:
        root, config = load_work(folder, max_duration=max_duration)
        report = check_work(root, max_duration=max_duration)
    if not report["pass"]:
        raise ValueError("Static work rules failed: " + "; ".join(report["errors"]))
    count = frame_count(config["duration"], fps)
    actions = load_actions(actions_path, config["duration"])
    actions_hash = sha256(actions_path) if actions_path else None
    output = new_output(output_path)
    if output.is_relative_to(root):
        raise ValueError("Render outputs must be outside the original work folder")
    sidecar = Path(str(output) + ".json")
    frame_sidecar = Path(str(output) + ".frames.json")
    final_audio = Path(str(output) + ".wav")
    if sidecar.exists() or frame_sidecar.exists() or final_audio.exists():
        raise FileExistsError("Render evidence already exists; use a new output filename")
    frames, elapsed = [], time.monotonic()
    with temp_workspace(output.parent, "render-") as temporary:
        audio_path = temporary / "generated.wav"
        silent_video = temporary / "picture.mp4"
        audio_evidence = {"source": "none", "rate": SAMPLE_RATE, "length": round(config["duration"]*SAMPLE_RATE), "channels": 2}
        init_script = None
        if generic:
            init_script = "(" + (Path(__file__).parent / "generic.js").read_text(encoding="utf-8") + ")(" + __import__("json").dumps({"seed": seed, "duration": duration, "rate": SAMPLE_RATE}) + ")"
        with work_page(root, config, output.parent, width=width, height=height, init_script=init_script, require_api=not generic) as (page, runtime):
            if generic:
                pass  # All scheduled/interactive audio events are collected first.
            elif config.get("audio") == "generated":
                audio_result = evaluate(page, AUDIO_RENDER, {"duration": config["duration"], "rate": SAMPLE_RATE}, timeout=120)
                wav = base64.b64decode(audio_result.pop("wav"))
                audio_path.write_bytes(wav)
                audio_evidence.update(audio_result, source="OfflineAudioContext", sha256=sha256(audio_path))
                if audio_result["clipped"]:
                    raise ValueError("Generated audio clips; lower gain before rendering")
            else:
                run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={SAMPLE_RATE}:cl=stereo", "-t", str(config["duration"]), "-c:a", "pcm_s16le", audio_path])
                audio_evidence["sha256"] = sha256(audio_path)
            actor = Actions(page, actions)
            client = page.context.new_cdp_session(page)
            log = temporary / "encoder.log"
            with log.open("wb") as error_log:
                encoder = subprocess.Popen(encode_arguments(fps, silent_video), stdin=subprocess.PIPE,
                                           stdout=subprocess.DEVNULL, stderr=error_log, creationflags=NO_WINDOW)
                timed_out = threading.Event()
                def stop_encoder():
                    if encoder.poll() is None:
                        timed_out.set()
                        encoder.kill()  # Break a blocked stdin write as well.
                watchdog = threading.Timer(max(180, count*1.5), stop_encoder)
                watchdog.daemon = True
                watchdog.start()
                try:
                    for index in range(count):
                        t = index / fps
                        if generic:
                            evaluate(page, "t => window.__webfilmAdvance(t)", t)
                        else:
                            seek(page, t)
                        actor.tick(t)
                        # Handlers may change visual state; give the work the same
                        # logical time once more, without advancing the frame clock.
                        if actions and not generic:
                            seek(page, t)
                            actor.tick(t)
                        png = base64.b64decode(client.send("Page.captureScreenshot", {"format": "png", "fromSurface": True,
                                                                                   "captureBeyondViewport": False, "optimizeForSpeed": True})["data"])
                        with Image.open(io.BytesIO(png)) as frame:
                            if frame.size != (width, height):
                                raise RuntimeError("Chrome returned a screenshot with the wrong dimensions")
                            pixels = frame.convert("RGB").tobytes()
                            frames.append(hashlib.sha256(pixels).hexdigest())
                        encoder.stdin.write(png)
                        if index % 60 == 0:
                            assert_runtime(page, runtime)
                        if index % 300 == 0 or index == count - 1:
                            print(f"webfilm frame {index+1}/{count} t={t:.3f}s elapsed={time.monotonic()-elapsed:.1f}s", flush=True)
                    encoder.stdin.close()
                    encoder.wait(timeout=600)
                    if encoder.returncode:
                        if timed_out.is_set():
                            raise TimeoutError("Frame capture/encoding exceeded its host-clock deadline")
                        raise RuntimeError("Video encoding failed: " + log.read_text(encoding="utf-8", errors="replace")[-5000:])
                except BaseException:
                    if encoder.poll() is None:
                        encoder.kill()
                    encoder.wait(timeout=10)
                    raise
                finally:
                    watchdog.cancel()
            assert_runtime(page, runtime)
            if generic:
                # Collect timers scheduled at the final audio boundary without
                # adding an extra video frame.
                evaluate(page, "t => window.__webfilmAdvance(t)", duration)
                audio_result = evaluate(page, "() => window.__webfilmExportAudio()", timeout=120)
                limitations = audio_result.get("limitations", [])
                if limitations:
                    raise ValueError("This page cannot be captured deterministically: " + "; ".join(limitations) + ". Use a model-exported MP4 or an explicitly labelled realtime recording.")
                audio_path.write_bytes(base64.b64decode(audio_result.pop("wav")))
                audio_evidence.update(audio_result, source="externally captured AudioContext -> OfflineAudioContext", sha256=sha256(audio_path))
                if audio_result["clipped"]:
                    raise ValueError("Captured program audio clips")
                assert_runtime(page, runtime)
            runtime_evidence = {key: value for key, value in runtime.items() if key != "origin"}
            runtime_evidence["requests"] = sorted(set(runtime["requests"]))
            runtime_evidence["action_log"] = actor.log
        # Audio is precomputed from precisely the same zero point as i/fps.
        staged_output = temporary / "complete.mp4"
        run([tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", silent_video, "-i", audio_path,
             "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
             "-ar", str(SAMPLE_RATE), "-ac", "2", "-t", str(config["duration"]), "-movflags", "+faststart", staged_output])
        info = probe(staged_output)
        video = next(stream for stream in info["streams"] if stream["codec_type"] == "video")
        audio = next(stream for stream in info["streams"] if stream["codec_type"] == "audio")
        if (video["width"], video["height"]) != (width, height) or Fraction(video["avg_frame_rate"]) != fps or int(video.get("nb_frames", -1)) != count:
            raise RuntimeError("Final video dimensions/rate/frame count failed verification")
        if abs(float(video["duration"])-config["duration"]) > 1/fps or abs(float(audio["duration"])-config["duration"]) > 1/SAMPLE_RATE:
            raise RuntimeError("Final audio/video duration failed verification")
        # Keep the exact offline soundtrack as a useful editable/review source.
        current_report = check_work(root, max_duration=max_duration, config=config)
        if report["files"] != current_report["files"] or (actions_path and actions_hash != sha256(actions_path)):
            raise RuntimeError("Original page/materials/action script changed during rendering; refusing stale source binding")
        # Bind the first valid offline master and reuse its exact bytes on later
        # renders. The source still executed its audio graph, so its side effects
        # and current runtime/rule checks were exercised above.
        previous = reusable_soundtrack(output.parent, report, config, width, height, actions_hash,
                                       runtime_evidence["chrome"], generic)
        if previous:
            source_master, audio_evidence = previous
            shutil.copyfile(source_master, audio_path)
            run([tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", silent_video, "-i", audio_path,
                 "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                 "-ar", str(SAMPLE_RATE), "-ac", "2", "-t", str(config["duration"]), "-movflags", "+faststart", staged_output])
            info = probe(staged_output)
        staged_output.replace(output)
        audio_path.replace(final_audio)
    write_json(frame_sidecar, {"schema": "webfilm.frames.v1", "pixel_format": "RGB24", "width": width,
                              "height": height, "fps": fps, "duration": config["duration"], "sha256": frames})
    report.update(scope="static + complete runtime render", runtime=runtime_evidence)
    identity = {"schema": "webfilm.render.v1", "work": report, "frame_count": count, "width": width, "height": height,
                "fps": fps, "duration": config["duration"], "audio": audio_evidence, "output_sha256": sha256(output),
                "frames_sha256": sha256(frame_sidecar), "action_script_sha256": actions_hash,
                "capture_mode": "external webpage clock" if generic else "optional explicit-time work API",
                "seed": config.get("seed", 829),
                "entrypoint": config.get("entry", "index.html"),
                "elapsed_seconds": round(time.monotonic()-elapsed, 3), "probe": info}
    write_json(sidecar, identity)
    return identity


def compare_renders(left, right):
    a, b = read_json(str(left) + ".frames.json"), read_json(str(right) + ".frames.json")
    ia, ib = read_json(str(left) + ".json"), read_json(str(right) + ".json")
    for path, identity in ((left, ia), (right, ib)):
        if sha256(path) != identity["output_sha256"]:
            raise ValueError("Rendered MP4 bytes no longer match their recorded source identity")
        if sha256(str(path) + ".frames.json") != identity["frames_sha256"]:
            raise ValueError("Captured frame manifest no longer matches its render identity")
        if sha256(str(path) + ".wav") != identity["audio"]["sha256"]:
            raise ValueError("Offline soundtrack no longer matches its render identity")
    parameters = ("width", "height", "fps", "duration")
    mismatches = [i for i, pair in enumerate(zip(a["sha256"], b["sha256"])) if pair[0] != pair[1]]
    same_parameters = all(a[key] == b[key] for key in parameters)
    same_count = len(a["sha256"]) == len(b["sha256"])
    audio_equal = ia["audio"]["sha256"] == ib["audio"]["sha256"]
    encoded_equal = ia["output_sha256"] == ib["output_sha256"]
    encoded_mismatches = []
    if not encoded_equal:
        def decoded_hashes(path):
            result = run([tool("ffmpeg"), "-v", "error", "-i", path, "-map", "0:v:0", "-an",
                          "-pix_fmt", "rgb24", "-fps_mode", "passthrough", "-hash", "sha256", "-f", "framehash", "-"], timeout=3600)
            return [line.rsplit(",", 1)[-1].strip() for line in result.stdout.decode("utf-8").splitlines() if line and not line.startswith("#")]
        ha, hb = decoded_hashes(left), decoded_hashes(right)
        encoded_mismatches = [i for i, values in enumerate(zip(ha, hb)) if values[0] != values[1]]
        if len(ha) != len(hb):
            encoded_mismatches += list(range(min(len(ha), len(hb)), max(len(ha), len(hb))))
    return {"schema": "webfilm.compare.v1", "pass": same_parameters and same_count and not mismatches and audio_equal and not encoded_mismatches,
            "parameters_equal": same_parameters, "frame_counts": [len(a["sha256"]), len(b["sha256"])],
            "mismatched_frames": mismatches, "offline_audio_equal": audio_equal,
            "mp4_bytes_equal": encoded_equal, "encoded_frame_mismatches": encoded_mismatches, "current_bytes_verified": True,
            "scope": "Every captured RGB frame and offline PCM WAV, bound to current output bytes; MP4s are byte-identical or decoded frame-by-frame. Fixed installed Chrome and host."}


def render_cover(folder, output_dir, *, at=0):
    root, config = load_work(folder)
    report = check_work(root)
    if not report["pass"]:
        raise ValueError("Cover work rules failed: " + "; ".join(report["errors"]))
    if not isinstance(at, (int, float)) or not math.isfinite(at) or not 0 <= at <= config["duration"]:
        raise ValueError("Cover sampling time is outside duration")
    output = new_output(output_dir)
    if output.is_relative_to(root):
        raise ValueError("Covers must be outside original work")
    output.mkdir()
    files = []
    for width, height, name in ((3840, 2160, "cover-16x9.png"), (2880, 2160, "cover-4x3.png")):
        with work_page(root, config, output.parent, width=width, height=height) as (page, evidence):
            seek(page, at)
            page.screenshot(path=str(output / name))
            assert_runtime(page, evidence)
            files.append({"path": name, "width": width, "height": height, "sha256": sha256(output / name)})
    result = {"schema": "webfilm.covers.v1", "at": at, "work": report, "files": files}
    write_json(output / "identity.json", result)
    return result
