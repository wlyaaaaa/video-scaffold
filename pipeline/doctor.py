# -*- coding: utf-8 -*-
"""Local workflow preflight. It creates no video project content.

Default checks are static and read-only (no browser, GPU, model download or key file read).
``--live-local`` explicitly runs local browser/encoder/CUDA probes. ``--live-fish`` additionally sends one
very short TTS request through the configured Fish route and deletes the probe
audio immediately after validation.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.io_utils import safe_print as print


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def _check(name: str, condition: bool, detail: str, *, warning: bool = False) -> Check:
    if condition:
        return Check(name, "PASS", detail)
    return Check(name, "WARN" if warning else "FAIL", detail)


def _run(command: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _probe(path: str) -> dict[str, object]:
    completed = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            path,
        ]
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffprobe failed")
    return json.loads(completed.stdout)


def _package_check() -> Check:
    packages = ["playwright", "requests"]
    if config.TIMING_SOURCE == "whisper":
        packages += ["faster-whisper", "ctranslate2"]
    missing = []
    versions = []
    for package in packages:
        try:
            versions.append(f"{package}={importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            missing.append(package)
    return _check(
        "python-packages",
        not missing,
        ", ".join(versions) if not missing else "missing: " + ", ".join(missing),
    )


def _background_check() -> Check:
    try:
        probe = _probe(config.BG_VIDEO)
        video = next(
            stream
            for stream in probe.get("streams", [])
            if stream.get("codec_type") == "video"
        )
        rate = str(video.get("r_frame_rate", "0/1"))
        numerator, denominator = (float(part) for part in rate.split("/", 1))
        fps = numerator / denominator if denominator else 0.0
        valid = (
            int(video.get("width", 0)) == config.WIDTH
            and int(video.get("height", 0)) == config.HEIGHT
            and abs(fps - config.FPS) < 0.01
        )
        return _check(
            "background",
            valid,
            f"{video.get('codec_name')} {video.get('width')}x{video.get('height')} {fps:g}fps",
        )
    except Exception as error:
        return Check("background", "FAIL", str(error))


def _playwright_check() -> Check:
    try:
        from playwright.sync_api import sync_playwright

        uri = pathlib.Path(config.TEMPLATE_BASE).as_uri() + "?dur=1"
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True, channel="chrome")
            except Exception:
                browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": config.WIDTH, "height": config.HEIGHT}
            )
            page.goto(uri, wait_until="load")
            stage_count = page.locator("#stage").count()
            runtime = page.evaluate("typeof window.seekTime")
            browser.close()
        return _check(
            "svg-runtime",
            stage_count == 1 and runtime == "function",
            f"stage={stage_count}, seekTime={runtime}",
        )
    except Exception as error:
        return Check("svg-runtime", "FAIL", str(error))


def _gpu_memory_detail() -> str:
    try:
        completed = _run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ]
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            return "GPU memory state unavailable"
        values = [part.strip() for part in completed.stdout.splitlines()[0].split(",")]
        if len(values) != 3:
            return "GPU memory state unavailable"
        used, free, utilization = values
        return f"{used} MiB used, {free} MiB free, {utilization}% utilization"
    except Exception:
        return "GPU memory state unavailable"


def _nvenc_check() -> Check:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={config.WIDTH}x{config.HEIGHT}:r={config.FPS}:d=0.1",
        "-frames:v",
        "1",
        "-c:v",
        config.VCODEC,
        *config.NVENC_EXTRA,
        "-f",
        "null",
        os.devnull,
    ]
    from pipeline.gpu import gpu_lease

    with gpu_lease(config.VCODEC.endswith("_nvenc")):
        completed = _run(command, timeout=60)
    error = completed.stderr.strip()
    if completed.returncode != 0 and (
        "out of memory" in error.lower() or "cannot allocate memory" in error.lower()
    ):
        return Check(
            "nvenc",
            "BUSY",
            f"GPU resource pressure prevented the 4K AV1 probe; {_gpu_memory_detail()}",
        )
    return _check(
        "nvenc",
        completed.returncode == 0,
        "4K AV1 one-frame encode" if completed.returncode == 0 else error,
    )


def _cuda_check() -> Check:
    try:
        from pipeline import transcribe  # noqa: F401 - registers Windows CUDA DLL directories
        import ctranslate2

        count = ctranslate2.get_cuda_device_count()
        compute = (
            sorted(ctranslate2.get_supported_compute_types("cuda")) if count else []
        )
        return _check(
            "whisper-cuda", count > 0, f"devices={count}, compute={','.join(compute)}"
        )
    except Exception as error:
        return Check("whisper-cuda", "FAIL", str(error))


def _model_cache_check() -> Check:
    model = str(config.WHISPER_MODEL)
    if pathlib.Path(model).is_dir():
        paths = [pathlib.Path(model) / "model.bin"]
    else:
        home = pathlib.Path(
            os.environ.get(
                "HF_HOME", str(pathlib.Path.home() / ".cache" / "huggingface")
            )
        )
        cache = pathlib.Path(os.environ.get("HF_HUB_CACHE", str(home / "hub")))
        slug = "models--" + (
            model if "/" in model else "Systran/faster-whisper-" + model
        ).replace("/", "--")
        paths = list((cache / slug / "snapshots").glob("*/model.bin"))
    found = any(path.is_file() and path.stat().st_size > 0 for path in paths)
    return _check(
        "whisper-model-cache",
        found,
        "model weights located; actual inference not checked"
        if found
        else "local weights not located; no download was attempted",
        warning=True,
    )


def _fish_config_check() -> Check:
    ready = bool(
        config.get_fish_api_key() and config.FISH_MODEL and config.FISH_REFERENCE_ID
    )
    return _check(
        "fish-config",
        ready,
        f"model={config.FISH_MODEL}, voice={'configured' if config.FISH_REFERENCE_ID else 'missing'}, "
        f"key={'configured' if ready else 'missing'}",
    )


def _fish_live_check() -> Check:
    if not config.get_fish_api_key():
        return Check("fish-live", "FAIL", "FISH_API_KEY is not configured")
    try:
        from pipeline import fish_tts

        with tempfile.TemporaryDirectory(prefix="video-scaffold-fish-") as temporary:
            output = os.path.join(temporary, "probe.mp3")
            if not fish_tts.synth_one("连通性测试。", output):
                return Check("fish-live", "FAIL", "Fish rejected the configured route")
            probe = _probe(output)
            audio = next(
                stream
                for stream in probe.get("streams", [])
                if stream.get("codec_type") == "audio"
            )
            duration = float(probe.get("format", {}).get("duration", 0.0))
            valid = audio.get("codec_name") == "mp3" and duration > 0
            return _check(
                "fish-live",
                valid,
                f"{audio.get('codec_name')} {audio.get('sample_rate')}Hz {duration:.3f}s",
            )
    except Exception as error:
        return Check("fish-live", "FAIL", str(error))


def run_checks(*, live_fish: bool = False, live_local: bool = False) -> list[Check]:
    checks = [
        _check("python", sys.version_info >= (3, 11), sys.version.split()[0]),
        _package_check(),
        _check(
            "ffmpeg",
            shutil.which("ffmpeg") is not None,
            shutil.which("ffmpeg") or "missing",
        ),
        _check(
            "ffprobe",
            shutil.which("ffprobe") is not None,
            shutil.which("ffprobe") or "missing",
        ),
        _check(
            "background-file",
            os.path.isfile(config.BG_VIDEO),
            "tracked background exists",
        ),
        _check(
            "scene-template",
            os.path.isfile(config.TEMPLATE_BASE),
            "scene template exists",
        ),
        Check(
            "mode",
            "PASS",
            "live-local probes requested"
            if live_local
            else "static read-only; no browser/GPU/network/private key read",
        ),
        Check(
            "fish-route",
            "UNKNOWN",
            f"configured model={config.FISH_MODEL}; account and voice not tested",
        ),
        Check(
            "gpu-coordination",
            "PASS" if config.GPU_BROKER_URL else "WARN",
            "existing broker configured"
            if config.GPU_BROKER_URL
            else "standalone mode; set machine GPU broker adapter on managed hosts",
        ),
    ]
    if config.TIMING_SOURCE == "whisper":
        checks.append(_model_cache_check())
    if live_local:
        for name, function in (
            ("background", _background_check),
            ("nvenc", _nvenc_check),
            ("svg-runtime", _playwright_check),
        ):
            try:
                checks.append(function())
            except Exception as error:
                checks.append(Check(name, "FAIL", str(error)))
        if config.TIMING_SOURCE == "whisper" and config.WHISPER_DEVICE == "cuda":
            from pipeline.gpu import gpu_lease

            try:
                with gpu_lease():
                    checks.append(_cuda_check())
            except Exception as error:
                checks.append(Check("whisper-cuda", "FAIL", str(error)))
    if live_fish:
        checks.extend((_fish_config_check(), _fish_live_check()))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the local video workflow without starting a video."
    )
    parser.add_argument(
        "--live-local",
        action="store_true",
        help="run explicit browser, GPU encoder and CUDA probes",
    )
    parser.add_argument(
        "--live-fish", action="store_true", help="send one minimal Fish TTS probe"
    )
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable results"
    )
    args = parser.parse_args()
    checks = run_checks(live_fish=args.live_fish, live_local=args.live_local)
    if args.json:
        print(
            json.dumps(
                [asdict(check) for check in checks], ensure_ascii=False, indent=2
            )
        )
    else:
        for check in checks:
            print(f"[{check.status:4s}] {check.name}: {check.detail}")
    if any(check.status == "FAIL" for check in checks):
        return 1
    if any(check.status == "BUSY" for check in checks):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
