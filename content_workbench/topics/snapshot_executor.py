from content_workbench.domain.errors import DomainError
from content_workbench.topics.dynamic_snapshot import fetch_dynamic_snapshot
from content_workbench.topics.link_snapshot import fetch_public_snapshot


class WechatSnapshotExecutor:
    def __init__(self, inbox):
        self.inbox = inbox

    def run(self, job, context):
        message_id = job["aggregate_id"]
        message = self.inbox.get(message_id)
        if not message.get("original_url"):
            raise DomainError("SNAPSHOT_URL_MISSING", "这条微信消息没有可解析链接", 422, "original_url", "先在后台补充原始链接")
        self.inbox.update_snapshot(message_id, "running")
        try:
            snapshot = fetch_public_snapshot(message["original_url"])
        except Exception as error:
            self.inbox.update_snapshot(message_id, "failed", error=str(error)[:500])
            if isinstance(error, DomainError):
                raise
            raise DomainError("SNAPSHOT_FAILED", "链接快照生成失败：" + str(error)[:300], 502, "original_url", "检查公开链接后手动重试")
        if snapshot.get("platform") != "generic" and (snapshot.get("limited") or not snapshot.get("author") or not snapshot.get("cover_url")):
            try:
                snapshot = fetch_dynamic_snapshot(message["original_url"], message_id)
            except DomainError as error:
                snapshot["dynamic_attempted"] = True
                snapshot["dynamic_error"] = error.message
                snapshot["limited"] = True
        self.inbox.update_snapshot(message_id, "succeeded", snapshot=snapshot)
        return {"message_id": message_id, "snapshot_status": "succeeded", "limited": snapshot["limited"],
                "title": snapshot.get("title"), "site_name": snapshot.get("site_name")}
