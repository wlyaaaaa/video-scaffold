"""Local live webpage player; no video, soundtrack file, or work mutation."""
from __future__ import annotations

from contextlib import contextmanager
from functools import partial
from html import escape
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import re
import subprocess
import threading
from urllib.parse import quote, unquote, urlparse

from .browser import Handler
from .check import load_work
from .common import chrome_path, NO_WINDOW

PREFIX = "/__webfilm_preview__/"
CAPTURE = "<script>window.__WEBFILM_CAPTURE__=true;window.__WEBFILM_TIME__=0;</script>"


def preview_html(config, width, height):
    title = escape(config.get("title", "网页作品"))
    settings = json.dumps(dict(config, width=width, height=height), ensure_ascii=False).replace("<", "\\u003c")
    entry = quote(config.get("entry", "index.html"), safe="/")
    return f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · 实时预览</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f4f6f3;color:#173c2e;font:16px system-ui}}
main{{max-width:1280px;margin:auto;padding:24px}}h1{{font-size:24px;margin:0 0 8px}}
p{{color:#627367;margin:0 0 20px}}#stage{{position:relative;overflow:hidden;background:#fff;
width:min(100%,calc((100vh - 220px)*{width}/{height}));aspect-ratio:{width}/{height};margin:auto}}
iframe{{border:0;position:absolute;top:0;left:0;transform-origin:0 0;width:{width}px;height:{height}px}}
#controls{{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:20px}}
button{{border:1px solid #b3c5b8;border-radius:8px;padding:9px 16px;background:white;color:inherit;
font:inherit;cursor:pointer}}#play{{background:#245a40;color:white}}button:disabled{{opacity:.5}}
input{{flex:1;min-width:160px;accent-color:#245a40}}output{{font-variant-numeric:tabular-nums}}
#status{{display:block;margin-top:12px;color:#627367}}:focus-visible{{outline:3px solid #84b09a}}
</style><main><h1>{title}</h1><p>实时有声预览 · 拖动进度查看 · 修改作品后刷新</p>
<div id="stage"><iframe id="work" src="/{entry}" title="作品画面" allow="autoplay"></iframe></div>
<div id="controls"><button id="play" disabled>播放</button><button id="restart" disabled>从头播放</button>
<input id="seek" aria-label="播放进度" type="range" min="0" max="{config['duration']}" step="0.01" value="0" disabled>
<output id="clock">0.0 / {config['duration']:.1f} 秒</output><button id="reload">刷新作品</button></div>
<span id="status" role="status">正在加载作品…</span></main>
<script>window.webfilmPreviewConfig={settings};</script><script src="{PREFIX}player.js"></script></html>"""


@contextmanager
def preview_server(folder, *, width=1920, height=1080, max_duration=120, narration_path=None):
    root, _ = load_work(folder, max_duration=max_duration)
    narration = Path(narration_path).resolve() if narration_path is not None else None
    if narration is not None and not narration.is_file():
        raise ValueError("Narration must be an existing local audio file")
    if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in (width, height)):
        raise ValueError("Preview width and height must be positive integers")

    class PreviewHandler(Handler):
        def do_GET(self):
            relative = unquote(urlparse(self.path).path).lstrip("/")
            local = (root / relative).resolve()
            try:
                _, config = load_work(root, max_duration=max_duration)
                config.pop("narration_url", None)
                if narration is not None:
                    config["narration_url"] = PREFIX + "narration"
                if relative == PREFIX.lstrip("/"):
                    data, kind = preview_html(config, width, height).encode("utf-8"), "text/html; charset=utf-8"
                elif relative == PREFIX.lstrip("/") + "player.js":
                    data, kind = Path(__file__).with_name("preview.js").read_bytes(), "text/javascript; charset=utf-8"
                elif narration is not None and relative == PREFIX.lstrip("/") + "narration":
                    data, kind = narration.read_bytes(), self.guess_type(str(narration))
                elif not local.is_relative_to(root) or not local.is_file():
                    self.send_error(404)
                    return
                elif local == (root / config.get("entry", "index.html")).resolve():
                    source = local.read_text(encoding="utf-8-sig")
                    match = re.search(r"(?is)<head\b[^>]*>", source) or re.search(r"(?is)<!doctype\s[^>]*>", source)
                    at = match.end() if match else 0
                    data, kind = (source[:at] + CAPTURE + source[at:]).encode("utf-8"), "text/html; charset=utf-8"
                else:
                    return super().do_GET()
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except (OSError, ValueError) as error:
                self.send_error(500, str(error))

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(PreviewHandler, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}{PREFIX}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def serve_preview(folder, *, width=1920, height=1080, max_duration=120, open_browser=False, narration_path=None):
    """An explicit local narration starts at zero; excess is trimmed and a short tail is silent."""
    with preview_server(folder, width=width, height=height, max_duration=max_duration, narration_path=narration_path) as url:
        print(f"实时预览：{url}\n按 Ctrl+C 停止本地预览服务。", flush=True)
        if open_browser:
            subprocess.Popen([chrome_path(), url], creationflags=NO_WINDOW)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            return {"schema": "webfilm.preview.v1", "url": url, "stopped": True}
