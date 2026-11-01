"""Read-only projection of existing work. No parallel task store or mutations."""
from contextlib import closing
from pathlib import Path
from urllib.parse import quote
from content_workbench.storage.db import connect, loads, utcnow

def overview(db_path, worker):
    alive = bool(worker and worker.thread and worker.thread.is_alive())
    allowed = getattr(worker, 'allowed_kinds', None)
    def available(kind):
        return alive and kind in worker.executors and (allowed is None or kind in allowed)
    groups = []
    def group(key, label, rows):
        groups.append({'key': key, 'label': label, 'total': len(rows), 'items': rows[:100]})
    with closing(connect(db_path, readonly=True)) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        def read(table, sql):
            return [dict(row) for row in conn.execute(sql)] if table in tables else []
        articles = read('wb_content_items', "SELECT i.id,i.state,i.updated_at,c.title FROM wb_content_items i LEFT JOIN wb_campaigns c ON c.id=i.campaign_id WHERE i.content_type='article' AND i.state NOT IN ('published','archived','reviewed') ORDER BY i.updated_at DESC")
        for row in articles:
            row.update(href='/articles/'+quote(row['id'], safe=''), next='继续编辑或审核正文', attention=row['state'] in ('review_required','in_review','needs_review'))
            if row['state'] in ('approved','exported'):
                row.update(next='交给发布 Agent', href='/publish?kind=article&id='+quote(row['id'], safe=''))
        group('article', '文章 Agent', articles)
        videos = read('tasks', "SELECT content_id AS id,title,state,source_json,updated_at FROM tasks WHERE state NOT IN ('published','analyzed') ORDER BY updated_at DESC")
        for row in videos:
            handoff = loads(row.pop('source_json'), {}).get('yingxu_handoff') or {}
            row.update(href='/tasks/'+quote(row['id'], safe=''), next='继续映序制作', attention=False)
            if handoff.get('stale'):
                row.update(next='内容已修改，请重新交付成片', attention=True)
            elif handoff.get('review_batch_id'):
                row.update(next='查看关联审核进度', href='/review?batch_id='+quote(handoff['review_batch_id'], safe=''))
        group('video', '视频 Agent', videos)
        reviews = read('review_items', "SELECT id,batch_id,source_path,status AS state,decision,updated_at FROM review_items WHERE decision != 'approved' ORDER BY updated_at DESC")
        for row in reviews:
            row.update(title=Path(row.pop('source_path')).name, href='/review?batch_id='+quote(row.pop('batch_id'), safe=''), attention=row['state'] in ('failed','needs_review') or row['decision']=='rejected', next='查看预审结果与人工审核')
        group('review', '质检 Agent', reviews)
        publications = read('publish_targets', "SELECT t.id,t.platform,t.status AS state,t.updated_at,b.content_kind,b.source_id,b.source_file_id FROM publish_targets t JOIN publish_batches b ON b.id=t.batch_id WHERE t.status NOT IN ('published','succeeded','cancelled') ORDER BY t.updated_at DESC")
        for row in publications:
            row.update(title=row['platform']+' · '+row['source_id'], href='/publish?kind='+row['content_kind']+'&id='+quote(row['source_id'] + (':'+str(row['source_file_id']) if row['source_file_id'] else ''), safe=''), next='打开发布工作区，检查字段与人工确认', attention=row['state'] in ('failed','unknown_remote','awaiting_confirmation','prepared'))
        group('publish', '发布 Agent', publications)
        jobs = read('wb_jobs', "SELECT id,kind,aggregate_id,status AS state,stage,progress,blocked_reason,error_json,created_at,updated_at FROM wb_jobs WHERE status IN ('queued','leased','running','retry_wait','cancel_requested','failed','blocked','unknown_remote') ORDER BY updated_at DESC")
        jobs = [row for row in jobs if not row['kind'].startswith(('social.', 'retro.', 'competitor.'))]
        for row in jobs:
            kind = row['kind']; aggregate = quote(row['aggregate_id'] or '', safe='')
            href = '/settings/agents'
            if kind.startswith('article.'): href='/articles/'+aggregate
            elif kind.startswith('video.'): href='/tasks/'+aggregate
            elif kind.startswith('review.'): href='/review'
            elif kind.startswith('publish.'): href='/publish'
            elif kind.startswith(('topic.','topics.','research.','collection.')):
                href='/topics/'+('xiaohongshu' if 'xhs' in kind or row['aggregate_id']=='xiaohongshu' else 'industry' if 'industry' in kind or row['aggregate_id']=='industry' else 'douyin')
            elif kind.startswith('accounts.'): href='/accounts'
            row.pop('error_json', None)
            queued = row['state'] in ('queued','retry_wait')
            reason = '任务执行异常，请到原工作区查看详情' if row['state'] in ('failed','unknown_remote','retry_wait') else ''
            if row['state']=='blocked': reason=row.get('blocked_reason') or '任务被阻塞，请检查原任务'
            if queued and not available(kind): reason = '当前进程未启动此执行器；排队不代表正在运行'
            row.update(title=kind, href=href, next=reason or row['stage'] or '查看任务进度', attention=bool(reason), executor_available=available(kind))
        topic_jobs=[row for row in jobs if row['kind'].startswith(('topic.','topics.','research.','collection.'))]
        group('topics', '选题 Agent', topic_jobs)
        group('jobs', '其他 Agent 执行任务', [row for row in jobs if row not in topic_jobs])
    return {'generated_at': utcnow(), 'groups': groups, 'worker': {'running': alive, 'allowed_kinds': allowed},
            'boundary': '按原记录只读汇总。内容、审核项、平台发布项和执行任务分别计数，不相加为项目总数；每组最多显示最近 100 条。未自动调用模型或执行发布。'}
