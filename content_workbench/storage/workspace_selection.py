"""Validate an existing workspace before changing the desktop launch pointer."""
import json,os,sqlite3,uuid
from pathlib import Path
from content_workbench.domain.errors import DomainError

def select_workspace(current, destination, pointer):
 current=Path(current).resolve();target=Path(destination).expanduser().resolve();pointer=Path(pointer)
 if target==current:raise DomainError('SAME_WORKSPACE','当前已在使用此工作区',409)
 db=target/'data/content-agent.db'
 if not db.is_file():raise DomainError('INVALID_WORKSPACE','请选择已经恢复或已有的完整工作区，不能只选择空文件夹',422)
 with sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True) as conn:
  if conn.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise DomainError('INVALID_WORKSPACE','目标数据库校验失败',422)
  if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tasks'").fetchone():raise DomainError('INVALID_WORKSPACE','目标不是有效的内容工作区',422)
 probe=target/('.write-test-'+uuid.uuid4().hex)
 try:probe.write_text('');probe.unlink()
 except OSError:raise DomainError('WORKSPACE_READONLY','目标工作区不可写，请检查磁盘权限',422)
 pointer.parent.mkdir(parents=True,exist_ok=True);temporary=pointer.with_suffix('.pending')
 temporary.write_text(json.dumps({'root':str(target)},ensure_ascii=False));os.replace(temporary,pointer)
 return {'path':str(target),'note':'工作区已校验，正在重新启动本地服务。原工作区完整保留。'}
