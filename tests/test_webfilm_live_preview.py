"""Local preview transport and real Chrome sound-clock controls."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
from webfilm.common import chrome_path, write_json
from webfilm.preview import preview_server

class LivePreviewTests(unittest.TestCase):
    def fixture(self, root, audio="generated"):
        write_json(root / "work.json", dict(schema=1, duration=2, audio=audio))
        entry = root / "index.html"
        entry.write_text("""<!doctype html><head><meta charset="utf-8"></head><body><script>
        window.audioCalls=0;window.webfilm={duration:2,render(t){document.body.dataset.at=t;document.body.dataset.audioCalls=audioCalls;},
        audio(ctx){audioCalls++;const o=ctx.createOscillator(),g=ctx.createGain();g.gain.value=.1;
        o.connect(g);g.connect(ctx.destination);o.start(0);o.stop(2);}};
        fetch('https://example.invalid/probe').catch(()=>window.networkBlocked=true);
        </script></body>""", encoding="utf-8")
        return entry
    def narration(self, path, seconds=1):
        import struct
        import wave
        with wave.open(str(path), "wb") as voice:
            voice.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
            voice.writeframes(struct.pack("<h", 6554) * round(seconds * 48000))

    def test_serves_fresh_local_work_without_changing_original(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory) / "work"
            root.mkdir()
            entry = self.fixture(root)
            voice = Path(directory) / "voice.wav"
            self.narration(voice)
            original = entry.read_bytes()
            with preview_server(root, narration_path=voice) as url:
                with urlopen(url) as response:
                    self.assertIn("connect-src 'self'", response.headers["Content-Security-Policy"])
                    self.assertIn('iframe', response.read().decode())
                with urlopen(url.split("/__webfilm")[0] + "/index.html") as response:
                    self.assertIn(b"window.__WEBFILM_CAPTURE__=true", response.read())
                with urlopen(url + "narration") as response:
                    self.assertEqual(response.read(), voice.read_bytes())
                for path in ("/", "/voice.wav"):
                    with self.assertRaises(HTTPError):
                        urlopen(url.split("/__webfilm")[0] + path)
            self.assertEqual(entry.read_bytes(), original)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["index.html", "work.json"])

    @unittest.skipUnless(os.environ.get("WEBFILM_LIVE_PREVIEW_BROWSER_TESTS") == "1", "opt-in installed Chrome integration")
    def test_sound_once_pause_seek_end_refresh_and_silent_work(self):
        from playwright.sync_api import sync_playwright
        with TemporaryDirectory(dir=Path(__file__).parent) as directory, sync_playwright() as p:
            root = Path(directory) / "work"
            root.mkdir()
            env = dict(os.environ, TEMP=str(root), TMP=str(root), TMPDIR=str(root))
            browser = p.chromium.launch(executable_path=chrome_path(), headless=True, env=env, args=["--disable-gpu", "--disable-background-networking"])
            try:
                for audio, with_voice in (("generated", False), ("none", False), ("generated", True), ("none", True)):
                    entry = self.fixture(root, audio)
                    voice = Path(directory) / "voice.wav" if with_voice else None
                    if voice: self.narration(voice, 3 if audio == "generated" else 1)
                    with self.subTest(audio=audio, narration=with_voice), preview_server(root, narration_path=voice) as url:
                        page = browser.new_page(viewport={"width": 1280, "height": 900})
                        def route_local(route):
                            if route.request.url.endswith('/player.js'):
                                source = (Path(__file__).resolve().parents[1] / "webfilm" / "preview.js").read_text(encoding="utf-8")
                                route.fulfill(status=200, content_type="text/javascript; charset=utf-8", body="window.addEventListener('load',()=>{\n"+source+"\n});")
                            elif route.request.url.startswith(url.split('/__webfilm')[0]): route.continue_()
                            else: route.abort()
                        page.route("**/*", route_local)
                        page.add_init_script("""const original=OfflineAudioContext.prototype.startRendering;
                          OfflineAudioContext.prototype.startRendering=async function(){const b=await original.call(this);
                          window.audioPeak=Math.max(...b.getChannelData(0).slice(0,480));window.testAudio=b;return b;};
                          const start=AudioBufferSourceNode.prototype.start;
                          AudioBufferSourceNode.prototype.start=function(at,offset){window.lastAudioOffset=offset;return start.call(this,at,offset);};""")
                        page.goto(url)
                        page.wait_for_function("!document.getElementById('play').disabled")
                        work = page.frame_locator("#work")
                        self.assertEqual(work.locator("body").evaluate("()=>window.audioCalls"), int(audio == "generated"))
                        self.assertEqual(work.locator("body").get_attribute("data-audio-calls"), str(int(audio == "generated")))
                        self.assertTrue(work.locator("body").evaluate("()=>window.networkBlocked"))
                        if audio == "generated" or voice: self.assertGreater(page.evaluate("audioPeak"), .09 if audio == "generated" else .19)
                        if voice:
                            self.assertEqual(page.evaluate("testAudio.length"), 96000)
                            if audio == "none": self.assertEqual(page.evaluate("testAudio.getChannelData(0)[72000]"), 0)
                        page.locator("#play").click()
                        page.wait_for_function("webfilmPreview.position > .1")
                        page.evaluate("webfilmPreview.seek(1.25)")
                        if audio == "generated" or voice: self.assertEqual(page.evaluate("lastAudioOffset"), 1.25)
                        page.locator("#play").click()
                        paused = page.evaluate("webfilmPreview.position")
                        self.assertGreaterEqual(paused, 1.25)
                        page.wait_for_timeout(100)
                        self.assertEqual(page.evaluate("webfilmPreview.position"), paused)
                        page.locator("#seek").evaluate("e=>{e.value='.5';e.dispatchEvent(new Event('input'));}")
                        page.wait_for_function("document.querySelector('#work').contentDocument.body.dataset.at==='0.5'")
                        page.locator("#play").click()
                        page.wait_for_function("!webfilmPreview.playing && webfilmPreview.position===2")
                        self.assertEqual(work.locator("body").evaluate("()=>window.audioCalls"), int(audio == "generated"))
                        entry.write_text(entry.read_text(encoding="utf-8") + '<p id="revision">修改已刷新</p>', encoding="utf-8")
                        page.locator("#reload").click()
                        work.locator("#revision").wait_for()
                        page.close()
            finally: browser.close()
