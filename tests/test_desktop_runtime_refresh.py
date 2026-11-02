import tempfile
import unittest
from pathlib import Path
from desktop.entry import refresh_renderer_code


class RuntimeRefreshTest(unittest.TestCase):
    def test_upgrade_refreshes_code_and_preserves_customer_media(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            resources, runtime = root / 'bundle', root / 'runtime'
            (resources / 'remotion-app/scripts').mkdir(parents=True)
            (resources / 'remotion-app/scripts/render.mjs').write_text('new renderer')
            (runtime / 'scripts').mkdir(parents=True)
            (runtime / 'scripts/render.mjs').write_text('old renderer')
            (runtime / 'public/assets').mkdir(parents=True)
            (runtime / 'public/assets/customer.mp4').write_bytes(b'original media')
            (runtime / '.cache').mkdir()
            (runtime / '.cache/keep').write_text('cache')
            refresh_renderer_code(resources, runtime)
            refresh_renderer_code(resources, runtime)
            self.assertEqual((runtime / 'scripts/render.mjs').read_text(), 'new renderer')
            self.assertEqual((runtime / 'public/assets/customer.mp4').read_bytes(), b'original media')
            self.assertEqual((runtime / '.cache/keep').read_text(), 'cache')
            self.assertFalse(list(runtime.rglob('*.upgrade-tmp')))
