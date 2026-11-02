"""Workspace-owned editor drafts, included in the existing database backup."""
import json
import uuid
import shutil
from content_workbench.storage.db import connect, immediate, utcnow
from content_workbench.domain.errors import DomainError

class DraftStore:
    def __init__(self, db_path):
        from pathlib import Path
        self.db_path = Path(db_path)
        with connect(db_path) as conn, immediate(conn):
            conn.execute("CREATE TABLE IF NOT EXISTS wb_workspace_identity (id INTEGER PRIMARY KEY CHECK(id=1), uuid TEXT NOT NULL)")
            conn.execute("INSERT OR IGNORE INTO wb_workspace_identity VALUES(1,?)", (uuid.uuid4().hex,))
            conn.execute("CREATE TABLE IF NOT EXISTS wb_content_drafts (key TEXT PRIMARY KEY, data_json TEXT NOT NULL, revision INTEGER NOT NULL, updated_at TEXT NOT NULL)")

    def bootstrap(self):
        with connect(self.db_path, readonly=True) as conn:
            workspace = conn.execute('SELECT uuid FROM wb_workspace_identity WHERE id=1').fetchone()[0]
            rows = conn.execute('SELECT * FROM wb_content_drafts').fetchall()
            prefixes=[]
            tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'wb_content_items' in tables:
                for row in conn.execute('SELECT id FROM wb_content_items'):
                    prefixes.extend(['article:'+row[0]+':','publishing:article:'+row[0]+':'])
            if 'tasks' in tables:
                for row in conn.execute('SELECT content_id,created_at FROM tasks'):
                    prefixes.extend(['video:'+row[0]+':'+row[1]+':','publishing:video:'+row[0]+':'])
            return {'workspace_id':workspace, 'legacy_prefixes':prefixes, 'drafts':
                [{k:row[k] for k in ('key','revision','updated_at')} | {'data':json.loads(row['data_json'])} for row in rows]}

    def save(self, payload):
        key = payload.get('key')
        expected = payload.get('expected_revision')
        if not isinstance(key,str) or not key or len(key)>512 or not isinstance(expected,int) or isinstance(expected,bool) or expected<0 or 'data' not in payload:
            raise DomainError('DRAFT_INPUT_INVALID','草稿格式无效',422)
        data = json.dumps(payload['data'],ensure_ascii=False,allow_nan=False)
        if len(data.encode())>2*1024**2:
            raise DomainError('DRAFT_TOO_LARGE','草稿超过 2MB，请将图片作为素材导入，正文中保留素材引用',413)
        with connect(self.db_path) as conn, immediate(conn):
            current = conn.execute('SELECT revision FROM wb_content_drafts WHERE key=?',(key,)).fetchone()
            revision = current[0] if current else 0
            if revision != expected:
                raise DomainError('DRAFT_CONFLICT','另一窗口已更新此草稿；当前输入已保留，请先导出当前内容，再刷新核对，未覆盖其他窗口',409)
            if shutil.disk_usage(self.db_path.parent).free < len(data.encode())+64*1024**2:
                raise DomainError('DRAFT_STORAGE_FULL','工作区磁盘空间不足，请清理缓存后重试；当前编辑内容未丢弃',413)
            timestamp=utcnow()
            conn.execute('INSERT OR REPLACE INTO wb_content_drafts VALUES(?,?,?,?)',(key,data,revision+1,timestamp))
            return {'key':key,'revision':revision+1,'updated_at':timestamp}
