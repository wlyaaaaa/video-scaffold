"""Isolated installed Chrome, with explicit sampling instead of wall-clock capture."""
from __future__ import annotations

from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlparse, unquote

from .common import chrome_path, temp_workspace


def evaluate(page, expression, argument=None, *, timeout=30):
    """Bound both JS execution and a returned Promise, using the host clock.

    Playwright's page timeout does not bound evaluate's awaited promises.
    CDP bounds synchronous execution; the host polls a promise result.
    """
    client = getattr(page, "_webfilm_evaluation_client", None)
    if client is None:
        client = page.context.new_cdp_session(page)
        page._webfilm_evaluation_client = client
    token = "__webfilm_eval_result"
    invocation = f"({expression})({json.dumps(argument, ensure_ascii=False)})"
    source = f"(() => {{ window.{token}={{status:'pending'}}; Promise.resolve({invocation}).then(value=>window.{token}={{status:'ok',value}},error=>window.{token}={{status:'error',message:String(error?.stack||error)}}); return true; }})()"
    result = client.send("Runtime.evaluate", {"expression": source, "returnByValue": True, "timeout": timeout*1000})
    if result.get("exceptionDetails"):
        raise RuntimeError(str(result["exceptionDetails"]))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = client.send("Runtime.evaluate", {"expression": f"window.{token}", "returnByValue": True, "timeout": min(timeout, 5)*1000})
        value = result.get("result", {}).get("value", {})
        if value.get("status") == "ok":
            return value.get("value")
        if value.get("status") == "error":
            raise RuntimeError(value["message"])
        time.sleep(0.005)
    raise TimeoutError(f"Page operation/Promise did not complete within {timeout} seconds")


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'")
        super().end_headers()


@contextmanager
def local_server(root):
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


CAPTURE_INIT = r"""({seed}) => {
  window.__WEBFILM_CANVAS_CONTEXTS__ = new WeakMap();
  const getContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function(type, ...args) {
    const context = getContext.call(this, type, ...args);
    if (context) window.__WEBFILM_CANVAS_CONTEXTS__.set(this, {type, context});
    return context;
  };
  window.__WEBFILM_CAPTURE__ = true;
  window.__WEBFILM_TIME__ = 0;
  window.__WEBFILM_VIOLATIONS__ = [];
  let randomState = seed >>> 0;
  Math.random = () => {randomState = (Math.imul(randomState,1664525)+1013904223)>>>0;return randomState/4294967296;};
  const epoch = 1700000000000, RealDate = Date;
  const milliseconds = () => window.__WEBFILM_TIME__ * 1000;
  window.Date = new Proxy(RealDate, {
    construct(target,args) {return Reflect.construct(target,args.length ? args : [epoch+milliseconds()]);},
    apply() {return new RealDate(epoch+milliseconds()).toString();},
    get(target,key) {return key==='now' ? () => epoch+milliseconds() : Reflect.get(target,key);}
  });
  Object.defineProperty(performance,'now',{value:milliseconds});
  try {Object.defineProperty(Event.prototype,'timeStamp',{get:milliseconds});} catch (_) {}
  window.requestAnimationFrame = () => 0;
  window.cancelAnimationFrame = () => {};
  for (const name of ['setTimeout','setInterval']) {
    window[name] = () => {window.__WEBFILM_VIOLATIONS__.push('Wall-clock timer '+name+' in capture path');return 0;};
  }
  for (const name of ['WebSocket','EventSource','RTCPeerConnection']) {
    window[name] = function(){window.__WEBFILM_VIOLATIONS__.push('Forbidden network API '+name);throw new Error(name+' forbidden');};
  }
  window.addEventListener('securitypolicyviolation', e => {
    if (e.blockedURI && !['inline','eval'].includes(e.blockedURI)) window.__WEBFILM_VIOLATIONS__.push('Blocked request '+e.blockedURI);
  });
}"""


