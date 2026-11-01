"""Portable local article delivery; images remain tied to the reviewed revision."""
import base64
import html
import hashlib
import json
import re
import zipfile
from content_workbench.domain.errors import DomainError


def picture_rows(payload):
    plan = payload.get('creative_plan') or {}
    if not isinstance(plan, dict) or not isinstance(plan.get('pictures', []), list):
        raise DomainError('INVALID_PICTURE_PLAN', '配图计划格式无效', 422)
    rows = plan.get('pictures', [])
    if len(rows) > 40 or any(not isinstance(row, dict) for row in rows):
        raise DomainError('INVALID_PICTURE_PLAN', '每篇最多支持 40 个配图位置', 422)
    paragraphs = re.split(r'\n\s*\n', str(payload.get('text', '')).strip())
    for row in rows:
        if not row.get('asset_id'):
            continue
        position = row.get('after_paragraph', 0)
        if type(position) is not int or not 0 <= position <= len(paragraphs):
            raise DomainError('INVALID_PICTURE_POSITION', '配图段落位置超出正文范围，0 表示正文之前', 422)
    return rows


def image_file(workbench, asset):
    if not asset or asset['mime_type'] not in ('image/png', 'image/jpeg', 'image/webp'):
        raise DomainError('INVALID_ARTICLE_IMAGE', '文章配图仅支持 PNG、JPEG 或 WebP', 422)
    if asset['byte_size'] > 20 * 1024 * 1024:
        raise DomainError('ARTICLE_IMAGE_TOO_LARGE', '单张配图不能超过 20 MB，请先压缩', 422)
    path = workbench.resolve_asset_path(asset, verify=True)
    with path.open('rb') as stream:
        magic = stream.read(12)
    valid = ((asset['mime_type'] == 'image/png' and magic.startswith(b'\x89PNG\r\n\x1a\n')) or
             (asset['mime_type'] == 'image/jpeg' and magic.startswith(b'\xff\xd8\xff')) or
             (asset['mime_type'] == 'image/webp' and magic[:4] == b'RIFF' and magic[8:12] == b'WEBP'))
    if not valid:
        raise DomainError('INVALID_ARTICLE_IMAGE', '文件内容与图片格式不符', 422)
    return path


def build_delivery(workbench, payload, title, directory):
    rows = picture_rows(payload)
    paragraphs = re.split(r'\n\s*\n', str(payload.get('text', '')).strip())
    images = {}
    credits = {}
    total = 0
    for row in rows:
        asset_id = row.get('asset_id')
        if not asset_id or asset_id in images:
            continue
        with workbench.conn(readonly=True) as conn:
            asset = conn.execute('SELECT * FROM wb_assets WHERE id=?', (asset_id,)).fetchone()
        path = image_file(workbench, asset)
        total += asset['byte_size']
        if total > 50 * 1024 * 1024:
            raise DomainError('ARTICLE_IMAGES_TOO_LARGE', '本篇配图总大小超过 50 MB，请先压缩', 422)
        with path.open('rb') as stream:
            data = stream.read(20 * 1024 * 1024 + 1)
        if len(data) != asset['byte_size'] or hashlib.sha256(data).hexdigest() != asset['sha256']:
            raise DomainError('ASSET_CHANGED', '导出期间图片内容发生变化，请重新导入并审核', 409)
        suffix = {'image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp'}[asset['mime_type']]
        images[asset_id] = (f'images/{asset_id}{suffix}', data, asset['mime_type'])
        source = json.loads(asset['source_json'] or '{}')
        if source.get('kind') == 'image_search':
            credits[asset_id] = {key: source.get(key, '') for key in ('author', 'license', 'license_url', 'source_url', 'attribution')}
    html_parts, markdown_parts = [], [f'# {title}\n']
    def insert(position):
        for row in rows:
            if row.get('asset_id') not in images or row.get('after_paragraph', 0) != position:
                continue
            name, data, mime = images[row['asset_id']]
            caption = str(row.get('description') or '')
            credit = credits.get(row['asset_id'])
            if credit:
                caption += ' ｜ 图片来源：' + ' · '.join(str(credit[key]) for key in ('author', 'license', 'source_url') if credit.get(key))
            uri = 'data:' + mime + ';base64,' + base64.b64encode(data).decode('ascii')
            html_parts.append('<figure><img src="{}" alt="{}"><figcaption>{}</figcaption></figure>'.format(uri, html.escape(caption, quote=True), html.escape(caption)))
            markdown_parts.append('![{}]({})\n'.format(html.escape(re.sub(r'[\[\]\\\r\n]', ' ', caption)), name))
    insert(0)
    for index, paragraph in enumerate(paragraphs, 1):
        html_parts.append('<p>' + html.escape(paragraph).replace('\n', '<br>') + '</p>')
        markdown_parts.append(paragraph + '\n')
        insert(index)
    document = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{}</title><style>body{{margin:0;background:#faf8f4;color:#292621;font:18px/1.85 sans-serif}}article{{max-width:720px;margin:auto;padding:32px 24px;background:white}}img{{max-width:100%;height:auto}}figure{{margin:24px 0}}figcaption{{font-size:14px;color:#766b5b}}p{{overflow-wrap:anywhere}}</style><article><h1>{}</h1>{}</article></html>'.format(html.escape(title),html.escape(title),''.join(html_parts))
    markdown = '\n'.join(markdown_parts)
    package = directory / 'article-package.zip'
    with zipfile.ZipFile(package, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('image-credits.json', json.dumps(credits, ensure_ascii=False, indent=2))
        archive.writestr('article.md', markdown)
        archive.writestr('article.html', document)
        for name, data, _ in images.values():
            archive.writestr(name, data)
    return markdown, document, package, list(images)
