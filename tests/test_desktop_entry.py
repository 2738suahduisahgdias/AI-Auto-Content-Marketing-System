import unittest
from unittest import mock
from desktop.entry import main

class DesktopMountGuard(unittest.TestCase):
    def test_existing_stale_mount_directory_is_not_a_workspace(self):
        with mock.patch('sys.argv',['entry.py','--root','/Volumes/offline-test/project','--no-browser']), mock.patch('pathlib.Path.is_mount',return_value=False), mock.patch('pathlib.Path.exists',return_value=True), mock.patch('pathlib.Path.mkdir') as mkdir:
            with self.assertRaisesRegex(RuntimeError,'不会在系统盘'):
                main()
            mkdir.assert_not_called()