@contextmanager
def work_page(root, config, parent, *, width, height, capture=True, init_script=None, require_api=True,
              hardware=False):
    from playwright.sync_api import sync_playwright
    requests, blocked, failures = [], [], []
    with temp_workspace(parent, "chrome-", disposable=hardware) as temporary, local_server(root) as origin:
        # Playwright itself also writes temporary browser artifacts; direct them
        # to the task-owned directory, never to the user's Chrome profile.
        env = dict(os.environ, TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary))
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                str(temporary / "profile"), executable_path=chrome_path(), headless=True,
                viewport={"width": width, "height": height}, device_scale_factor=1,
                locale="zh-CN", timezone_id="Asia/Shanghai", color_scheme="light",
                reduced_motion="no-preference", service_workers="block", env=env,
                args=(["--disable-frame-rate-limit", "--disable-gpu-vsync"] if hardware else ["--disable-gpu"]) +
                     (["--enable-features=MediaFoundationD3DVideoProcessing,MediaFoundationSharedImageEncode"] if hardware and os.name == "nt" else []) +
                     ["--disable-background-networking", "--disable-component-update",
                      "--disable-extensions", "--disable-sync", "--force-color-profile=srgb",
                      "--hide-scrollbars"],
            )
            try:
                if init_script is not None:
                    context.add_init_script(init_script)
                elif capture:
                    context.add_init_script("(" + CAPTURE_INIT + ")({seed:" + str(config.get("seed", 829)) + "})")
                def route(request_route):
                    request = request_route.request
                    parsed = urlparse(request.url)
                    if request.url.startswith(origin + "/"):
                        relative = unquote(parsed.path).lstrip("/")
                        local = (root / relative).resolve()
                        if not local.is_relative_to(root) or (not local.is_file() and not local.is_dir()):
                            blocked.append(request.url)
                            request_route.abort()
                            return
                        requests.append(relative)
                        request_route.continue_()
                    elif parsed.scheme in ("data", "blob"):
                        request_route.continue_()
                    else:
                        blocked.append(request.url)
                        request_route.abort()
                context.route("**/*", route)
                if hasattr(context, "route_web_socket"):
                    def websocket(ws):
                        blocked.append(ws.url)
                        ws.close()
                    context.route_web_socket("**/*", websocket)
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(15000)
                page.on("pageerror", lambda error: failures.append(str(error)))
                page.goto(origin + "/" + config.get("entry", "index.html"), wait_until="load", timeout=30000)
                evaluate(page, "async () => { await document.fonts.ready; await Promise.all([...document.images].map(i => i.decode())); if(window.webfilm?.ready) await window.webfilm.ready; }")
                valid = evaluate(page, "() => !!window.webfilm && typeof window.webfilm.render === 'function'")
                if require_api and not valid:
                    raise ValueError("Entry page must provide window.webfilm.render(t)")
                declared = evaluate(page, "() => window.webfilm?.duration")
                if require_api and declared != config["duration"]:
                    raise ValueError("webfilm.duration does not match work.json")
                assert_runtime(page, {"blocked": blocked, "failures": failures})
                yield page, {"requests": requests, "blocked": blocked, "failures": failures,
                             "chrome": context.browser.version, "chrome_path": chrome_path(), "origin": origin}
            finally:
                context.close()


def seek(page, seconds):
    evaluate(page, """async t => {
        window.__WEBFILM_TIME__ = t;
        await window.webfilm.render(t);
        for (const animation of document.getAnimations()) { animation.pause(); animation.currentTime = t*1000; }
        document.documentElement.style.scrollBehavior = 'auto';
        document.body.getBoundingClientRect();
    }""", seconds)


def assert_runtime(page, evidence):
    violations = evaluate(page, "() => window.__WEBFILM_VIOLATIONS__ || []")
    errors = evidence["blocked"] + evidence["failures"] + violations
    if errors:
        raise ValueError("Work runtime failed rules/readiness checks: " + "; ".join(dict.fromkeys(errors)))
