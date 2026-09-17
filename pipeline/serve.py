"""Explicit short-lived loopback preview server. It serves only preview dependencies."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse, unquote, quote
import hashlib
import mimetypes
import os
import threading
import config
from pipeline.io_utils import safe_print as print
from pipeline.resources import inventory
from pipeline.indexed_files import indexed_files


def create_server():
    root = Path(config.ROOT).resolve()
    preview = Path(config.DIR_OUTPUT) / "preview.html"
    if not preview.is_file():
        raise RuntimeError("run preview before serve")
    mapping = {"/": preview, "/output/preview.html": preview}
    for path in [
        Path(config.DIR_OUTPUT) / "_preview_bg.jpg",
        *map(
            Path, indexed_files(os.path.join(config.DIR_SCENE, "scene_*.html")).values()
        ),
        *map(
            Path, indexed_files(os.path.join(config.DIR_AUDIO, "audio_*.mp3")).values()
        ),
    ]:
        if path.is_file():
            mapping["/" + path.resolve().relative_to(root).as_posix()] = path
    replacements = {}
    for resource in inventory(
        indexed_files(os.path.join(config.DIR_SCENE, "scene_*.html")).values()
    ):
        from urllib.request import url2pathname

        path = Path(url2pathname(urlparse(resource["uri"]).path))
        route = (
            "/_assets/"
            + hashlib.sha256(resource["uri"].encode()).hexdigest()
            + path.suffix
        )
        mapping[route] = path
        replacements[resource["uri"]] = route
        try:
            mapping["/" + path.resolve().relative_to(root).as_posix()] = path
        except ValueError:
            pass

    class Handler(BaseHTTPRequestHandler):
        def do_HEAD(self):
            self.respond(False)

        def do_GET(self):
            self.respond(True)

        def respond(self, body):
            key = unquote(urlparse(self.path).path)
            path = mapping.get(key)
            if path is None:
                self.send_error(404)
                return
            try:
                content = path.read_bytes()
                if path.suffix == ".html":
                    text = content.decode("utf-8")
                    for old, new in replacements.items():
                        text = text.replace(old, new)
                    from pipeline.resources import _Links
                    from urllib.parse import urljoin

                    parser = _Links()
                    parser.feed(text)
                    for link in parser.links:
                        if not urlparse(link).scheme and not link.startswith(
                            ("#", "/_assets/", "data:")
                        ):
                            absolute = urljoin(path.resolve().as_uri(), link)
                            if absolute in replacements:
                                text = text.replace(link, replacements[absolute])
                    content = text.encode("utf-8")
                start, end = 0, len(content) - 1
                status = 200
                header = self.headers.get("Range")
                if header and path.suffix != ".html":
                    import re

                    match = re.fullmatch(r"bytes=([0-9]+)-([0-9]*)", header)
                    if not match:
                        self.send_error(416)
                        return
                    start = int(match[1])
                    end = min(end, int(match[2])) if match[2] else end
                    if start > end:
                        self.send_error(416)
                        return
                    status = 206
                self.send_response(status)
                self.send_header(
                    "Content-Type",
                    mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                )
                self.send_header("Content-Length", str(end - start + 1))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Accept-Ranges", "bytes")
                if status == 206:
                    self.send_header(
                        "Content-Range", f"bytes {start}-{end}/{len(content)}"
                    )
                self.end_headers()
                if body:
                    self.wfile.write(content[start : end + 1])
            except (OSError, UnicodeError):
                self.send_error(500)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    return server


@contextmanager
def preview_server():
    server = create_server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/output/preview.html"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    server = create_server()
    url = f"http://127.0.0.1:{server.server_port}/output/preview.html"
    print(
        f"Preview: {url} | Ctrl+C stops this server; underlying project files are unchanged.",
        flush=True,
    )
    if args.open:
        import webbrowser

        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
