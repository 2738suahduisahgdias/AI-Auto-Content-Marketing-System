#!/usr/bin/env python3
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from desktop import slim_download


class SlimDownloadTest(unittest.TestCase):
    def test_tar_rejects_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "bad.tar"
            with tarfile.open(archive, "w") as source:
                data = b"bad"
                info = tarfile.TarInfo("../escape")
                info.size = len(data)
                source.addfile(info, io.BytesIO(data))
            with self.assertRaisesRegex(RuntimeError, "越界"):
                slim_download.extract_tar(archive, root / "target")
            self.assertFalse((root / "escape").exists())

    def test_tar_extracts_single_runtime_directory(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "runtime.tar"
            with tarfile.open(archive, "w") as source:
                data = b"python"
                info = tarfile.TarInfo("python/bin/python3")
                info.size = len(data)
                source.addfile(info, io.BytesIO(data))
            slim_download.extract_tar(archive, root / "target")
            self.assertEqual((root / "target/bin/python3").read_bytes(), data)


if __name__ == "__main__":
    unittest.main()
