"""Portable workspace snapshot; restore never overwrites an existing workspace."""
import json
import os
import re
import shutil
import sqlite3
import uuid
from pathlib import Path
from .db import file_hash, payload_hash
from content_workbench.domain.errors import DomainError
from content_workbench.domain.services import Workbench

DIRS=('config','skills','assets','renders','voice','subtitles','covers','narration','previews','analytics','review-work','data/review-uploads')
MEDIA={'.mp4','.mov','.mkv','.webm','.wav','.mp3','.m4a','.aac','.flac','.png','.jpg','.jpeg','.webp','.srt','.html','.md','.txt','.json'}

def fail(message):raise DomainError('PROJECT_MIGRATION',message,409)
def safe(root,relative):
    path=(root/relative).resolve()
    if root.resolve() not in path.parents:fail('迁移清单包含越界路径')
    return path

def export_workspace(db_path,root,destination):
    root=Path(root).resolve(); destination=Path(destination).expanduser().resolve()
    if destination.exists():fail('导出目录已存在，请选择新的目录')
    if root==destination or root in destination.parents:fail('请将迁移包保存在工作区之外')
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_name('.'+destination.name+'.'+uuid.uuid4().hex+'.partial');temporary.mkdir()
    try:
        database=temporary/'data/content-agent.db';database.parent.mkdir()
        with sqlite3.connect(str(db_path)) as source,sqlite3.connect(str(database)) as snapshot:source.backup(snapshot)
        entries={};mapping={}
        for directory in DIRS:
            folder=root/directory
            if folder.is_dir():
                for path in folder.rglob('*'):
                    if path.is_file() and not path.is_symlink():entries[path.relative_to(root).as_posix()]=path
        with sqlite3.connect(str(database)) as conn:
            conn.row_factory=sqlite3.Row
            tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'files' in tables:
                for row in conn.execute('SELECT relative_path,media_info_json FROM files'):
                    if json.loads(row['media_info_json'] or '{}').get('wb_asset_id'):continue
                    path=safe(root,row['relative_path'])
                    if not path.is_file():fail('任务素材缺失：'+row['relative_path'])
                    entries[row['relative_path']]=path
            if 'wb_assets' in tables:
                wb=Workbench(database,root)
                for row in conn.execute('SELECT * FROM wb_assets').fetchall():
                    path=wb.resolve_asset_path(row,verify=True)
                    relative=path.relative_to(root).as_posix() if root in path.parents else 'assets/migrated/'+row['sha256']+path.suffix.lower()
                    entries[relative]=path;mapping[str(path)]=relative
                    conn.execute('UPDATE wb_assets SET storage_key=?,source_json=? WHERE id=?',(relative,json.dumps({'kind':'local_copy','original_name':path.name}),row['id']))
            # Retain external review candidates and approved outputs as portable media.
            if 'review_items' in tables:
                for row in conn.execute('SELECT source_path,candidate_path,output_path FROM review_items'):
                    for value in row:
                        if not value:continue
                        path=Path(value).resolve()
                        if not path.is_file():fail('审核素材缺失：'+str(path))
                        if root not in path.parents:
                            relative='assets/migrated/'+file_hash(path)+path.suffix.lower();entries[relative]=path;mapping[str(path)]=relative
            # Connection secrets and per-machine readiness must be configured on the new Mac.
            if 'settings' in tables:
                for row in conn.execute('SELECT key,value FROM settings').fetchall():
                    if re.search(r'key|secret|token|password|cookie|ready|binary',row['key'],re.I):conn.execute('DELETE FROM settings WHERE key=?',(row['key'],))
        required=sum(p.stat().st_size for p in entries.values())+database.stat().st_size+64*1024**2
        if shutil.disk_usage(temporary).free<required:fail('迁移目标磁盘空间不足')
        records=[]
        for relative,path in entries.items():
            target=safe(temporary,relative);target.parent.mkdir(parents=True,exist_ok=True)
            digest=file_hash(path);shutil.copyfile(path,target)
            if file_hash(target)!=digest or file_hash(path)!=digest:fail('导出期间素材变化，请重试')
            records.append({'path':relative,'size':target.stat().st_size,'sha256':digest})
        records.append({'path':'data/content-agent.db','size':database.stat().st_size,'sha256':file_hash(database)})
        (temporary/'manifest.json').write_text(json.dumps({'format':'yingxu-workspace','version':1,'source_root':str(root),'path_map':mapping,'files':records},ensure_ascii=False,indent=2))
        if destination.exists():fail("目标目录已存在，未覆盖")
        os.rename(temporary,destination)
        return {'path':str(destination),'files':len(records),'bytes':sum(x['size'] for x in records),'note':'新电脑需要重新激活、登录平台及配置模型连接；原工作区未改变'}
    finally:
        if temporary.exists():shutil.rmtree(temporary)

