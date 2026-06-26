# -*- coding: utf-8 -*-
"""
Stage 3 (optional) - local faster-whisper word timing for A/V sync.

We don't burn subtitles. We use whisper purely to learn *when* each word is
spoken, so a scene's animations can be cued to the narration. Output is
srt_data/srt_NN.json: a list of {word, start, end} in seconds.

Model large-v3 on CUDA float16 is the best quality/speed point on the 5080.
"""

import os
import sys
import glob
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


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
        dll_dirs += _glob.glob(os.path.join(root, "nvidia", "*", "bin"))  # cublas, cudart, cudnn...
        dll_dirs.append(os.path.join(root, "ctranslate2"))
    existing = [p for p in dll_dirs if os.path.isdir(p)]
    for p in existing:
        try:
            os.add_dll_directory(p)
        except OSError:
            pass
    # PATH is the search location the native CTranslate2 loader actually honors
    # for resolving cuBLAS's implicit dependency on cudart, so prepend there too.
    if existing:
        os.environ["PATH"] = os.pathsep.join(existing) + os.pathsep + os.environ.get("PATH", "")


_register_cuda_dlls()

_model = None      # WhisperModel
_pipe = None       # BatchedInferencePipeline (max GPU throughput) if available


def _get_engine():
    """Load large-v3 once, prefer the batched pipeline for 5080 throughput."""
    global _model, _pipe
    if _model is None:
        from faster_whisper import WhisperModel
        print(f"[whisper] loading {config.WHISPER_MODEL} on {config.WHISPER_DEVICE}/{config.WHISPER_COMPUTE}")
        _model = WhisperModel(config.WHISPER_MODEL,
                              device=config.WHISPER_DEVICE,
                              compute_type=config.WHISPER_COMPUTE,
                              cpu_threads=config.WHISPER_CPU_THREADS)
        try:
            from faster_whisper import BatchedInferencePipeline
            _pipe = BatchedInferencePipeline(model=_model)
        except Exception:
            _pipe = None  # older faster-whisper: fall back to sequential
    return _model, _pipe


def transcribe_one(audio_path, out_path):
    model, pipe = _get_engine()
    # VAD trims silence; batching keeps the 5080 saturated on longer clips.
    if pipe is not None:
        segments, _ = pipe.transcribe(audio_path, language=config.WHISPER_LANGUAGE,
                                      word_timestamps=True, vad_filter=True,
                                      batch_size=config.WHISPER_BATCH_SIZE)
    else:
        segments, _ = model.transcribe(audio_path, language=config.WHISPER_LANGUAGE,
                                       word_timestamps=True, vad_filter=True)
    words = []
    for seg in segments:
        for w in (seg.words or []):
            words.append({"word": w.word, "start": round(w.start, 3), "end": round(w.end, 3)})
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)
    print(f"[whisper] {os.path.basename(audio_path)} -> {os.path.basename(out_path)} ({len(words)} words)")
    return words


def transcribe_batch(audio_dir=config.DIR_AUDIO, srt_dir=config.DIR_SRT):
    config.ensure_dirs()
    for audio in sorted(glob.glob(os.path.join(audio_dir, "audio_*.mp3"))):
        idx = os.path.splitext(os.path.basename(audio))[0].split("_")[-1]
        transcribe_one(audio, os.path.join(srt_dir, f"srt_{idx}.json"))


if __name__ == "__main__":
    transcribe_batch()
