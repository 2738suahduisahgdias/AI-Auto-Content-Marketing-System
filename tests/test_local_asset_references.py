import tempfile
import unittest
from pathlib import Path
from content_workbench.storage.db import connect, expand_schema
from content_workbench.domain.services import Workbench
from content_workbench.domain.errors import DomainError

class LocalReferenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.db = self.root / 'test.db'
        with connect(self.db) as conn:
            expand_schema(conn)
        self.wb = Workbench(self.db, self.root / 'data')
        self.original = self.root / 'source.srt'
        self.original.write_text('1\n00:00:00,000 --> 00:00:01,000\nhello\n')

    def asset(self, asset_id):
        with self.wb.conn(readonly=True) as conn:
            return conn.execute('SELECT * FROM wb_assets WHERE id=?', (asset_id,)).fetchone()

    def test_reference_relink_preserves_identity_and_never_copies(self):
        asset_id = self.wb.import_local_asset(self.original)
        self.assertEqual(self.wb.resolve_asset_path(self.asset(asset_id)), self.original)
        self.assertFalse((self.wb.root / 'assets').exists())
        moved = self.root / 'moved.srt'
        self.original.rename(moved)
        with self.assertRaises(DomainError):
            self.wb.resolve_asset_path(self.asset(asset_id))
        wrong = self.root / 'wrong.srt'
        wrong.write_text('wrong')
        with self.assertRaises(DomainError):
            self.wb.relink_asset(asset_id, wrong)
        self.assertEqual(self.wb.relink_asset(asset_id, moved), asset_id)
        self.assertEqual(self.wb.resolve_asset_path(self.asset(asset_id), verify=True), moved)

    def test_copy_survives_original_removal(self):
        asset_id = self.wb.import_local_asset(self.original, copy=True)
        self.assertTrue(self.original.exists())
        self.original.unlink()
        self.assertTrue(self.wb.resolve_asset_path(self.asset(asset_id)).is_file())

    def test_modified_reference_and_managed_escape_rejected(self):
        asset_id = self.wb.import_local_asset(self.original)
        self.original.write_text('changed')
        with self.assertRaises(DomainError):
            self.wb.resolve_asset_path(self.asset(asset_id), verify=True)
        asset = dict(self.asset(asset_id))
        asset.update(source_json='{}', storage_key=str(self.original))
        with self.assertRaises(DomainError):
            self.wb.resolve_asset_path(asset)

    def test_reference_upgraded_to_copy_keeps_id(self):
        asset_id = self.wb.import_local_asset(self.original)
        self.assertEqual(self.wb.import_local_asset(self.original, copy=True), asset_id)
        self.original.unlink()
        self.assertTrue(self.wb.resolve_asset_path(self.asset(asset_id)).is_file())