def restore_workspace(package,destination):
    package=Path(package).expanduser().resolve();destination=Path(destination).expanduser().resolve()
    if destination.exists():fail('恢复目标必须是尚不存在的新目录，不能覆盖现有系统')
    manifest=json.loads((package/'manifest.json').read_text())
    if manifest.get('format')!='yingxu-workspace' or manifest.get('version')!=1:fail('不支持的迁移包')
    records=manifest['files'];seen=set()
    for entry in records:
        relative=entry['path'];path=safe(package,relative)
        if relative in seen or path.is_symlink() or not path.is_file() or path.stat().st_size!=entry['size'] or file_hash(path)!=entry['sha256']:fail('迁移包缺失、重复或内容损坏：'+relative)
        seen.add(relative)
    if 'data/content-agent.db' not in seen:fail('迁移包缺少数据库')
    destination.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(destination.parent).free<sum(e['size'] for e in records)+64*1024**2:fail('恢复磁盘空间不足')
    temporary=destination.with_name('.'+destination.name+'.'+uuid.uuid4().hex+'.partial');temporary.mkdir()
    try:
        for entry in records:
            target=safe(temporary,entry['path']);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(safe(package,entry['path']),target)
            if file_hash(target)!=entry['sha256']:fail('复制迁移包时内容变化')
        mapping={}
        for key,value in manifest.get('path_map',{}).items():
            if value not in seen:fail('迁移路径未包含在校验清单中')
            mapping[key]=str(safe(destination,value))
        old=manifest['source_root']
        def rewrite(value):
            if isinstance(value,str):
                if value in mapping:return mapping[value]
                if value.startswith(old+'/'):return str(destination)+value[len(old):]
                try:
                    decoded=json.loads(value)
                    if isinstance(decoded,(dict,list)):return json.dumps(rewrite(decoded),ensure_ascii=False)
                except ValueError:pass
                return value
            if isinstance(value,list):return [rewrite(v) for v in value]
            if isinstance(value,dict):return {k:rewrite(v) for k,v in value.items()}
            return value
        with sqlite3.connect(str(temporary/'data/content-agent.db')) as conn:
            tables=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            for table in tables:
                if not re.fullmatch(r'[A-Za-z0-9_]+',table):fail('数据库表名异常')
                columns=[r[1] for r in conn.execute('PRAGMA table_info("'+table+'")')]
                for row in conn.execute('SELECT rowid,* FROM "'+table+'"').fetchall():
                    values=[rewrite(v) for v in row[1:]]
                    for payload_column,hash_column in (("payload_json","payload_hash"),("input_json","input_hash")):
                        if payload_column in columns and hash_column in columns:
                            position=columns.index(payload_column)
                            if values[position]!=row[position+1]:
                                values[columns.index(hash_column)]=payload_hash(json.loads(values[position]))
                    if values!=list(row[1:]):conn.execute('UPDATE "'+table+'" SET '+','.join('"'+c+'"=?' for c in columns)+' WHERE rowid=?',values+[row[0]])
            if 'wb_jobs' in tables:
                conn.execute("UPDATE wb_jobs SET status='cancelled',stage='restored_requires_retry',lease_owner=NULL,lease_expires_at=NULL,fencing_token=fencing_token+1,error_json=? WHERE status IN ('queued','leased','running','retry_wait','cancel_requested','blocked')",(json.dumps({'code':'WORKSPACE_RESTORED','message':'工作区已迁移，请检查连接后手动重试任务'}),))
            if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or conn.execute('PRAGMA foreign_key_check').fetchall():fail('恢复数据库校验失败')
        if destination.exists():fail("目标目录已存在，未覆盖")
        os.rename(temporary,destination)
        return {'path':str(destination),'database':str(destination/'data/content-agent.db'),'note':'已恢复到新目录；现有工作区未覆盖。请在客户端选择此目录，重新激活和登录。'}
    finally:
        if temporary.exists():shutil.rmtree(temporary)
