"""Fish SSE timestamps: latest snapshot per chunk, transport audio concatenated.

Protocol reference: docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech-stream-with-timestamps
Native timestamps remain opt-in; they do not certify pronunciation accuracy.
"""

import base64
import json
import time
from pipeline.build_scene import validate_words
from pipeline.io_utils import positive
from pipeline.artifact_identity import sha256_file, read_record


def decode(lines, output):
    snapshots = {}
    count = 0
    deadline = time.monotonic() + 180
    for raw in lines:
        if time.monotonic() > deadline:
            raise TimeoutError("Fish stream exceeded the request deadline")
        line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        if not line or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        event = json.loads(data)
        if "error" in event:
            raise RuntimeError("Fish stream returned an error event")
        audio = base64.b64decode(event["audio_base64"], validate=True)
        output.write(audio)
        count += len(audio)
        alignment = event.get("alignment")
        if alignment is not None:
            seq = event.get("chunk_seq")
            if type(seq) is not int or seq < 0:
                raise ValueError("invalid Fish chunk sequence")
            offset = positive(
                event.get("chunk_audio_offset_sec"), "chunk offset", zero=True
            )
            snapshots[seq] = (offset, alignment)
    if not count or not snapshots:
        raise RuntimeError("Fish returned no audio or timestamp snapshots")
    if sorted(snapshots) != list(range(max(snapshots) + 1)):
        raise RuntimeError("Fish alignment chunks are incomplete")
    words = []
    for seq, (offset, alignment) in sorted(snapshots.items()):
        positive(alignment.get("audio_duration"), "chunk audio duration")
        for segment in alignment["segments"]:
            start = positive(segment.get("start"), "segment start", zero=True)
            end = positive(segment.get("end"), "segment end", zero=True)
            words.append(
                {
                    "word": segment["text"],
                    "start": round(offset + start, 3),
                    "end": round(offset + end, 3),
                }
            )
    if not words:
        raise RuntimeError("Fish alignment contains no words")
    return validate_words(words)


def load(audio_path):
    value = read_record(str(audio_path) + ".timestamps.json")
    if (
        not value
        or value.get("schema") != "video-scaffold.fish-timestamps.v1"
        or value.get("audio_sha256") != sha256_file(audio_path)
    ):
        raise RuntimeError(
            "native Fish timestamps missing or not bound to this audio; run tts --force with VIDEO_TIMING_SOURCE=fish"
        )
    return validate_words(value["words"])
