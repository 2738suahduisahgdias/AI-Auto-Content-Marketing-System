"""Read-only runtime evidence, never treats historical login as a live session."""
import os
import sys
import json
import urllib.request
import importlib.util
import shutil
from pathlib import Path
from content_workbench.storage.db import PROJECT_ROOT, utcnow


def runtime_readiness(app):
    root = app.root
    resources = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
    worker = getattr(app, 'overview_worker', app.worker)
    running = bool(worker.thread and worker.thread.is_alive())
    allowed = getattr(worker, 'allowed_kinds', None)
    enabled = sorted(k for k in worker.executors if running and (allowed is None or k in allowed))
    kimi = Path(shutil.which('kimi') or Path.home()/'.kimi-code/bin/kimi')
    from content_workbench.agents.registry import agent_config
    article_engine = agent_config(app.workbench.db_path, 'article_agent')['engine'] if hasattr(app, 'workbench') else 'kimi_cli'
    publish_engine = agent_config(app.workbench.db_path, 'publish_agent')['engine'] if hasattr(app, 'workbench') else 'codex_cli'
    checks = {
        'text_cli': kimi.is_file() and os.access(kimi, os.X_OK),
        'codex_cli': bool(shutil.which('codex')),
        'ffmpeg': bool(shutil.which('ffmpeg') and shutil.which('ffprobe')),
        'node': bool(shutil.which('node')),
        'remotion': (resources/'remotion-app/node_modules').is_dir(),
        'browser_python': importlib.util.find_spec('playwright') is not None or any((root/p).is_file() for p in ('.venv-topics/bin/python','.venv-topics/Scripts/python.exe')),
    }
    try:
        with urllib.request.urlopen('http://127.0.0.1:10086/status', timeout=1) as response:
            bridge = json.load(response)
        checks['chrome_bridge'] = bridge.get('extension_connected') is True
    except Exception:
        checks['chrome_bridge'] = False
    definitions = [
        ('文案生成', ['article.outline','article.draft'], ['codex_cli' if article_engine == 'codex_cli' else 'text_cli'], 'CLI 存在不等于模型登录有效，需真实生成验证'),
        ('文章文档导出', ['article.export'], [], '沿用已审批正文版本，导出 Markdown 与 HTML'),
        ('映序视频制作', [], ['node','ffmpeg','remotion'], '映序使用直接渲染接口；包含全片和单镜预览，需以实际项目确认画面和声音'),
        ('本地技术质检', ['review.scan','review.repair'], ['ffmpeg'], 'OCR 与 AI 审核另有依赖，不代表品牌质检全部完成'),
        ('发布字段生成', ['publish.fields'], ['codex_cli' if publish_engine == 'codex_cli' else 'text_cli'], '只生成字段，不代表平台已登录'),
        ('平台登录与预填', ['publish.login','publish.prepare'], ['browser_python','chrome_bridge'], '需要本机浏览器连接服务及扩展；扫码仅确认身份，需分别验证字段和素材上传。公众号、视频号自动上传尚未通过交付验收'),
        ('公开发布', [], [], '客户端只准备草稿；最终由用户在平台后台检查并点击发布'),
    ]
    capabilities=[]
    for name,kinds,deps,note in definitions:
        missing=[d for d in deps if not checks[d]]
        offline=[k for k in kinds if k not in enabled]
        capabilities.append({'name':name,'status':'blocked' if missing or offline else 'requires_validation',
                             'missing_dependencies':missing,'inactive_executors':offline,'note':note})
    capabilities.extend([{'name':'图文图片搜索与生成','status':'requires_validation' if checks['codex_cli'] and 'article.image' in enabled else 'blocked','missing_dependencies':[] if checks['codex_cli'] else ['codex_cli'],'inactive_executors':[] if 'article.image' in enabled else ['article.image'],'note':'Commons 搜图与 Codex 生图已接通；仍需当前网络、账户额度和工具可用'}, {'name':'平台专用排版与长图','status':'requires_validation' if 'article.export' in enabled else 'blocked','missing_dependencies':[],'inactive_executors':[] if 'article.export' in enabled else ['article.export'],'note':'本地 PNG 分页、HTML、ZIP 已接通；渲染时检查 Pillow 与中文字体'}])
    for name in ['Mac 安装包']:
        capabilities.append({'name':name,'status':'requires_validation','missing_dependencies':[],
                             'inactive_executors':[],'note':'已有本机测试安装包；当前代码尚需重新完整打包，Developer ID 签名公证和客户干净机器验收未完成'})
    capabilities.append({'name':'本地素材引用与重新定位','status':'requires_validation','missing_dependencies':[],
                         'inactive_executors':[],'note':'已实现原文件引用、重新定位、代理预览与工作区迁移；需在客户目标磁盘验证，拔盘后应重新定位素材'})
    capabilities.append({'name':'AI 视频大模型','status':'not_implemented','missing_dependencies':[],
                         'inactive_executors':[],'note':'场景与参考素材可规划；自动生成视频尚未接入。可上传已有视频或使用 Remotion，扫码不能解锁此能力'})
    return {'checked_at' :utcnow(),'worker_running':running,'enabled_executors':enabled,'dependencies':checks,
            'capabilities':capabilities,'platforms':[{'platform':p,'status':'requires_login_verification'} for p in
              ['douyin','xiaohongshu','wechat_channels','wechat_official_account']],
            'delivery_ready':False, 'delivery_blockers':['当前变更未重新生成正式签名公证安装包','浏览器服务与扩展需按接入向导手动安装；已提供检测和重启，仍需在干净客户 Mac 验证','公众号与视频号自动上传未完成真实验收','AI 模型需安装并登录 Codex 或 Kimi；平台扫码不提供模型能力'], 'boundary':'只读本机探测；不读取密钥、不登录平台、不调用模型、不提交发布。历史快照不能证明当前登录有效。'}
