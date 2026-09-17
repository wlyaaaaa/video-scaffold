"""Generate an audio-synchronized cue review page; no server is started implicitly."""

import html
import json
import os
from pathlib import Path
import config
from pipeline.io_utils import safe_print as print
from pipeline.indexed_files import indexed_files
from pipeline.artifact_identity import (
    output_record_matches,
    write_output_record,
    sha256_file,
)
from pipeline.io_utils import atomic_output, atomic_text, positive, run

PREVIEW_HTML = os.path.join(config.DIR_OUTPUT, "preview.html")
PREVIEW_BG = os.path.join(config.DIR_OUTPUT, "_preview_bg.jpg")


def _ensure_bg():
    if not os.path.isfile(config.BG_VIDEO):
        raise FileNotFoundError("preview background missing")
    expected = {
        "schema": "video-scaffold.preview-background.v1",
        "background_sha256": sha256_file(config.BG_VIDEO),
    }
    if output_record_matches(PREVIEW_BG + ".identity.json", expected, PREVIEW_BG):
        return
    with atomic_output(PREVIEW_BG) as staged:
        run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                config.BG_VIDEO,
                "-frames:v",
                "1",
                staged,
            ]
        )
    write_output_record(PREVIEW_BG + ".identity.json", expected, PREVIEW_BG)


def build(names=None, out=None):
    out = out or os.path.join(config.DIR_OUTPUT, "preview.html")
    with open(config.DURATIONS_JSON, encoding="utf-8") as source:
        values = json.load(source)
    scenes = indexed_files(os.path.join(config.DIR_SCENE, "scene_*.html"))
    if not scenes or len(scenes) != len(values):
        raise RuntimeError("preview scene/duration count mismatch")
    values = [positive(value, "scene duration") for value in values]
    # Validate all inputs before generating or replacing preview files.
    rows = []
    for position, ((index, path), duration) in enumerate(zip(scenes.items(), values)):
        audio = Path(config.DIR_AUDIO) / f"audio_{index:02d}.mp3"
        words = Path(config.DIR_SRT) / f"srt_{index:02d}.json"
        fragment = Path(config.DIR_SCENE) / f"fragment_{index:02d}.svg"
        relative = lambda target: os.path.relpath(target, Path(out).parent).replace(
            "\\", "/"
        )
        rows.append(
            {
                "id": index,
                "name": names[position]
                if names and position < len(names)
                else f"scene_{index:02d}",
                "duration": duration,
                "scene": relative(path) + "?preview=1",
                "audio": relative(audio) if audio.is_file() else None,
                "words": json.loads(words.read_text(encoding="utf-8"))
                if words.is_file()
                else [],
                "fragment": fragment.read_text(encoding="utf-8")
                if fragment.is_file()
                else "",
            }
        )
    _ensure_bg()
    template = (Path(config.ROOT) / "templates" / "preview.html").read_text(
        encoding="utf-8"
    )
    data = json.dumps({"scenes": rows}, ensure_ascii=False, allow_nan=False).replace(
        "<", "\\u003c"
    )
    values = {
        "@@TITLE@@": html.escape(str(config.PROJECT_TITLE)),
        "@@COUNT@@": str(len(rows)),
        "@@TOTAL@@": f"{sum(values):.3f}",
        "@@DATA@@": data,
    }
    import re

    result = re.sub(
        r"@@(?:TITLE|COUNT|TOTAL|DATA)@@", lambda match: values[match.group()], template
    )
    atomic_text(out, result)
    print(f"[preview] {len(rows)} scenes -> {out}")
    return out


if __name__ == "__main__":
    from pipeline.workflow import stage_preview
    from pipeline.io_utils import project_lock

    with project_lock(config.ROOT):
        stage_preview()
