#!/usr/bin/env python3
import json
import subprocess
import tempfile
import threading
import unittest
import unittest.mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from content_workbench.agents.registry import agent_config, save_agent_config
from content_workbench.providers.system import (
    provider_for,
    public_settings,
    save_settings,
)
from content_workbench.storage.db import connect, expand_schema


class SystemModelCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "data/content-agent.db"
        self.db.parent.mkdir()
        with connect(self.db) as connection:
            expand_schema(connection)
            connection.execute(
                "CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT)"
            )

    def tearDown(self):
        self.temp.cleanup()

    def test_system_switch_and_explicit_override(self):
        save_agent_config(self.db, "article_agent", {"engine": "kimi_cli"})
        save_settings(self.db, {"engine": "kimi_cli"})
        for agent in (
            "script_agent",
            "asset_planning_agent",
            "industry_topic_agent",
            "video_review_agent",
            "publish_agent",
        ):
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
            connection.execute(
                "INSERT OR REPLACE INTO settings VALUES ('agent_configs',?)",
                (
                    json.dumps(
                        {
                            "script_agent": {
                                "engine": "codex_cli",
                                "prompt": "保留提示",
                            },
                            "article_agent": {"engine": "kimi_cli"},
                        }
                    ),
                ),
            )
        save_settings(self.db, {"engine": "kimi_cli"})
        self.assertEqual(agent_config(self.db, "script_agent")["engine"], "kimi_cli")
        self.assertEqual(agent_config(self.db, "script_agent")["prompt"], "保留提示")
        save_settings(self.db, {"engine": "codex_cli"})
        self.assertEqual(agent_config(self.db, "article_agent")["engine"], "kimi_cli")

    def test_kimi_agent_model_is_passed_to_the_actual_cli(self):
        from content_workbench.providers.text import KimiCLIProvider

        context = unittest.mock.Mock()
        context.run_process.return_value = (
            '{"type":"assistant","content":[{"text":"ok"}]}',
            "",
        )
        agent = self.root / "agent.md"
        agent.write_text("测试系统指令")
        provider = KimiCLIProvider(self.root)
        with unittest.mock.patch(
            "content_workbench.providers.text.discover_cli", return_value="/tmp/kimi"
        ):
            self.assertEqual(
                provider.complete_text("测试", context, agent, model="agent-model"),
                "ok",
            )
        arguments = context.run_process.call_args.args[0]
        self.assertEqual(arguments[arguments.index("-m") + 1], "agent-model")

    def test_packaged_kimi_cli_is_preferred(self):
        from content_workbench.providers.text import discover_cli

        with (
            unittest.mock.patch.dict(
                "os.environ", {"YINGXU_KIMI_CLI": "/app/bin/kimi"}
            ),
            unittest.mock.patch(
                "content_workbench.providers.text.shutil.which", return_value=None
            ),
            unittest.mock.patch(
                "content_workbench.providers.text.Path.is_file", return_value=True
            ),
            unittest.mock.patch(
                "content_workbench.providers.text.os.access", return_value=True
            ),
        ):
            self.assertEqual(discover_cli("kimi"), "/app/bin/kimi")

    def test_api_request_and_local_secret(self):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append(
                    (
                        self.path,
                        self.headers.get("Authorization"),
                        json.loads(
                            self.rfile.read(int(self.headers["Content-Length"]))
                        ),
                    )
                )
                payload = json.dumps(
                    {"choices": [{"message": {"content": '{"text":"API执行成功"}'}}]}
                ).encode()
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
            config = {
                "engine": "model_api",
                "base_url": f"http://127.0.0.1:{server.server_port}/v1",
                "model": "test-model",
                "api_key": "local-test-key",
            }
            save_settings(self.db, config)
            agent = self.root / "agent.md"
            agent.write_text("测试系统指令")
            engine = agent_config(self.db, "article_agent")["engine"]

            def run_process(arguments, timeout, stage, cwd):
                result = subprocess.run(
                    arguments,
                    timeout=timeout,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return result.stdout, result.stderr

            save_agent_config(
                self.db,
                "article_agent",
                {"engine": "model_api", "model": "agent-model"},
            )
            result = provider_for(self.root, engine).complete_json(
                "测试用户输入",
                SimpleNamespace(run_process=run_process),
                agent,
                model=agent_config(self.db, "article_agent")["model"],
            )
            self.assertEqual(result["text"], "API执行成功")
            self.assertEqual(requests[0][0], "/v1/chat/completions")
            self.assertEqual(requests[0][1], "Bearer local-test-key")
            self.assertEqual(requests[0][2]["model"], "agent-model")
            self.assertNotIn("api_key", public_settings(self.db))
            self.assertEqual(
                (self.root / "config/text-model-secret.json").stat().st_mode & 0o777,
                0o600,
            )
            save_settings(self.db, {"engine": "codex_cli"})
            self.assertTrue(public_settings(self.db)["key_configured"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
