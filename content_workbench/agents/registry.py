from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import connect, dumps, loads

AGENTS = {
    "hotspot_agent": {"name": "热点情报Agent", "description": "热榜与收藏快照采集", "engines": ["playwright"], "engine": "playwright", "model": "topics-v1", "timeout": 1800, "attempts": 3, "concurrency": 1, "prompt": False, "connected": True},
    "industry_topic_agent": {"name": "行业选题Agent", "description": "行业资讯分析与今日推荐", "engines": ["kimi_cli"], "engine": "kimi_cli", "model": "default_unpinned", "timeout": 600, "attempts": 3, "concurrency": 2, "prompt": True, "connected": True},
    "douyin_topic_agent": {"name": "抖音选题Agent", "description": "抖音热榜、收藏与今日推荐", "engines": ["kimi_cli"], "engine": "kimi_cli", "model": "default_unpinned", "timeout": 600, "attempts": 3, "concurrency": 2, "prompt": True, "connected": True},
    "script_agent": {"name": "脚本Agent", "description": "母稿与平台版本生成", "engines": ["kimi_cli"], "engine": "kimi_cli", "model": "default_unpinned", "timeout": 600, "attempts": 3, "concurrency": 2, "prompt": True, "connected": True},
    "asset_planning_agent": {"name": "素材规划Agent", "description": "口播与 SRT 分镜规划", "engines": ["kimi_cli"], "engine": "kimi_cli", "model": "default_unpinned", "timeout": 600, "attempts": 3, "concurrency": 2, "prompt": True, "connected": True},
    "voice_agent": {"name": "配音Agent", "description": "macOS 系统语音生成", "engines": ["macos_say"], "engine": "macos_say", "model": "system_voice", "timeout": 300, "attempts": 2, "concurrency": 1, "prompt": False, "connected": True},
    "clone_agent": {"name": "本人音色Agent", "description": "OpenVoice 本人授权音色克隆", "engines": ["openvoice"], "engine": "openvoice", "model": "v2_zh_cpu", "timeout": 3600, "attempts": 2, "concurrency": 1, "prompt": False, "connected": True},
    "caption_agent": {"name": "字幕转写Agent", "description": "faster-whisper 本地字幕", "engines": ["faster_whisper"], "engine": "faster_whisper", "model": "small", "variants": ["small", "base"], "timeout": 3600, "attempts": 2, "concurrency": 1, "prompt": False, "connected": True},
    "remotion_agent": {"name": "Remotion视频Agent", "description": "Remotion 与 FFmpeg 视频构建", "engines": ["remotion", "ffmpeg"], "engine": "remotion", "model": "TalkingHead", "timeout": 1800, "attempts": 2, "concurrency": 1, "prompt": False, "connected": True},
    "quality_agent": {"name": "合规质检Agent", "description": "自动规格与内容质检", "engines": ["manual"], "engine": "manual", "model": "not_connected", "timeout": 600, "attempts": 1, "concurrency": 1, "prompt": False, "connected": False},
    "publish_agent": {"name": "发布助手Agent", "description": "平台字段生成、发布检查、预览填充与人工确认", "engines": ["kimi_cli", "playwright"], "engine": "kimi_cli", "model": "default_unpinned", "timeout": 1800, "attempts": 2, "concurrency": 1, "prompt": True, "connected": True},
    "retro_agent": {"name": "发布复盘Agent", "description": "复盘结论与下一轮建议", "engines": ["manual"], "engine": "manual", "model": "not_connected", "timeout": 600, "attempts": 1, "concurrency": 1, "prompt": False, "connected": False},
    "analytics_agent": {"name": "数据分析Agent", "description": "账号指标采集与比较", "engines": ["manual"], "engine": "manual", "model": "not_connected", "timeout": 600, "attempts": 1, "concurrency": 1, "prompt": False, "connected": False},
    "account_analysis_agent": {"name": "账号分析Agent", "description": "账号日报、表现分析与今日推荐", "engines": ["kimi_cli"], "engine": "kimi_cli", "model": "default_unpinned", "timeout": 600, "attempts": 3, "concurrency": 2, "prompt": True, "connected": True},
    "article_agent": {"name": "文章创作Agent", "description": "文章大纲、正文、引用与导出", "engines": ["kimi_cli"], "engine": "kimi_cli", "model": "default_unpinned", "timeout": 600, "attempts": 3, "concurrency": 2, "prompt": True, "connected": True},
    "workflow_agent": {"name": "流程监督Agent", "description": "每日调度、提醒与恢复", "engines": ["scheduler"], "engine": "scheduler", "model": "daily", "timeout": 60, "attempts": 3, "concurrency": 1, "prompt": False, "connected": True},
    "video_review_agent": {"name": "短视频审核Agent", "description": "批量技术预审与风险证据整理", "engines": ["kimi_cli"], "engine": "kimi_cli", "model": "default_unpinned", "timeout": 600, "attempts": 2, "concurrency": 1, "prompt": True, "connected": True},
    "schedule_agent": {"name": "发布调度Agent", "description": "批量定时、间隔与发布队列管理", "engines": ["scheduler"], "engine": "scheduler", "model": "interval_queue", "timeout": 60, "attempts": 3, "concurrency": 1, "prompt": False, "connected": True},
}
DEFAULT_PROMPTS = {
    "industry_topic_agent": "优先真实业务、流程改造、验收和可复用方法。",
    "douyin_topic_agent": "热点只作场景，优先差异化、真实证据和账号定位。",
    "script_agent": "语言直接具体，不编造证据，短视频适合自然口播。",
    "asset_planning_agent": "优先真实业务画面、录屏、流程图和简洁文字卡。",
    "account_analysis_agent": "区分事实、推断和待验证实验，不编造指标或稳定规律。",
    "article_agent": "先明确读者、真实任务和核心结论，用证据组织步骤、边界与行动清单。",
    "publish_agent": "按平台分别生成可直接检查的标题、正文或简介、摘要和标签；保留事实边界，不生成人工选项，不执行发布。",
    "video_review_agent": "只基于实际证据指出风险位置与核查建议，不判断事实、版权或平台合规结论。",
}


