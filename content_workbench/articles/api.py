import re

from content_workbench.domain.errors import DomainError


class ArticleAPI:
    def __init__(self, app):
        self.app = app
        self.workbench = app.workbench
        self.jobs = app.jobs

    def handle(self, handler, method, path, body):
        body = body or {}
        if method == "GET" and path == "/api/articles/bootstrap":
            return self.app.response(handler, {"items": self.workbench.list_items("article"), "jobs": [job for job in self.jobs.list() if job["kind"].startswith("article.")][:20],
                                               "csrf_token": self.app.csrf(self.app.cookie(handler))})
        if method == "POST" and path == "/api/articles":
            title = body.get("title") or "企业AI落地，先别买工具：用一个真实任务做验收"
            item = self.workbench.create_item("article", "wechat_official_account", title, body.get("brief") or {})
            if body.get("sample"):
                outline = "一、为什么工具没有带来结果\n二、选择一个真实部门任务\n三、把任务变成工作流\n四、定义可检查的交付结果\n五、权限、数据和人员边界\n六、验收清单与下一步"
                self.workbench.save_revision(item["id"], "outline", {"text": outline}, item["version"])
                current = self.workbench.get_item(item["id"])
                draft = "很多企业开始用AI时，第一反应是买更多账号、换更强的模型。但工具还在，工作方式却没有变化。问题往往不在模型，而在于没有人把AI变成一个可以验收的工作结果。\n\n一、先选一个真实部门任务\n不要从“我们要不要做AI”开始，而从一个每周都在发生的具体任务开始，比如销售整理跟进记录、运营汇总内容数据。这个任务必须有人需要结果、过程可以描述、结果能够检查。\n\n二、把任务变成工作流\n说明资料从哪里来、哪些步骤自动完成、哪些判断必须由人确认，以及失败后如何继续。提示词只是其中一个环节，权限、数据质量、员工习惯和验收标准决定它能否进入业务。\n\n三、定义可检查的交付结果\n如果是内容生成，就检查事实、引用、格式和人工修改比例；如果是客户跟进，就检查字段完整率、遗漏和有效跟进。不要只问“好不好用”，要留下结果证据。\n\n四、边界与常见失败\n不要选择涉及客户隐私、无人负责或没有可用数据的任务。先跑通一个小结果，再扩大范围。\n\n五、验收清单\n1. 任务是否真实发生？\n2. 输入是否可用且已授权？\n3. 哪些步骤可自动完成？\n4. 哪些判断由人负责？\n5. 失败如何发现和恢复？\n6. 最终结果用什么指标验收？"
                self.workbench.save_revision(item["id"], "draft", {"text": draft, "format": "markdown"}, current["version"])
            return self.app.response(handler, self.workbench.get_item(item["id"]), 201)
        match = re.fullmatch(r"/api/articles/([^/]+)", path)
        if method == "GET" and match:
            return self.app.response(handler, self.workbench.get_item(match.group(1)))
        match = re.fullmatch(r"/api/articles/([^/]+)/revisions", path)
        if method == "POST" and match:
            revision = self.workbench.save_revision(match.group(1), body.get("kind"), body.get("payload"), body.get("expected_version"))
            return self.app.response(handler, {"revision_id": revision, "item": self.workbench.get_item(match.group(1))}, 201)
        match = re.fullmatch(r"/api/articles/([^/]+)/generate", path)
        if method == "POST" and match:
            operation = body.get("operation")
            if operation not in ("article.outline", "article.draft"):
                raise DomainError("INVALID_ARTICLE_OPERATION", "文章生成操作仅支持大纲或正文", 422, "operation", "选择大纲或正文")
            return self.app.response(handler, self.jobs.enqueue(operation, body, match.group(1), resource_key="cloud_text"), 202)
        match = re.fullmatch(r"/api/articles/([^/]+)/actions", path)
        if method == "POST" and match:
            item_id = match.group(1)
            action = body.get("action")
            if action == "submit_review":
                return self.app.response(handler, self.workbench.submit_review(item_id, body.get("expected_version")))
            if action in ("approve", "reject"):
                return self.app.response(handler, self.workbench.approve(item_id, body.get("revision_id"), body.get("manifest_hash"), "local_user", action, "article"))
            raise DomainError("UNKNOWN_ARTICLE_ACTION", "未知文章操作", 400, "action", "使用页面提供的操作")
        match = re.fullmatch(r"/api/articles/([^/]+)/export", path)
        if method == "POST" and match:
            return self.app.response(handler, self.jobs.enqueue("article.export", {"revision_id": body.get("revision_id"), "expected_version": body.get("expected_version")}, match.group(1), resource_key="export"), 202)
        match = re.fullmatch(r"/api/articles/([^/]+)/publish", path)
        if method == "POST" and match:
            return self.app.response(handler, self.workbench.record_publication(match.group(1), body.get("revision_id"), body.get("url"), body.get("published_at")), 201)
        raise DomainError("ARTICLE_API_NOT_FOUND", "文章接口不存在", 404)
