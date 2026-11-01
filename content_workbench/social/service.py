from content_workbench.domain.errors import DomainError
from content_workbench.providers.text import TextProviderRegistry
from content_workbench.social.catalog import catalog, get_operation
from content_workbench.storage.db import connect, dumps, immediate, loads, new_id, utcnow


class SocialDataService:
    def __init__(self, db_path, root, providers=None):
        self.db_path = str(db_path)
        self.root = root
        self.providers = providers or TextProviderRegistry(root)
        self.ensure_tables()

    def conn(self, readonly=False):
        return connect(self.db_path, readonly=readonly)

    def ensure_tables(self):
        with self.conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS social_data_runs(
                id TEXT PRIMARY KEY,operation_id TEXT NOT NULL,platform TEXT NOT NULL,kind TEXT NOT NULL,
                status TEXT NOT NULL,provider TEXT NOT NULL,input_json TEXT NOT NULL,result_json TEXT,
                error_json TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS social_data_runs_created ON social_data_runs(created_at DESC)")

    def bootstrap(self):
        return {**catalog(), "providers": self.providers.status(), "runs": self.list_runs(20)}

    def validate(self, operation, data):
        if not operation:
            raise DomainError("SOCIAL_OPERATION_NOT_FOUND", "社媒能力不存在", 404, "operation_id", "从能力目录选择有效接口")
        if operation["status"] != "supported":
            raise DomainError("SOCIAL_ADAPTER_REQUIRED", "该能力已纳入目录，但本地适配器尚未完成", 501, "operation_id",
                              "先使用目录中 supported 的能力；未验收接口不会返回伪数据")
        if operation["executor"] == "local_transcript" and operation["path"].endswith("/get"):
            raise DomainError("SOCIAL_RUN_LOOKUP_ONLY", "转写结果通过运行记录查询", 422, "run_id", "调用运行详情接口")
        if operation["kind"] == "search" and not str(data.get("keyword") or "").strip():
            raise DomainError("SOCIAL_KEYWORD_REQUIRED", "搜索关键词不能为空", 422, "keyword", "填写公开内容搜索关键词")
        if operation["executor"] == "browser_model" and operation["kind"] != "search":
            url = data.get("url") or data.get("note_url") or data.get("profile_url")
            if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                raise DomainError("SOCIAL_URL_REQUIRED", "当前本地采集器需要公开页面链接", 422, "url", "传入可公开访问的 HTTP(S) 链接")
        if operation["executor"] == "local_download" and not str(data.get("url") or "").startswith(("https://", "http://")):
            raise DomainError("SOCIAL_URL_REQUIRED", "下载解析需要公开视频链接", 422, "url", "传入 B站视频链接")
        if operation["executor"] == "local_transcript":
            if not str(data.get("media_path") or "").strip():
                raise DomainError("SOCIAL_MEDIA_REQUIRED", "本地转写需要媒体文件路径", 422, "media_path", "选择项目目录内的音视频文件")
            if data.get("model", "base") not in ("base", "small"):
                raise DomainError("SOCIAL_ASR_MODEL_INVALID", "本地转写模型仅支持 base/small", 422, "model", "选择 base 或 small")

    def create_run(self, operation_id, data, provider="kimi_cli"):
        operation = get_operation(operation_id)
        data = data or {}
        self.validate(operation, data)
        if operation["executor"] == "browser_model":
            self.providers.get(provider)
        else:
            provider = "local_worker"
        run_id = new_id("social")
        timestamp = utcnow()
        with self.conn() as conn, immediate(conn):
            conn.execute("INSERT INTO social_data_runs VALUES (?,?,?,?,'queued',?,?,?,NULL,?,?)",
                         (run_id, operation_id, operation["platform"], operation["kind"], provider,
                          dumps(data), "{}", timestamp, timestamp))
        return self.get_run(run_id)

    def start_run(self, run_id):
        self.update_run(run_id, "running")

    def finish_run(self, run_id, result):
        self.update_run(run_id, "succeeded", result=result)

    def fail_run(self, run_id, error):
        self.update_run(run_id, "failed", error=error)

    def update_run(self, run_id, status, result=None, error=None):
        with self.conn() as conn, immediate(conn):
            if result is not None:
                conn.execute("UPDATE social_data_runs SET status=?,result_json=?,updated_at=? WHERE id=?",
                             (status, dumps(result), utcnow(), run_id))
            elif error is not None:
                conn.execute("UPDATE social_data_runs SET status=?,error_json=?,updated_at=? WHERE id=?",
                             (status, dumps(error), utcnow(), run_id))
            else:
                conn.execute("UPDATE social_data_runs SET status=?,updated_at=? WHERE id=?", (status, utcnow(), run_id))

    def get_run(self, run_id):
        with self.conn(readonly=True) as conn:
            row = conn.execute("SELECT * FROM social_data_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise DomainError("SOCIAL_RUN_NOT_FOUND", "社媒数据运行记录不存在", 404, "run_id", "刷新运行列表")
        return self.run_dict(row)

    def list_runs(self, limit=100):
        with self.conn(readonly=True) as conn:
            rows = conn.execute("SELECT * FROM social_data_runs ORDER BY created_at DESC LIMIT ?", (min(limit, 200),)).fetchall()
        return [self.run_dict(row) for row in rows]

    @staticmethod
    def run_dict(row):
        value = dict(row)
        value["input"] = loads(value.pop("input_json"), {})
        value["result"] = loads(value.pop("result_json"), {})
        value["error"] = loads(value.pop("error_json"), None)
        return value