def default_config(agent_id):
    definition = AGENTS[agent_id]
    return {"enabled": definition["connected"], "engine": definition["engine"], "model": definition["model"],
            "prompt": DEFAULT_PROMPTS.get(agent_id, ""), "timeout_seconds": definition["timeout"],
            "max_attempts": definition["attempts"], "concurrency": definition["concurrency"], "custom": {}}


def agent_config(db_path, agent_id):
    if agent_id not in AGENTS:
        raise DomainError("AGENT_NOT_FOUND", "Agent 不存在", 404, "agent_id", "从注册表选择有效 Agent")
    with connect(db_path, readonly=True) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='agent_configs'").fetchone()
    stored = loads(row[0], {}) if row else {}
    config = {**default_config(agent_id), **stored.get(agent_id, {})}
    definition = AGENTS[agent_id]
    if config["engine"] not in definition["engines"]:
        config["engine"] = definition["engine"]
    if not definition["connected"]:
        config["enabled"] = False
    return config


def all_agent_configs(db_path):
    return {agent_id: agent_config(db_path, agent_id) for agent_id in AGENTS}


def save_agent_config(db_path, agent_id, values):
    definition = AGENTS[agent_id]
    if values.get("reset"):
        updated = default_config(agent_id)
    else:
        current = agent_config(db_path, agent_id)
        updated = dict(current)
        for key in ("enabled", "engine", "model", "prompt", "timeout_seconds", "max_attempts", "concurrency", "custom"):
            if key in values:
                updated[key] = values[key]
        if updated["engine"] not in definition["engines"]:
            raise DomainError("INVALID_AGENT_ENGINE", "该 Agent 不支持这个执行引擎", 422, "engine", "从页面提供的引擎列表选择")
        if updated["enabled"] and not definition["connected"]:
            raise DomainError("AGENT_NOT_CONNECTED", "该 Agent 尚未接入，不能启用", 409, "enabled", "先完成对应连接器和真实验收")
        if not isinstance(updated["enabled"], bool):
            raise DomainError("INVALID_AGENT_ENABLED", "启用状态必须是布尔值", 422, "enabled", "使用打开或关闭")
        if not isinstance(updated["model"], str) or not updated["model"].strip() or len(updated["model"]) > 100:
            raise DomainError("INVALID_AGENT_MODEL", "模型或变体需为 1～100 字符", 422, "model", "填写已支持的变体")
        variants = definition.get("variants")
        if variants and updated["model"] not in variants:
            raise DomainError("INVALID_AGENT_VARIANT", "不支持的模型变体", 422, "model", "选择 " + " / ".join(variants))
        if not isinstance(updated["prompt"], str) or len(updated["prompt"]) > 12000:
            raise DomainError("INVALID_AGENT_PROMPT", "补充提示词不能超过 12000 字符", 422, "prompt", "精简提示词")
        for key, minimum, maximum in (("timeout_seconds", 30, 3600), ("max_attempts", 1, 5), ("concurrency", 1, 2)):
            value = updated[key]
            if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
                raise DomainError("INVALID_AGENT_LIMIT", "{} 超出允许范围".format(key), 422, key,
                                  "{} 必须在 {}～{} 之间".format(key, minimum, maximum))
        if not isinstance(updated["custom"], dict) or len(dumps(updated["custom"])) > 4000:
            raise DomainError("INVALID_AGENT_CUSTOM", "扩展配置无效", 422, "custom", "只提交支持的扩展字段")
    with connect(db_path) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='agent_configs'").fetchone()
        stored = loads(row[0], {}) if row else {}
        stored[agent_id] = updated
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES ('agent_configs',?)", (dumps(stored),))
    return updated


def require_agent_enabled(db_path, agent_id):
    config = agent_config(db_path, agent_id)
    if not config["enabled"]:
        raise DomainError("AGENT_DISABLED", AGENTS[agent_id]["name"] + "已停用", 409, "enabled", "到设置页启用该 Agent 后创建新任务")
    return config
