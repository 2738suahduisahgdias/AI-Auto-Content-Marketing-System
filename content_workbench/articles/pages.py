import json
import os
import subprocess
import sys
from pathlib import Path
from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import PROJECT_ROOT
from .layout import picture_rows, image_file


def generate_pages(workbench, payload, title, directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    # Resolve registered originals, then snapshot bytes for a deterministic render.
    images=[]
    for index,row in enumerate(picture_rows(payload)):
        if not row.get('asset_id'):continue
        with workbench.conn(readonly=True) as conn:
            asset=conn.execute('SELECT * FROM wb_assets WHERE id=?',(row['asset_id'],)).fetchone()
        path=image_file(workbench,asset)
        import hashlib
        with path.open('rb') as source: data=source.read(20*1024*1024+1)
        if hashlib.sha256(data).hexdigest()!=asset['sha256']:
            raise DomainError('ASSET_CHANGED','分页期间图片发生变化',409)
        target=directory/('input-%03d'%index+path.suffix);target.write_bytes(data)
        provenance=json.loads(asset['source_json'] or '{}')
        description=str(row.get('description') or '')
        if provenance.get('kind')=='image_search':
            description += ' ｜ 图片来源：' + ' · '.join(str(provenance[k]) for k in ('author','license','source_url') if provenance.get(k))
        images.append({**row,'description':description,'path':str(target),'after_paragraph':row.get('after_paragraph',0)})
    input_path=directory/'input.json'
    input_path.write_text(json.dumps({'title':title,'text':str(payload.get('text') or ''),'images':images},ensure_ascii=False))
    fonts=[os.environ.get('CONTENT_AGENT_CJK_FONT',''),'/System/Library/Fonts/STHeiti Light.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
    font=next((p for p in fonts if p and Path(p).is_file()),None)
    if not font:raise DomainError('PAGE_FONT_MISSING','缺少本地中文字体',503,action='安装中文字体或配置 CONTENT_AGENT_CJK_FONT 路径')
    candidates=[workbench.root/'.venv-topics/bin/python',PROJECT_ROOT/'.venv-topics/bin/python',Path(sys.executable),Path('/usr/bin/python3')]
    python=None
    for candidate in candidates:
        if candidate.is_file():
            check=subprocess.run([str(candidate),'-c','from PIL import Image, ImageFont'],capture_output=True,timeout=15)
            if check.returncode==0:python=candidate;break
    if not python:raise DomainError('PAGE_PILLOW_MISSING','缺少本地 Pillow 图片渲染依赖',503)
    result=subprocess.run([str(python),str(PROJECT_ROOT/'content_workbench/articles/page_worker.py'),'--input',str(input_path),'--output',str(directory),'--font',font],capture_output=True,text=True,timeout=180)
    if result.returncode:raise DomainError('PAGE_RENDER_FAILED','长图分页渲染失败，请检查图片格式、内容长度和字体',502)
    result=json.loads((directory/'pages.json').read_text())
    return [directory/page['file'] for page in result['pages']]
