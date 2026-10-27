import json
import shutil
from pathlib import Path

from content_workbench.agents.registry import require_agent_enabled
from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import utcnow
from .media_review import review_media


class ReviewExecutors:
    def __init__(self, service):
        self.service = service
        self.root = service.root

    def mapping(self):
        return {"review.scan": self.scan, "review.repair": self.repair, "review.ai": self.ai}

    def scan(self, job, context):
        batch = self.service.get_batch(job["input"]["batch_id"])
        results = []
        for item in batch["items"]:
            if item["decision"] == "approved":
                continue
            context.progress("media_review:" + item["id"], None)
            try:
                options = dict(batch["rules"])
                check_ocr = options.pop("check_ocr", True)
                options.pop("ai_risk", None)
                report = review_media(item["source_path"], check_ocr=check_ocr, **options)
                status = "needs_review"
                error = None
            except Exception as exc:
                report = {"status": "failed", "issues": [{"type": "review_failed", "severity": "error", "recommendation": str(exc)}]}
                status = "failed"
                error = {"code": "REVIEW_MEDIA_FAILED", "message": str(exc)[:800], "action": "检查文件后重新预审"}
            with self.service.conn() as conn:
                conn.execute("UPDATE review_items SET status=?,report_json=?,error_json=?,updated_at=? WHERE id=?",
                             (status, json.dumps(report, ensure_ascii=False), json.dumps(error, ensure_ascii=False) if error else None,
                              utcnow(), item["id"]))
            results.append({"id": item["id"], "status": status})
        with self.service.conn() as conn:
            conn.execute("UPDATE review_batches SET status='needs_review',updated_at=? WHERE id=?",
                         (utcnow(), batch["id"]))
        return {"items": results, "human_review_required": True}

    def repair(self, job, context):
        item_id = job["input"]["item_id"]
        with self.service.conn(readonly=True) as conn:
            item = conn.execute("SELECT * FROM review_items WHERE id=?", (item_id,)).fetchone()
        if not item:
            raise DomainError("REVIEW_ITEM_NOT_FOUND", "审核视频不存在", 404, "item_id", "刷新审核批次")
        report = json.loads(item["report_json"])
        command = report["safe_transcode_candidate"]["command"]
        work = Path(item["source_path"]).parent / ".审核工作"
        work.mkdir(exist_ok=True)
        candidate = work / (Path(item["source_path"]).stem + ".mp4")
        command = [str(candidate) if value == "media-review-output.mp4" else value for value in command]
        context.run_process(command, timeout=1800, stage="safe_transcode")
        report = review_media(candidate)
        with self.service.conn() as conn:
            conn.execute("UPDATE review_items SET status='needs_review',candidate_path=?,report_json=?,updated_at=? WHERE id=?",
                         (str(candidate), json.dumps(report, ensure_ascii=False),
                          utcnow(), item_id))
        return {"candidate_path": str(candidate), "source_unchanged": True, "human_review_required": True}

    def ai(self, job, context):
        config = require_agent_enabled(self.service.db_path, "video_review_agent")
        batch = self.service.get_batch(job["input"]["batch_id"])
        binary = shutil.which("kimi") or str(Path.home() / ".kimi-code/bin/kimi")
        if not Path(binary).is_file():
            raise DomainError("KIMI_NOT_FOUND", "未找到 Kimi CLI", 503, "provider", "安装并登录后重试")
        items = [{"item_id": item["id"], "filename": Path(item["source_path"]).name,
                  "technical_report": item["report"]} for item in batch["items"] if item["report"]]
        if not items:
            raise DomainError("REVIEW_REQUIRED", "没有可供风险分析的机器预审报告", 409, "batch_id", "先完成机器预审")
        prompt = json.dumps({"operation": "短视频风险证据分析，逐条返回结果，不得声称看到了未提供的画面或事实",
                             "items": items, "agent_supplement": config["prompt"]}, ensure_ascii=False)
        agent = self.root / "agents/video-review-agent.md"
        stdout, _ = context.run_process([binary, "--agent-file", str(agent), "-p", prompt, "--output-format", "stream-json"],
                                        timeout=config["timeout_seconds"], stage="video_review_agent", cwd=self.root)
        contents = []
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "assistant" and event.get("role") != "assistant":
                continue
            content = event.get("content")
            if isinstance(content, list):
                content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            elif isinstance(content, dict):
                content = content.get("text", "")
            if isinstance(content, str) and content.strip():
                contents.append(content.strip())
        try:
            payload = json.loads(contents[-1])
            risks = payload["items"]
            by_id = {item["item_id"]: item for item in risks}
        except (IndexError, json.JSONDecodeError, KeyError, TypeError):
            raise DomainError("REVIEW_AI_SCHEMA_INVALID", "审核 Agent 未返回规定的 items 风险数组", 502, "provider", "重试或人工完成风险审核")
        for item in batch["items"]:
            risk = by_id.get(item["id"], {"risks": [], "evidence_scope": "模型未返回该视频风险分析"})
            with self.service.conn() as conn:
                conn.execute("UPDATE review_items SET ai_risk_json=?,updated_at=? WHERE id=?",
                             (json.dumps(risk, ensure_ascii=False), utcnow(), item["id"]))
        return {"items": len(risks), "evidence_only": True, "human_review_required": True}
