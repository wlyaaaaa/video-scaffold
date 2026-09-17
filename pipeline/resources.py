"""Resolve the actual local dependencies of generated HTML without a browser."""

from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname
from pipeline.artifact_identity import sha256_file


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if value and (key in ("href", "xlink:href", "src") or key == "style"):
                if key == "style":
                    self.links.extend(re.findall(r"url\(['\"]?([^)'\"]+)", value))
                else:
                    self.links.append(value)


def inventory(paths):
    result = {}
    for source in paths:
        source = Path(source).resolve()
        parser = _Links()
        parser.feed(source.read_text(encoding="utf-8"))
        for uri in parser.links:
            if uri.startswith(("#", "data:")):
                continue
            parsed = urlparse(uri)
            if parsed.scheme not in ("", "file") or parsed.netloc not in (
                "",
                "localhost",
            ):
                raise ValueError(
                    f"external resource must be materialized locally before render: {uri}"
                )
            path = (
                Path(url2pathname(parsed.path))
                if parsed.scheme == "file"
                else source.parent / unquote(parsed.path)
            )
            path = path.resolve()
            if not path.is_file():
                raise FileNotFoundError(
                    f"scene file resource is missing or unreadable: {uri}"
                )
            result[path.as_uri()] = {
                "uri": path.as_uri(),
                "sha256": sha256_file(str(path)),
            }
    return [result[key] for key in sorted(result)]
