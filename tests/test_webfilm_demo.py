"""Demo isolation and portable work configuration, without launching hardware."""
import json
from pathlib import Path
import tempfile
import unittest

from webfilm.check import check_work
from webfilm.demo import create_demo, PROMPT


class WebfilmDemoTests(unittest.TestCase):
    def test_every_demo_is_a_self_contained_valid_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "六类作品"
            result = create_demo(root)
            self.assertEqual(result["works"], ["animation", "interactive", "card", "opener", "outro", "cover"])
            durations = {"animation": 20, "interactive": 12, "card": 8, "opener": 4, "outro": 6, "cover": 1}
            for name, duration in durations.items():
                with self.subTest(work=name):
                    work = root / name
                    report = check_work(work)
                    self.assertTrue(report["pass"], report["errors"])
                    self.assertEqual(report["duration"], duration)
                    self.assertTrue((work / "runtime.js").is_file())
            site = json.loads((root / "site.json").read_text(encoding="utf-8"))
            self.assertEqual(site["prompt"], PROMPT)
            self.assertEqual((root / "prompt.txt").read_text(encoding="utf-8").strip(), PROMPT)
            self.assertEqual(len(site["entries"]), 2)
            for entry in site["entries"]:
                for version in entry["versions"]:
                    self.assertEqual(version["work"], "animation")
            actions = json.loads((root / "interactive" / "actions.json").read_text(encoding="utf-8"))
            self.assertEqual([action["type"] for action in actions["actions"]], ["move", "click", "scroll", "hover", "wait"])

    def test_nonempty_target_is_not_touched(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / "旁白原件.txt"
            original.write_text("不能覆盖", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                create_demo(root)
            self.assertEqual(original.read_text(encoding="utf-8"), "不能覆盖")
            self.assertEqual(list(root.iterdir()), [original])

    def test_existing_empty_directory_is_allowed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "empty"
            root.mkdir()
            create_demo(root)
            self.assertTrue((root / "animation" / "index.html").is_file())
            with self.assertRaises(FileExistsError):
                create_demo(root)


if __name__ == "__main__":
    unittest.main()
