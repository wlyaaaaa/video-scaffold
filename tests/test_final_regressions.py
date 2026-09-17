from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
from urllib.request import urlopen
import config
from pipeline import contracts, subtitles, preview
from helpers import project_graph


class FinalRegressionTests(unittest.TestCase):
    def test_empty_local_key_preserves_environment_fallback(self):
        stub = types.ModuleType("secret_local")
        stub.FISH_API_KEY = ""
        with (
            mock.patch.dict(sys.modules, {"secret_local": stub}),
            mock.patch.object(config, "FISH_API_KEY", "environment-fixture"),
        ):
            self.assertEqual(config.get_fish_api_key(), "environment-fixture")

    def test_nonempty_local_key_retains_existing_priority(self):
        stub = types.ModuleType("secret_local")
        stub.FISH_API_KEY = "local-fixture"
        with (
            mock.patch.dict(sys.modules, {"secret_local": stub}),
            mock.patch.object(config, "FISH_API_KEY", "environment-fixture"),
        ):
            self.assertEqual(config.get_fish_api_key(), "local-fixture")

    def test_optional_subtitles_must_match_current_timeline(self):
        with project_graph() as root:
            subtitles.export()
            contracts.require_subtitles()
            (root / "output" / "subtitles.srt").write_text("edited", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                contracts.require_subtitles()

    def test_http_preview_serves_only_referenced_relative_asset(self):
        from pipeline.serve import preview_server
        from urllib.error import HTTPError

        with project_graph() as root, mock.patch.object(preview, "_ensure_bg"):
            hero = root / "assets" / "hero.png"
            hero.write_bytes(b"fixture-image")
            scene = root / "scene_html" / "scene_01.html"
            scene.write_text(
                scene.read_text(encoding="utf-8").replace(
                    "<!-- @@SCENE_CONTENT@@ -->", ""
                )
                + '<svg><image href="../assets/hero.png"/></svg>',
                encoding="utf-8",
            )
            preview.build()
            with preview_server() as url:
                base = url.split("/output/", 1)[0]
                self.assertEqual(
                    urlopen(base + "/assets/hero.png").read(), b"fixture-image"
                )
                html = urlopen(base + "/scene_html/scene_01.html").read().decode()
                self.assertIn("/_assets/", html)
                with self.assertRaises(HTTPError):
                    urlopen(base + "/config.py")

    def test_direct_cleanup_dry_run_writes_no_lock(self):
        source = Path(config.ROOT) / "pipeline" / "cleanup.py"
        code = "import runpy,sys,config;config.ROOT=sys.argv[1];sys.argv=['cleanup','--dry-run'];runpy.run_module('pipeline.cleanup',run_name='__main__')"
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run(
                [sys.executable, "-B", "-c", code, temporary],
                cwd=config.ROOT,
                capture_output=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(Path(temporary).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
