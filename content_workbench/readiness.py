"""Read-only runtime evidence, never treats historical login as a live session."""
import os
import shutil
from pathlib import Path
from content_workbench.storage.db import PROJECT_ROOT, utcnow


def runtime_readiness(app):
    root = app.root
    worker = getattr(app, 'overview_worker', app.worker)
    running = bool(worker.thread and worker.thread.is_alive())
    allowed = getattr(worker, 'allowed_kinds', None)
    enabled = sorted(k for k in worker.executors if running and (allowed is None or k in allowed))
    kimi = Path(shutil.which('kimi') or Path.home()/'.kimi-code/bin/kimi')
    from content_workbench.agents.registry import agent_config
    article_engine = agent_config(app.workbench.db_path, 'article_agent')['engine'] if hasattr(app, 'workbench') else 'kimi_cli'
    checks = {
        'text_cli': kimi.is_file() and os.access(kimi, os.X_OK),
        'codex_cli': bool(shutil.which('codex')),
        'ffmpeg': bool(shutil.which('ffmpeg') and shutil.which('ffprobe')),
        'node': bool(shutil.which('node')),
        'remotion': (PROJECT_ROOT/'remotion-app/node_modules').is_dir(),
        'browser_python': any((root/p).is_file() for p in ('.venv-topics/bin/python','.venv-topics/Scripts/python.exe')),
    }
    definitions = [
        ('文案生成', ['article.outline','article.draft'], ['codex_cli' if article_engine == 'codex_cli' else 'text_cli'], 'CLI 存在不等于模型登录有效，需真实生成验证'),
        ('文章文档导出', ['article.export'], [], '沿用已审批正文版本，导出 Markdown 与 HTML'),
        ('映序视频制作', ['video.produce','video.preview'], ['node','ffmpeg','remotion'], '需以真实项目渲染验证模板和输入素材'),
        ('本地技术质检', ['review.scan','review.repair'], ['ffmpeg'], 'OCR 与 AI 审核另有依赖，不代表品牌质检全部完成'),
        ('发布字段生成', ['publish.fields'], ['text_cli'], '只生成字段，不代表平台已登录'),
        ('平台登录与预填', ['publish.login','publish.prepare'], ['browser_python'], '公众号/视频号另依赖浏览器桥接，四个平台均需逐一核验当前登录'),
        ('公开发布', ['publish.execute'], [], '必须先预填验证，再由用户在发布页明确确认'),
    ]
    capabilities=[]
    for name,kinds,deps,note in definitions:
        missing=[d for d in deps if not checks[d]]
        offline=[k for k in kinds if k not in enabled]
        capabilities.append({'name':name,'status':'blocked' if missing or offline else 'requires_validation',
                             'missing_dependencies':missing,'inactive_executors':offline,'note':note})
    for name in ['图文图片搜索与生成','平台专用排版与长图','Mac 安装包']:
        capabilities.append({'name':name,'status':'not_implemented','missing_dependencies':[],
                             'inactive_executors':[],'note':'尚未完成真实接入与交付验收，不能通过登录解决'})
    capabilities.append({'name':'本地素材引用与重新定位','status':'requires_validation','missing_dependencies':[],
                         'inactive_executors':[],'note':'后端引用、复制、指纹重定位及消费者回归测试已通过；设置页待实机验证，代理缓存与项目迁移仍待开发'})
    return {'checked_at':utcnow(),'worker_running':running,'enabled_executors':enabled,'dependencies':checks,
            'capabilities':capabilities,'platforms':[{'platform':p,'status':'requires_login_verification'} for p in
              ['douyin','xiaohongshu','wechat_channels','wechat_official_account']],
            'boundary':'只读本机探测；不读取密钥、不登录平台、不调用模型、不提交发布。历史快照不能证明当前登录有效。'}
