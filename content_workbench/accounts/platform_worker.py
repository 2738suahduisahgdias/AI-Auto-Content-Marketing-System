import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    sync_playwright = None

from content_workbench.topics.browser_worker import open_context, visible_videos


def xhs_logged_in(context):
    names = {cookie["name"] for cookie in context.cookies("https://creator.xiaohongshu.com")}
    return bool(names & {"web_session", "webId", "a1", "web_sessionid"})


def xhs_notes(page):
    page.goto("https://creator.xiaohongshu.com/new/note-manager", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)
    if "login" in page.url:
        return {"status": "login_required"}
    cards = page.evaluate("""() => Array.from(document.querySelectorAll('.note-card')).map(card => ({
      title: card.querySelector('.note-card__title')?.innerText.trim() || '',
      text: card.innerText,
      impression: card.getAttribute('data-impression') || '',
      cover: card.querySelector('.note-card__media')?.style.backgroundImage || ''
    }))""")
    items = []
    for card in cards:
        if not card["title"]:
            continue
        note_id = ""
        try:
            impression = json.loads(card["impression"])
            note_id = impression.get("noteTarget", {}).get("value", {}).get("noteId", "")
        except (TypeError, json.JSONDecodeError):
            pass
        text = card["text"]
        published_at = re.search(r"20\d{2}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?", text)
        items.append({"title": card["title"], "canonical_url": "https://www.xiaohongshu.com/explore/" + note_id if note_id else "https://creator.xiaohongshu.com/new/note-manager",
                      "platform_item_id": note_id or None,
                      "metadata": {"title": card["title"], "cover_url": card["cover"], "visible_text": text[:2000],
                                   "visible_metrics": re.findall(r"\d+(?:\.\d+)?[万wW]?", text),
                                   "published_at": published_at.group(0) if published_at else None}})
    return {"status": "ok", "items": items}


def douyin_account(page):
    page.goto("https://www.douyin.com/user/self", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3500)
    if "login" in page.url or "登录后查看" in page.locator("body").inner_text():
        return {"status": "login_required"}
    page.mouse.wheel(0, 2200)
    page.wait_for_timeout(3000)
    body = page.locator("body").inner_text()
    def match(pattern):
        found = re.search(pattern, body)
        return found.group(1) if found else None
    profile = {"account_name": match(r"抖音号：([^\n]+)"), "fans": match(r"粉丝\s*(\d+(?:\.\d+)?[万wW]?)"),
               "likes": match(r"获赞\s*(\d+(?:\.\d+)?[万wW]?)"), "works_count": match(r"作品\s*(\d+)") }
    items = visible_videos(page, 20)
    return {"status": "ok", "profile": profile, "items": items}


def labeled_metrics(text, platform):
    labels = {"views": ("播放量", "播放", "阅读", "观看"),
              "likes": ("点赞", "推荐", "获赞", "喜欢", "在看"),
              "comments": ("评论", "评论数"), "shares": ("分享", "转发"),
              "favorites": ("收藏", "收藏数"), "fans": ("粉丝", "关注者", "关注人数")}
    result = {}
    for key, names in labels.items():
        for name in names:
            found = re.search(re.escape(name) + r"(?:量|数|人数)?\s*[：:]?\s*(\d+(?:\.\d+)?[万wW]?)", text)
            if found:
                result[key] = found.group(1)
                break
    return result


def linked_items(page, platform):
    raw_items = page.evaluate("""(platform) => {
      const result=[];const seen=new Set();
      for(const a of document.querySelectorAll('a[href]')){
        const href=a.href;const text=(a.innerText||a.closest('tr')?.innerText||a.closest('li')?.innerText||'').trim();
        if(!text||seen.has(href))continue;
        const relevant=platform==='wechat_official_account'?/appmsg|__biz/.test(href):/post|video/.test(href);
        if(!relevant)continue;
        if(platform!=='wechat_official_account'&&!a.querySelector('img'))continue;
        const lines=text.split('\\n').map(x=>x.trim()).filter(Boolean);
        const title=lines.filter(x=>x.length>1&&!/^[\\d.,]+[万wW]?$/.test(x)).sort((a,b)=>b.length-a.length)[0];
        if(!title)continue;
        seen.add(href);result.push({title,canonical_url:href,metadata:{title,visible_text:text.slice(0,2000),cover_url:a.querySelector('img')?.src||''}});
        if(result.length>=50)break;
      }
      return result;
    }""", platform)
    for item in raw_items:
        text = item["metadata"].get("visible_text", "")
        published_at = re.search(r"20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}", text)
        item["metadata"]["published_at"] = published_at.group(0) if published_at else None
        item["metrics"] = labeled_metrics(text, platform)
    return raw_items


