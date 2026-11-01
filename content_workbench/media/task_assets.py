"""Existing task files may refer to existing wb_assets; no second asset store."""
import json
from pathlib import Path
from content_workbench.domain.services import Workbench
from content_workbench.domain.errors import DomainError


def metadata(file):
    file=dict(file)
    return file.get('media_info') or json.loads(file.get('media_info_json') or '{}')


def resolve_task_asset(db_path, root, file, verify=True):
    info=metadata(file)
    asset_id=info.get('wb_asset_id')
    if not asset_id:
        path=(Path(root)/file['relative_path']).resolve()
        if Path(root).resolve() not in path.parents or not path.is_file():
            raise DomainError('ASSET_FILE_MISSING','任务文件不存在或路径无效',404)
        return path
    workbench=Workbench(db_path,root)
    with workbench.conn(readonly=True) as conn:
        asset=conn.execute('SELECT * FROM wb_assets WHERE id=?',(asset_id,)).fetchone()
    return workbench.resolve_asset_path(asset,verify=verify)
