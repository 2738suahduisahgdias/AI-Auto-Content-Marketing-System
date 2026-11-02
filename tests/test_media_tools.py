import tempfile,unittest
from pathlib import Path
from content_workbench.media.tools import config,save
from content_workbench.domain.errors import DomainError
class MediaToolsTest(unittest.TestCase):
 def test_invalid_paths_do_not_replace_saved_config(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);model=root/'models';model.mkdir()
   save(root,{'openvoice_root':str(model)})
   with self.assertRaises(DomainError):save(root,{'whisper_python':str(root/'missing')})
   self.assertEqual(config(root),{'openvoice_root':str(model.resolve())})
   save(root,{'openvoice_root':''});self.assertEqual(config(root),{})

 def test_python_symlink_preserves_virtual_environment(self):
  import sys
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);binary=root/'env/bin/python';binary.parent.mkdir(parents=True);binary.symlink_to(sys.executable)
   save(root,{'whisper_python':str(binary)})
   self.assertEqual(config(root)['whisper_python'],str(binary.absolute()))
