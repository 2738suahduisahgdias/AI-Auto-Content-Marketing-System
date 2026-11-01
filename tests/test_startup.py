import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from content_workbench.api.v2 import V2Application


class StartupCase(unittest.TestCase):
    def test_clean_database_initializes_twice_and_preserves_variant_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "test.db"
            with patch.object(app, "ROOT", root), patch.object(app, "DB_PATH", db):
                app.init_db()
                V2Application(db, root, app.create_task)
                task = app.create_task({"title": "Startup regression"})
                content_id = task["content_id"]
                with app.connect() as conn:
                    cursor = conn.execute(
                        """INSERT INTO files(content_id,kind,original_name,relative_path,size,created_at)
                        VALUES (?,'video','test.mp4','renders/test.mp4',0,?)""",
                        (content_id, app.now()),
                    )
                    file_id = cursor.lastrowid
                    conn.execute(
                        "INSERT INTO video_variants VALUES (?,?,?,?)",
                        (content_id, file_id, "test-digest", "2026-11-01T00:00:00Z"),
                    )
                V2Application(db, root, app.create_task)
                with app.connect() as conn:
                    row = conn.execute("SELECT * FROM video_variants").fetchone()
                    self.assertEqual("test-digest", row["file_sha256"])
                    self.assertEqual("2026-11-01T00:00:00Z", row["approved_at"])
                    self.assertEqual([], conn.execute("PRAGMA foreign_key_check").fetchall())
