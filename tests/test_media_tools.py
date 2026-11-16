import tempfile
import unittest
from pathlib import Path

from content_workbench.domain.errors import DomainError
from content_workbench.media.tools import config, ocr_python, save


class MediaToolsTest(unittest.TestCase):
    def test_invalid_paths_do_not_replace_saved_config(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model = root / "models"
            model.mkdir()
            save(root, {"openvoice_root": str(model)})
            with self.assertRaises(DomainError):
                save(root, {"whisper_python": str(root / "missing")})
            self.assertEqual(config(root), {"openvoice_root": str(model.resolve())})
            save(root, {"openvoice_root": ""})
            self.assertEqual(config(root), {})

    def test_python_symlink_preserves_virtual_environment(self):
        import sys

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            binary = root / "env/bin/python"
            binary.parent.mkdir(parents=True)
            binary.symlink_to(sys.executable)
            save(root, {"whisper_python": str(binary)})
            self.assertEqual(config(root)["whisper_python"], str(binary.absolute()))

    def test_ocr_python_uses_saved_workspace_path(self):
        import sys

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            binary = root / "env/bin/python"
            binary.parent.mkdir(parents=True)
            binary.symlink_to(sys.executable)
            save(root, {"ocr_python": str(binary)})
            self.assertEqual(ocr_python(root), binary.absolute())

    def test_ocr_python_preserves_development_default(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            binary = root / ".venv-topics/bin/python"
            binary.parent.mkdir(parents=True)
            binary.touch()
            self.assertEqual(ocr_python(root), binary)

    def test_desktop_uses_bundled_python_before_development_paths(self):
        from unittest.mock import patch

        from content_workbench.media.tools import demucs_python

        with tempfile.TemporaryDirectory() as d:
            resources = Path(d)
            binary = resources / "python/bin/python3.9"
            binary.parent.mkdir(parents=True)
            binary.touch()
            with (
                patch("content_workbench.media.tools.PROJECT_ROOT", resources),
                patch.dict("os.environ", {"CONTENT_AGENT_DESKTOP": "1"}),
            ):
                self.assertEqual(ocr_python(Path("/unused-workspace")), binary)
                self.assertEqual(demucs_python(Path("/unused-workspace")), binary)
