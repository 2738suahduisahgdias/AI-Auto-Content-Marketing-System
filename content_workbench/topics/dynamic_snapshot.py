import re
import time
from urllib.parse import urlsplit

from content_workbench.accounts.existing_browser import body
from content_workbench.domain.errors import DomainError
from content_workbench.publishing.webbridge_worker import Bridge
from content_workbench.storage.db import utcnow
from content_workbench.topics.link_snapshot import PLATFORM_LABELS, detect_platform


def parse_dynamic_document(text, details, url):
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    author = None
    for index, line in enumerate(lines):
        if line.startswith("粉丝"):
            for previous in reversed(lines[:index]):
                if previous not in ("关注", "作者", "...", "加载中"):
                    author = previous
                    break
            break
    followers = re.search(r"粉丝\s*([\d.,]+[万wW]?)", text)
    published_at = re.search(r"发布时间：([^\n]+)", text)
    title = details.get("heading") or details.get("title") or None
    description = details.get("heading") if details.get("heading") != title else None
    return {"title": title, "description": description, "site_name": urlsplit(url).hostname,
            "cover_url": details.get("cover_url") or None, "canonical_url": url, "source_url": url,
            "excerpt": text[:1200] or None, "platform": detect_platform(url),
            "platform_label": PLATFORM_LABELS[detect_platform(url)], "author": author,
            "author_followers": followers.group(1) if followers else None,
            "published_at": published_at.group(1).strip() if published_at else None,
            "captured_at": utcnow(), "parser": "existing_browser_dynamic_v1",
            "limited": not bool(title or author or details.get("cover_url")),
            "dynamic_attempted": True, "dynamic_error": None}


def fetch_dynamic_snapshot(url, message_id=None):
    bridge = Bridge()
    try:
        bridge.goto(url)
        time.sleep(4)
        text = body(bridge)
        details = bridge.evaluate("""() => ({
          heading: document.querySelector('h1')?.innerText.trim() || '',
          title: document.title || '',
          cover_url: document.querySelector('video')?.poster || document.querySelector('meta[property="og:image"]')?.content || ''
        })""") or {}
        snapshot_url = bridge.snapshot().get("url") or url
        snapshot = parse_dynamic_document(text, details, snapshot_url)
        if not snapshot["cover_url"] and message_id:
            result = bridge.screenshot(message_id, "link-cover")
            if result:
                snapshot["cover_url"] = "/api/topics/wechat/snapshots/" + message_id + "/cover"
                snapshot["cover_source"] = "page_viewport"
        return snapshot
    except DomainError:
        raise
    except Exception as error:
        raise DomainError("SNAPSHOT_DYNAMIC_UNAVAILABLE", "现有浏览器未能读取动态页面：" + str(error)[:300], 502,
                          "original_url", "检查现有浏览器连接后手动重新解析，不自动重试")
