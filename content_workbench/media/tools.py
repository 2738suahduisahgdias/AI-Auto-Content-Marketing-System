"""Customer-owned local dependency paths; never assume a developer checkout."""
import json,os
from pathlib import Path
from content_workbench.domain.errors import DomainError
KEYS={'whisper_python','openvoice_python','openvoice_root'}
def config(root):
 p=Path(root)/'config/media-tools.json'
 return json.loads(p.read_text()) if p.is_file() else {}
def save(root,values):
 updated=config(root)
 for key,value in values.items():
  if key not in KEYS:continue
  if not isinstance(value,str):raise DomainError('MEDIA_TOOLS_INVALID','路径格式无效',422)
  if not value.strip():updated.pop(key,None);continue
  p=Path(value).expanduser().absolute()
  if not key.endswith('python'):p=p.resolve()
  if key.endswith('python') and (not p.is_file() or not os.access(p,os.X_OK)):raise DomainError('MEDIA_TOOLS_INVALID','请选择可执行的 Python 文件',422)
  if key.endswith('root') and not p.is_dir():raise DomainError('MEDIA_TOOLS_INVALID','请选择 OpenVoice 模型目录',422)
  updated[key]=str(p)
 p=Path(root)/'config/media-tools.json';p.parent.mkdir(parents=True,exist_ok=True)
 temp=p.with_suffix('.tmp');temp.write_text(json.dumps(updated,ensure_ascii=False));os.replace(temp,p)
 return updated
