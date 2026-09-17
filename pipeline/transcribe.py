# -*- coding: utf-8 -*-
"""
Stage 3 (optional) - local faster-whisper word timing for A/V sync.

We don't burn subtitles. We use whisper purely to learn *when* each word is
spoken, so a scene's animations can be cued to the narration. Output is
srt_data/srt_NN.json: a list of {word, start, end} in seconds.

Model large-v3 on CUDA float16 is the verified quality/speed path.
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.io_utils import safe_print as print
from pipeline.artifact_identity import (
    output_record_matches,
    sha256_file,
    write_output_record,
)
from pipeline.indexed_files import indexed_basename, indexed_files


_CUDA_DLL_HANDLES = []


def _register_cuda_dlls():
    """Windows: CTranslate2 needs cuBLAS/cuDNN 12 on the DLL search path.
    Installed via `pip install nvidia-cublas-cu12` (cuDNN ships with ctranslate2).
    """
    if sys.platform != "win32":
        return
    import site
    import glob as _glob

    roots = list(site.getsitepackages()) + [site.getusersitepackages()]
    dll_dirs = []
    for root in roots:
        dll_dirs += _glob.glob(
            os.path.join(root, "nvidia", "*", "bin")
        )  # cublas, cudart, cudnn...
        dll_dirs.append(os.path.join(root, "ctranslate2"))
    existing = [p for p in dll_dirs if os.path.isdir(p)]
    for p in existing:
        try:
            _CUDA_DLL_HANDLES.append(os.add_dll_directory(p))
        except OSError:
            pass
    # PATH is the search location the native CTranslate2 loader actually honors
    # for resolving cuBLAS's implicit dependency on cudart, so prepend there too.
    if existing:
        os.environ["PATH"] = (
            os.pathsep.join(existing) + os.pathsep + os.environ.get("PATH", "")
        )


_register_cuda_dlls()

_model = None  # WhisperModel
_pipe = None  # BatchedInferencePipeline (max GPU throughput) if available


def _identity_record(audio_path):
    if config.TIMING_SOURCE == "fish":
        return {
            "schema": "video-scaffold.fish-word-timing.v1",
            "audio_sha256": sha256_file(audio_path),
            "native_sha256": sha256_file(audio_path + ".timestamps.json"),
        }
    return {
        "schema": "video-scaffold.word-timing-identity.v1",
        "audio_sha256": sha256_file(audio_path),
        "model": config.WHISPER_MODEL,
        "device": config.WHISPER_DEVICE,
        "compute": config.WHISPER_COMPUTE,
        "language": config.WHISPER_LANGUAGE,
        "batch_size": config.WHISPER_BATCH_SIZE,
        "cpu_threads": config.WHISPER_CPU_THREADS,
        "initial_prompt": config.WHISPER_INITIAL_PROMPT,
        "word_timestamps": True,
        "vad_filter": True,
    }


def _get_engine():
    """Load large-v3 once and prefer the batched CUDA pipeline."""
    global _model, _pipe
    if _model is None:
        from faster_whisper import WhisperModel

        print(
            f"[whisper] loading {config.WHISPER_MODEL} on {config.WHISPER_DEVICE}/{config.WHISPER_COMPUTE}"
        )
        _model = WhisperModel(
            config.WHISPER_MODEL,
            device=config.WHISPER_DEVICE,
            compute_type=config.WHISPER_COMPUTE,
            cpu_threads=config.WHISPER_CPU_THREADS,
        )
        try:
            from faster_whisper import BatchedInferencePipeline

            _pipe = BatchedInferencePipeline(model=_model)
        except Exception:
            _pipe = None  # older faster-whisper: fall back to sequential
    return _model, _pipe


def transcribe_one(audio_path, out_path):
    if config.TIMING_SOURCE == "fish":
        from pipeline.fish_native import load
        from pipeline.io_utils import atomic_json

        words = load(audio_path)
        atomic_json(out_path, words)
        return words
    model, pipe = _get_engine()
    # VAD trims silence; batching keeps the GPU useful on longer clips.
    if pipe is not None:
        segments, _ = pipe.transcribe(
            audio_path,
            language=config.WHISPER_LANGUAGE,
            word_timestamps=True,
            vad_filter=True,
            batch_size=config.WHISPER_BATCH_SIZE,
            initial_prompt=config.WHISPER_INITIAL_PROMPT,
        )
    else:
        segments, _ = model.transcribe(
            audio_path,
            language=config.WHISPER_LANGUAGE,
            word_timestamps=True,
            vad_filter=True,
            initial_prompt=config.WHISPER_INITIAL_PROMPT,
        )
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append(
                {"word": w.word, "start": round(w.start, 3), "end": round(w.end, 3)}
            )
    from pipeline.build_scene import validate_words
    from pipeline.io_utils import atomic_json

    if not words:
        raise RuntimeError("Whisper returned no words; review narration")
    validate_words(words)
    atomic_json(out_path, words)
    print(
        f"[whisper] {os.path.basename(audio_path)} -> {os.path.basename(out_path)} ({len(words)} words)"
    )
    return words


def _transcribe_batch(audio_dir=config.DIR_AUDIO, srt_dir=config.DIR_SRT, force=False):
    os.makedirs(srt_dir, exist_ok=True)
    audios = indexed_files(os.path.join(audio_dir, "audio_*.mp3"))
    for index, audio in audios.items():
        out_path = os.path.join(
            srt_dir,
            indexed_basename("srt", index, ".json"),
        )
        identity_path = os.path.join(
            srt_dir,
            indexed_basename("timing", index, ".identity.json"),
        )
        identity = _identity_record(audio)
        if not force and os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
            if output_record_matches(identity_path, identity, out_path):
                print(
                    f"[whisper] reuse {os.path.basename(out_path)} (audio identity matched)"
                )
                continue
            raise RuntimeError(
                f"{os.path.basename(out_path)} has no matching audio identity; "
                "refusing stale word timing reuse. Review the audio, then run timing --force."
            )
        import tempfile
        from pathlib import Path
        from pipeline.io_utils import publish_bundle

        with tempfile.TemporaryDirectory(prefix=".timing-", dir=srt_dir) as temporary:
            staged = str(Path(temporary) / Path(out_path).name)
            transcribe_one(audio, staged)
            staged_identity = str(Path(temporary) / Path(identity_path).name)
            write_output_record(staged_identity, identity, staged)
            publish_bundle([(staged, out_path), (staged_identity, identity_path)])


def transcribe_batch(audio_dir=config.DIR_AUDIO, srt_dir=config.DIR_SRT, force=False):
    from pipeline.gpu import gpu_lease

    global _model, _pipe
    with gpu_lease(
        config.TIMING_SOURCE == "whisper" and config.WHISPER_DEVICE == "cuda"
    ) as lease:
        try:
            result = _transcribe_batch(audio_dir, srt_dir, force)
            lease.check()
            return result
        finally:
            _pipe = None
            _model = None
            import gc

            gc.collect()


if __name__ == "__main__":
    transcribe_batch()
