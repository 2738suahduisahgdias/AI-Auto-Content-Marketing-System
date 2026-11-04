import json
import sqlite3
import subprocess
from types import SimpleNamespace
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from content_workbench.agents.registry import agent_config, save_agent_config
from content_workbench.providers.system import provider_for, public_settings, save_settings
from content_workbench.storage.db import connect, expand_schema


class SystemModelCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "data/content-agent.db"
        self.db.parent.mkdir()
        with connect(self.db) as connection:
            expand_schema(connection)
            connection.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT)")

    def tearDown(self):
        self.temp.cleanup()

    def test_system_switch_and_explicit_override(self):
        save_agent_config(self.db, "article_agent", {"engine": "kimi_cli"})
        save_settings(self.db, {"engine": "kimi_cli"})
        for agent in ("script_agent", "asset_planning_agent", "industry_topic_agent", "video_review_agent", "publish_agent"):
            self.assertEqual(agent_config(self.db, agent)["engine"], "kimi_cli")
        save_settings(self.db, {"engine": "codex_cli"})
        self.assertEqual(agent_config(self.db, "script_agent")["engine"], "codex_cli")
        self.assertEqual(agent_config(self.db, "article_agent")["engine"], "kimi_cli")
        save_agent_config(self.db, "article_agent", {"engine": "system"})
        self.assertTrue(agent_config(self.db, "article_agent")["follow_system"])
        self.assertEqual(agent_config(self.db, "article_agent")["engine"], "codex_cli")
        self.assertEqual(agent_config(self.db, "remotion_agent")["engine"], "remotion")

    def test_legacy_default_configuration_inherits(self):
        with connect(self.db) as connection:
            connection.execute("INSERT OR REPLACE INTO settings VALUES ('agent_configs',?)",
                               (json.dumps({"script_agent": {"engine": "codex_cli", "prompt": "保留提示"},
                                            "article_agent": {"engine": "kimi_cli"}}),))
        save_settings(self.db, {"engine": "kimi_cli"})
        self.assertEqual(agent_config(self.db, "script_agent")["engine"], "kimi_cli")
        self.assertEqual(agent_config(self.db, "script_agent")["prompt"], "保留提示")
        save_settings(self.db, {"engine": "codex_cli"})
        self.assertEqual(agent_config(self.db, "article_agent")["engine"], "kimi_cli")

    def test_api_request_and_local_secret(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append((self.path, self.headers.get("Authorization"),
                                 json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                payload = json.dumps({"choices": [{"message": {"content": '{"text":"API执行成功"}'}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            config = {"engine": "model_api", "base_url": "http://127.0.0.1:{}/v1".format(server.server_port),
                      "model": "test-model", "api_key": "local-test-key"}
            save_settings(self.db, config)
            agent = self.root / "agent.md"
            agent.write_text("测试系统指令")
            engine = agent_config(self.db, "article_agent")["engine"]
            def run_process(arguments, timeout, stage, cwd):
                result = subprocess.run(arguments, timeout=timeout, cwd=cwd, capture_output=True, text=True, check=True)
                return result.stdout, result.stderr
            result = provider_for(self.root, engine).complete_json("测试用户输入", SimpleNamespace(run_process=run_process), agent)
            self.assertEqual(result["text"], "API执行成功")
            self.assertEqual(requests[0][0], "/v1/chat/completions")
            self.assertEqual(requests[0][1], "Bearer local-test-key")
            self.assertEqual(requests[0][2]["model"], "test-model")
            self.assertNotIn("api_key", public_settings(self.db))
            self.assertEqual((self.root / "config/text-model-secret.json").stat().st_mode & 0o777, 0o600)
            save_settings(self.db, {"engine": "codex_cli"})
            self.assertTrue(public_settings(self.db)["key_configured"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
