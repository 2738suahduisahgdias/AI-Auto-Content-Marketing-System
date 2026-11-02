import json,sqlite3,tempfile,unittest
from pathlib import Path
from content_workbench.storage.workspace_selection import select_workspace
from content_workbench.domain.errors import DomainError
class SelectionTest(unittest.TestCase):
 def test_valid_and_invalid_preserve_pointer(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);old=root/'old';old.mkdir();target=root/'new';(target/'data').mkdir(parents=True)
   with sqlite3.connect(str(target/'data/content-agent.db')) as c:c.execute('create table tasks(id text)')
   pointer=root/'pointer.json';pointer.write_text(json.dumps({'root':str(old)}))
   with self.assertRaises(DomainError):select_workspace(old,root/'missing',pointer)
   self.assertEqual(json.loads(pointer.read_text())['root'],str(old))
   select_workspace(old,target,pointer);self.assertEqual(json.loads(pointer.read_text())['root'],str(target.resolve()))