def channels_account(page):
    page.goto("https://channels.weixin.qq.com/platform/post/list", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)
    body = page.locator("body").inner_text()
    if "login" in page.url or "登录视频号助手" in body:
        return {"status": "login_required"}
    return {"status": "ok", "profile": labeled_metrics(body, "wechat_channels"), "items": linked_items(page, "wechat_channels")}


def official_account(page):
    page.goto("https://mp.weixin.qq.com/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)
    body = page.locator("body").inner_text()
    if "使用账号登录" in body or "扫码登录" in body:
        return {"status": "login_required"}
    query = re.search(r"[?&]token=(\d+)", page.url)
    if query:
        page.goto("https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_list&action=list&token=" + query.group(1), wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        body = page.locator("body").inner_text()
    return {"status": "ok", "profile": labeled_metrics(body, "wechat_official_account"), "items": linked_items(page, "wechat_official_account")}


def publish_preview(page, video, title, description):
    page.goto("https://creator.douyin.com/creator-micro/content/upload", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    inputs = page.locator("input[type=file]")
    if not inputs.count():
        raise RuntimeError("未检测到抖音发布上传控件：请先在专用窗口登录创作者后台；若已登录，发布页结构可能已变化")
    inputs.first.set_input_files(str(video))
    page.wait_for_timeout(5000)
    textareas = page.locator("textarea")
    if textareas.count():
        textareas.first.fill(title)
    editors = page.locator("[contenteditable=true]")
    if editors.count():
        editors.first.fill(description)
    page.wait_for_timeout(2500)
    return {"status": "preview_ready", "title": title, "description": description, "auto_published": False}


def login_verified(page, action):
    try:
        body = page.locator("body").inner_text()
    except Exception:
        return False
    if action == "xiaohongshu_login":
        return xhs_logged_in(page.context) and "login" not in page.url
    if action == "douyin_publish_login":
        return "login" not in page.url and "短信验证" not in body and "扫码登录" not in body
    if action == "channels_login":
        return "login" not in page.url and "登录视频号助手" not in body
    if action == "official_login":
        return bool(re.search(r"[?&]token=\d+", page.url)) or ("使用账号登录" not in body and "扫码登录" not in body)
    return False


def wait_for_login(page, action, timeout_seconds=180, sleep_seconds=3):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if login_verified(page, action):
            return {"status": "ok", "login_verified": True, "next_action": "自动同步全部账号并刷新数据"}
        page.wait_for_timeout(sleep_seconds * 1000)
    return {"status": "login_required", "error": "3 分钟内未完成登录", "action": "请重新发起登录，在打开的页面完成扫码或验证"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("xhs_notes", "douyin_account", "channels_account", "official_account", "publish_preview", "xiaohongshu_login", "douyin_publish_login", "channels_login", "official_login"), required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--video")
    parser.add_argument("--title", default="")
    parser.add_argument("--description", default="")
    args = parser.parse_args()
    if sync_playwright is None:
        raise RuntimeError("真实账号采集需要 .venv-topics 隔离环境中的 Playwright，请先运行安装脚本")
    with sync_playwright() as p:
        context = open_context(p, Path(args.profile).resolve())
        try:
            page = context.pages[0] if context.pages else context.new_page()
            if args.action == "xhs_notes":
                if not xhs_logged_in(context):
                    print(json.dumps({"status": "login_required"}, ensure_ascii=False))
                else:
                    print(json.dumps(xhs_notes(page), ensure_ascii=False))
            elif args.action == "douyin_account":
                print(json.dumps(douyin_account(page), ensure_ascii=False))
            elif args.action == "channels_account":
                print(json.dumps(channels_account(page), ensure_ascii=False))
            elif args.action == "official_account":
                print(json.dumps(official_account(page), ensure_ascii=False))
            elif args.action in ("xiaohongshu_login", "douyin_publish_login", "channels_login", "official_login"):
                urls = {"xiaohongshu_login": "https://creator.xiaohongshu.com/",
                        "douyin_publish_login": "https://creator.douyin.com/creator-micro/content/upload",
                        "channels_login": "https://channels.weixin.qq.com/login.html",
                        "official_login": "https://mp.weixin.qq.com/"}
                page.goto(urls[args.action], wait_until="domcontentloaded", timeout=60000)
                print(json.dumps(wait_for_login(page, args.action), ensure_ascii=False))
            else:
                if not args.video:
                    raise ValueError("video required")
                print(json.dumps(publish_preview(page, Path(args.video).resolve(), args.title, args.description), ensure_ascii=False))
        except Exception as error:
            print(json.dumps({"status": "error", "error": str(error)[:500]}, ensure_ascii=False))
        finally:
            context.close()


if __name__ == "__main__":
    main()
