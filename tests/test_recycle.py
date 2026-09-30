"""Recycle boundaries and helper protocol; mocked calls are not OS acceptance."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from pipeline import recycle


class RecycleBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / "output"
        self.output.mkdir()
        self.target = self.output / "generated.txt"
        self.target.write_text("generated", encoding="utf-8")
        self.bin = self.root / "retained"
        self.bin.mkdir()
        self.addCleanup(mock.patch.stopall)
        # Exercise the wrapper without launching a host tool on either OS.
        mock.patch.object(recycle, "os", SimpleNamespace(name="nt")).start()
        self.backend = mock.patch.object(recycle, "_recycle_windows").start()

    def test_success_moves_and_retains_generated_bytes(self):
        self.backend.side_effect = lambda path, root: path.rename(self.bin / path.name)
        recycle.recycle_generated(self.target, self.output)
        self.backend.assert_called_once_with(self.target.resolve(), self.output.resolve())
        self.assertFalse(self.target.exists())
        self.assertEqual((self.bin / self.target.name).read_text(), "generated")

    def test_missing_generated_target_is_noop(self):
        recycle.recycle_generated(self.output / "absent.txt", self.output)
        self.backend.assert_not_called()

    def test_rejects_root_and_outside_paths(self):
        outside = self.root / "original.txt"
        outside.write_text("original", encoding="utf-8")
        for path in (self.output, outside, self.output / ".." / outside.name):
            with self.subTest(path=path), self.assertRaises(ValueError):
                recycle.recycle_generated(path, self.output)
        self.backend.assert_not_called()
        self.assertEqual(outside.read_text(), "original")

    def _symlink(self, link, target, *, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"symlink creation unavailable: {error}")

    def test_rejects_target_symlink(self):
        link = self.output / "link.txt"
        self._symlink(link, self.target)
        with self.assertRaises(ValueError):
            recycle.recycle_generated(link, self.output)
        self.backend.assert_not_called()
        self.assertTrue(self.target.exists())

    def test_rejects_dangling_symlink(self):
        link = self.output / "broken.txt"
        self._symlink(link, self.output / "absent.txt")
        with self.assertRaises(ValueError):
            recycle.recycle_generated(link, self.output)
        self.backend.assert_not_called()

    def test_rejects_ancestor_symlink_escape(self):
        outside = self.root / "originals"
        outside.mkdir()
        original = outside / "original.txt"
        original.write_text("original", encoding="utf-8")
        link = self.output / "link"
        self._symlink(link, outside, directory=True)
        with self.assertRaises(ValueError):
            recycle.recycle_generated(link / original.name, self.output)
        self.backend.assert_not_called()
        self.assertEqual(original.read_text(), "original")

    def test_backend_failure_preserves_source_without_fallback(self):
        self.backend.side_effect = PermissionError("locked")
        with self.assertRaisesRegex(PermissionError, "locked"):
            recycle.recycle_generated(self.target, self.output)
        self.backend.assert_called_once()
        self.assertEqual(self.target.read_text(), "generated")

    def test_backend_noop_is_not_success(self):
        with self.assertRaisesRegex(OSError, "target still exists"):
            recycle.recycle_generated(self.target, self.output)
        self.backend.assert_called_once()
        self.assertTrue(self.target.exists())

    def test_non_windows_backend_is_also_verified(self):
        backend = mock.Mock()
        with (
            mock.patch.object(recycle, "os", SimpleNamespace(name="posix")),
            mock.patch.dict("sys.modules", {"send2trash": SimpleNamespace(send2trash=backend)}),
            self.assertRaisesRegex(OSError, "target still exists"),
        ):
            recycle.recycle_generated(self.target, self.output)
        backend.assert_called_once_with(str(self.target.resolve()))
        self.assertTrue(self.target.exists())


class WindowsHelperContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.target = self.root / "generated.txt"
        self.target.write_text("generated", encoding="utf-8")
        self.helper = self.root / "trusted helper.ps1"
        self.helper.write_text("# inert unit fixture; never executed", encoding="utf-8")
        self.addCleanup(mock.patch.stopall)
        self.environment = {"VIDEO_RECYCLE_TOOL": str(self.helper)}
        mock.patch.object(
            recycle, "os", SimpleNamespace(name="nt", environ=self.environment)
        ).start()
        self.runner = mock.patch.object(recycle.subprocess, "run").start()
        self.runner.return_value = subprocess.CompletedProcess(
            [], 0, '{"status":"recycled"}', ""
        )

    def test_explicit_helper_protocol_and_source_postcondition(self):
        retained = self.root / "retained.txt"

        def run(command, **kwargs):
            self.target.rename(retained)
            return subprocess.CompletedProcess(command, 0, '{"status":"recycled"}', "")

        self.runner.side_effect = run
        recycle.recycle_generated(self.target, self.root)
        args, kwargs = self.runner.call_args
        self.assertEqual(args[0], [
            "pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.helper),
            "-LiteralPath", str(self.target.resolve()), "-AllowedRoot", str(self.root.resolve()), "-Json",
        ])
        self.assertEqual(kwargs["timeout"], 90)
        self.assertNotIn("shell", kwargs)
        self.assertEqual(retained.read_text(), "generated")

    def test_unconfigured_existing_legacy_helper_remains_compatible(self):
        self.environment.clear()
        with mock.patch.object(recycle, "RECYCLE_TOOL", self.helper):
            recycle._recycle_windows(self.target, self.root)
        self.assertEqual(self.runner.call_args.args[0][5], str(self.helper))

    def test_unconfigured_missing_legacy_helper_fails_closed(self):
        self.environment.clear()
        with (
            mock.patch.object(recycle, "RECYCLE_TOOL", self.root / "missing.ps1"),
            self.assertRaisesRegex(OSError, "VIDEO_RECYCLE_TOOL"),
        ):
            recycle._recycle_windows(self.target, self.root)
        self.runner.assert_not_called()
        self.assertTrue(self.target.exists())

    def test_invalid_explicit_helper_never_falls_back(self):
        with mock.patch.object(recycle, "RECYCLE_TOOL", self.helper):
            for value in ("", "relative.ps1", str(self.root / "missing.ps1"), str(self.root)):
                self.environment["VIDEO_RECYCLE_TOOL"] = value
                with self.subTest(value=value), self.assertRaises(OSError):
                    recycle._recycle_windows(self.target, self.root)
        self.runner.assert_not_called()
        self.assertTrue(self.target.exists())

    def test_nonzero_helper_exit_reports_failure(self):
        self.runner.return_value = subprocess.CompletedProcess([], 1, "", "locked")
        with self.assertRaisesRegex(OSError, "locked"):
            recycle.recycle_generated(self.target, self.root)
        self.runner.assert_called_once()
        self.assertTrue(self.target.exists())

    def test_timeout_reports_uncertain_state_without_retry(self):
        self.runner.side_effect = subprocess.TimeoutExpired(["pwsh"], 90)
        with self.assertRaisesRegex(OSError, "timed out.*verify its state"):
            recycle.recycle_generated(self.target, self.root)
        self.runner.assert_called_once()
        self.assertTrue(self.target.exists())

    def test_invalid_receipts_are_not_success(self):
        for value in ("", "not json", "null", "[]", "1", '"recycled"', "{}", '{"status":"failed"}'):
            self.runner.return_value = subprocess.CompletedProcess([], 0, value, "")
            with self.subTest(value=value), self.assertRaises(OSError):
                recycle.recycle_generated(self.target, self.root)
        self.assertTrue(self.target.exists())

    def test_success_receipt_without_move_is_failure(self):
        with self.assertRaisesRegex(OSError, "target still exists"):
            recycle.recycle_generated(self.target, self.root)
        self.runner.assert_called_once()
        self.assertTrue(self.target.exists())


if __name__ == "__main__":
    unittest.main()
