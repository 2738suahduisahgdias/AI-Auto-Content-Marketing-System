#!/usr/bin/env python3
"""Small Playwright adapter for account collectors that already use the bridge contract."""

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from content_workbench.topics.browser_worker import close_context, open_context


class LocalBrowser:
    def __init__(self, profile: Path):
        self.profile = Path(profile)
        self.manager = None
        self.context = None
        self.page = None

    def __enter__(self):
        self.manager = sync_playwright().start()
        self.context = open_context(self.manager, self.profile)
        self.page = (
            self.context.pages[0] if self.context.pages else self.context.new_page()
        )
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        close_context(self.context)
        self.manager.stop()

    def goto(self, url: str) -> None:
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        self.page.wait_for_timeout(3000)

    def evaluate(self, expression: str):
        return self.page.evaluate(expression)

    def snapshot(self) -> dict:
        return {
            "url": self.page.url,
            "title": self.page.title(),
            "tree": [self.page.locator("body").inner_text()],
        }

    def wait_for_text(self, text: str, timeout: int = 15) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if text in self.page.locator("body").inner_text():
                return True
            self.page.wait_for_timeout(500)
        return False

    def click_text(self, text: str, prefix: bool = False, timeout: int = 0) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            for frame in self.page.frames:
                locator = frame.get_by_text(text, exact=not prefix)
                for index in range(locator.count()):
                    candidate = locator.nth(index)
                    if candidate.is_visible() and candidate.is_enabled():
                        candidate.click()
                        return True
            if time.monotonic() >= deadline:
                return False
            self.page.wait_for_timeout(250)

    def call(self, action: str, args: dict) -> dict:
        if action == "navigate":
            self.goto(args["url"])
            return {"success": True, "url": self.page.url}
        if action == "find_tab":
            return {"success": True, "url": self.page.url}
        if action == "click":
            self.page.locator(args["selector"]).first.click()
            return {"success": True}
        if action == "upload":
            self.page.locator(args["selector"]).first.set_input_files(args["files"])
            return {"success": True, "fileCount": len(args["files"])}
        if action == "screenshot":
            path = Path(args["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(path))
            return {"path": str(path)}
        raise RuntimeError("内置浏览器不支持动作：" + action)
