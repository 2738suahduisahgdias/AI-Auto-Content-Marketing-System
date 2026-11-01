import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import app
from content_workbench.api.v2 import V2Application


class LegacyAPISecurityCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="legacy-api-security-")
        self.root = Path(self.temp.name)
        self.old_root = app.ROOT
        self.old_db = app.DB_PATH
        self.old_v2 = app.V2
        app.ROOT = self.root
        app.DB_PATH = self.root / "test.db"
        app.init_db()
        app.V2 = V2Application(app.DB_PATH, app.ROOT, app.create_task)
        self.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:{}".format(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        app.V2.stop()
        app.V2 = self.old_v2
        app.ROOT = self.old_root
        app.DB_PATH = self.old_db
        self.temp.cleanup()

    def request(self, opener, path, method="GET", payload=None, headers=None):
        request_headers = dict(headers or {})
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data=data, headers=request_headers, method=method)
        try:
            with opener.open(request, timeout=10) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_legacy_api_requires_session_and_csrf_without_breaking_page_flow(self):
        anonymous = urllib.request.build_opener()
        status, body = self.request(anonymous, "/api/bootstrap")
        self.assertEqual(401, status)
        self.assertEqual("本地会话已失效", body["error"])

        attack = {"title": "外部来源不得创建", "pillar": "enterprise_ai", "audience": "business_owners"}
        status, _ = self.request(anonymous, "/api/tasks", "POST", attack, {"Origin": "https://external.example"})
        self.assertEqual(403, status)

        browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        status, _ = self.request(browser, "/api/topics/bootstrap")
        self.assertEqual(401, status)
        with browser.open(self.base + "/", timeout=10) as response:
            self.assertEqual(200, response.status)
        status, topics = self.request(browser, "/api/topics/bootstrap")
        self.assertEqual(200, status)
        self.assertTrue(topics["csrf_token"])

        status, _ = self.request(browser, "/api/tasks", "POST", attack)
        self.assertEqual(403, status)
        status, created = self.request(browser, "/api/tasks", "POST", attack,
                                      {"Origin": self.base, "X-CSRF-Token": topics["csrf_token"]})
        self.assertEqual(201, status)
        self.assertEqual("外部来源不得创建", created["title"])
        status, bootstrap = self.request(browser, "/api/bootstrap")
        self.assertEqual(200, status)
        self.assertEqual(1, len(bootstrap["tasks"]))


if __name__ == "__main__":
    unittest.main()
