import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from playwright.sync_api import sync_playwright
from content_workbench.topics.browser_worker import open_context

ROOT = Path(__file__).resolve().parents[2]
URLS = {
    "douyin": "https://creator.douyin.com/creator-micro/content/upload",
    "xiaohongshu": "https://creator.xiaohongshu.com/publish/publish?source=official",
    "wechat_channels": "https://channels.weixin.qq.com/platform/post/list",
    "wechat_official_account": "https://mp.weixin.qq.com/",
}


def first(page, selectors, timeout=0):
    deadline = time.monotonic() + timeout / 1000
    while True:
        for selector in selectors:
            locator = page.locator(selector)
            for index in range(locator.count()):
                candidate = locator.nth(index)
                try:
                    if "input[type=file]" in selector or candidate.is_visible():
                        return candidate
                except Exception:
                    continue
        if time.monotonic() >= deadline:
            return None
        page.wait_for_timeout(250)


def value_of(locator):
    try:
        return locator.input_value()
    except Exception:
        try:
            return locator.inner_text()
        except Exception:
            return ""


def fill(locator, text):
    locator.click()
    try:
        locator.fill(text)
    except Exception:
        locator.press("ControlOrMeta+a")
        locator.type(text)
    return value_of(locator)


def click_visible(locator, timeout=0):
    deadline = time.monotonic() + timeout / 1000
    while True:
        for index in range(locator.count()):
            candidate = locator.nth(index)
            if not candidate.is_visible() or not candidate.is_enabled():
                continue
            try:
                candidate.click()
                return True
            except Exception:
                try:
                    candidate.locator("xpath=..").click()
                    return True
                except Exception:
                    continue
        if time.monotonic() >= deadline:
            return False
        locator.page.wait_for_timeout(250)


def visible_text(page, text, timeout=0):
    deadline = time.monotonic() + timeout / 1000
    while True:
        for frame in page.frames:
            locator = frame.get_by_text(text, exact=True)
            for index in range(locator.count()):
                candidate = locator.nth(index)
                try:
                    if candidate.is_visible():
                        return candidate
                except Exception:
                    continue
        if time.monotonic() >= deadline:
            return None
        page.wait_for_timeout(250)


def xhs_publish_control(page):
    draft = visible_text(page, "暂存离开")
    if draft:
        candidate = draft.locator("xpath=following-sibling::*[1]")
        if candidate.count() and candidate.first.is_visible() and "下一步" not in value_of(candidate.first):
            return candidate.first
    return visible_text(page, "发布")


def field_error(platform, field, message):
    return {"status": "error", "field": field, "error": message}


def evidence(page, target_id, mode, fields, extra=None):
    directory = ROOT / "data/publishing-evidence"
    directory.mkdir(parents=True, exist_ok=True)
    name = "{}_{}_{}.png".format(target_id or "connection", mode, datetime.now().strftime("%Y%m%dT%H%M%S"))
    path = directory / name
    try:
        page.screenshot(path=str(path), full_page=False)
    except Exception:
        pass
    result = {"status": "preview_ready", "fields_verified": sorted(fields), "screenshot": str(path.relative_to(ROOT)), "auto_published": False}
    if extra:
        result.update(extra)
    return result


def prepare_douyin(page, data, mode):
    source, payload = data["source"], data["payload"]
    page.goto(URLS["douyin"], wait_until="domcontentloaded", timeout=60000)
    upload = first(page, ["input[type=file]"], 15000)
    if not upload:
        return {"status": "login_required", "error": "未检测到视频上传控件，请登录抖音创作者后台"}
    upload.set_input_files(source["absolute_video_path"])
    deadline = time.monotonic() + 180
    while True:
        page_text = page.locator("body").inner_text()
        if "取消上传" not in page_text and "上传过程中请不要删除" not in page_text:
            break
        if time.monotonic() >= deadline:
            return field_error("douyin", "video_path", "视频上传尚未完成，请检查网络后重试，不要提前发布")
        page.wait_for_timeout(1000)
    page.wait_for_timeout(3000)
    title = first(page, ['input[placeholder*="标题"]', 'textarea[placeholder*="标题"]', 'input[placeholder*="作品"]'])
    description = first(page, ['textarea[placeholder*="描述"]', 'textarea[placeholder*="简介"]', 'div[contenteditable="true"]', 'textarea'])
    if not description:
        return field_error("douyin", "description", "视频已选择，但未找到简介编辑区；请检查上传是否完成或页面是否变化")
    fields = set()
    if title:
        fill(title, payload["title"])
        fields.add("title")
        fill(description, payload["description"])
        fields.add("description")
    else:
        combined = payload["title"] + "\n" + payload["description"]
        fill(description, combined)
        fields.update(("title", "description", "combined_caption"))
    readback = value_of(description)
    if payload["description"][:30] not in readback:
        return field_error("douyin", "description", "简介写入后读回不一致")
    if mode == "execute":
        return click_publish(page, "douyin", data["target_id"])
    return evidence(page, data["target_id"], mode, fields, {"title": payload["title"]})


def xhs_editor(page):
    page.goto(URLS["xiaohongshu"], wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    if "login" in page.url:
        return None
    return page


def prepare_xhs_video(page, data, mode):
    source, payload = data["source"], data["payload"]
    if not xhs_editor(page):
        return {"status": "login_required", "error": "小红书创作者后台需要登录"}
    upload = first(page, ["input[type=file]"], 15000)
    if not upload:
        return {"status": "login_required", "error": "未检测到小红书视频上传控件，请确认登录状态"}
    upload.set_input_files(source["absolute_video_path"])
    page.wait_for_timeout(7000)
    title = first(page, ['input[placeholder*="标题"]', 'textarea[placeholder*="标题"]'])
    body = first(page, ['div[contenteditable="true"]', 'textarea[placeholder*="正文"]', 'textarea[placeholder*="描述"]', 'textarea'])
    if not title:
        return field_error("xiaohongshu", "title", "视频上传后未找到标题输入框")
    if not body:
        return field_error("xiaohongshu", "description", "视频上传后未找到正文编辑区")
    fill(title, payload["title"])
    fill(body, payload["description"])
    if payload["title"] not in value_of(title) or payload["description"][:30] not in value_of(body):
        return field_error("xiaohongshu", "description", "标题或正文读回不一致")
    if mode == "execute":
        return click_publish(page, "xiaohongshu", data["target_id"])
    return evidence(page, data["target_id"], mode, {"title", "description"}, {"title": payload["title"]})


def prepare_xhs_article(page, data, mode):
    payload = data["payload"]
    if not xhs_editor(page):
        return {"status": "login_required", "error": "小红书创作者后台需要登录"}
    if not click_visible(page.get_by_text("写长文", exact=True), 15000):
        return field_error("xiaohongshu", "long_article", "长文入口加载超时或被遮挡，请检查平台页面")
    if not click_visible(page.get_by_role("button", name="新的创作", exact=True), 15000):
        return field_error("xiaohongshu", "long_article", "未找到新的创作按钮")
    title = first(page, ['input[placeholder="输入标题"]', 'textarea[placeholder="输入标题"]'], 15000)
    body = first(page, ['div[contenteditable="true"]', 'textarea'])
    if not title or not body:
        return field_error("xiaohongshu", "body", "未找到长文标题或正文编辑器")
    fill(title, payload["title"])
    fill(body, payload["body"])
    if payload["title"] not in value_of(title) or payload["body"][:30] not in value_of(body):
        return field_error("xiaohongshu", "body", "长文标题或正文读回不一致")
    fields = {"title", "body", "long_article"}
    layout = page.get_by_role("button", name="一键排版", exact=True)
    if layout.count() and click_visible(layout):
        page.wait_for_timeout(3000)
        click_visible(page.get_by_role("button", name=re.compile("确定|完成|应用")))
        page.wait_for_timeout(1500)
        fields.add("layout")
    if visible_text(page, "选择模板"):
        if not click_visible(page.get_by_text("理性现代", exact=True), 5000):
            return field_error("xiaohongshu", "layout", "长文模板未选择，无法进入下一步")
        page.wait_for_timeout(1000)
        fields.add("template")
    next_button = page.get_by_text(re.compile("^下一步(?:设置)?$"))
    for _ in range(4):
        if xhs_publish_control(page) or not click_visible(next_button):
            break
        page.wait_for_timeout(2000)
        fields.add("publish_settings")
    click_visible(page.get_by_role("button", name="我知道了", exact=True), 3000)
    try:
        page.get_by_text(re.compile("笔记图片生成中")).wait_for(state="hidden", timeout=60000)
    except Exception:
        return field_error("xiaohongshu", "cover", "长文笔记图片仍在生成，请稍后重试，不要跳过图片检查")
    if not xhs_publish_control(page):
        return field_error("xiaohongshu", "publish_settings", "尚未进入可发布设置页，未找到发布按钮")
    fields.add("publish_button")
    if mode == "execute":
        return click_publish(page, "xiaohongshu", data["target_id"])
    return evidence(page, data["target_id"], mode, fields,
                    {"title": payload["title"], "body_length": len(payload["body"]), "settings_text": page.locator("body").inner_text()[-2500:]})


def prepare_wechat_article(page, data, mode):
    payload = data["payload"]
    page.goto(URLS["wechat_official_account"], wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    body_text = page.locator("body").inner_text()
    if "login" in page.url or ("使用账号登录" in body_text and "新的创作" not in body_text):
        return {"status": "login_required", "error": "公众号后台需要登录，请在专用窗口扫码"}
    article = page.get_by_text("文章", exact=True).first
    article.click()
    title = first(page, ["#title", 'input[placeholder*="标题"]'], 20000)
    if not title:
        return field_error("wechat_official_account", "title", "未进入公众号文章编辑器，未找到标题")
    author = first(page, ["#author", 'input[placeholder="请输入作者"]'])
    summary = first(page, ["#digest", 'textarea[placeholder*="摘要会在"]'])
    fill(title, payload["title"])
    if author and payload.get("author"):
        fill(author, payload["author"])
    if summary and payload.get("summary"):
        fill(summary, payload["summary"])
    body = None
    frames = page.locator("iframe")
    for index in range(frames.count()):
        try:
            candidate = frames.nth(index).content_frame.locator("body")
            if candidate.count():
                body = candidate
                break
        except Exception:
            continue
    if body is None:
        body = first(page, ['div[contenteditable="true"]'])
    if body is None:
        return field_error("wechat_official_account", "body", "未找到公众号正文编辑区")
    fill(body, payload["body"])
    cover = page.get_by_text("拖拽或选择封面", exact=True).first
    cover.click()
    upload = first(page, ["input[type=file]"], 10000)
    if not upload:
        return field_error("wechat_official_account", "cover_asset_id", "封面选择器已打开，但没有找到图片上传控件")
    upload.set_input_files(payload["cover_path"])
    page.wait_for_timeout(2500)
    confirm = page.get_by_role("button", name=re.compile("确定|完成|使用"))
    if confirm.count():
        confirm.last.click()
    page.wait_for_timeout(1500)
    if payload["title"] not in value_of(title):
        return field_error("wechat_official_account", "title", "公众号标题读回不一致")
    if mode == "execute":
        return click_publish(page, "wechat_official_account", data["target_id"])
    return evidence(page, data["target_id"], mode, {"title", "author", "summary", "body", "cover"},
                    {"title": payload["title"], "body_length": len(payload["body"])})


def click_publish(page, platform, target_id):
    click_visible(page.get_by_role("button", name="我知道了", exact=True), 3000)
    labels = ("发表",) if platform == "wechat_official_account" else ("发布", "发表")
    clicked = False
    if platform == "xiaohongshu":
        control = xhs_publish_control(page)
        if control and click_visible(control):
            clicked = True
    for label in labels if not clicked else ():
        buttons = page.get_by_text(label, exact=True)
        for index in range(buttons.count()):
            button = buttons.nth(index)
            try:
                if button.is_visible() and button.is_enabled():
                    button.click()
                    clicked = True
                    break
            except Exception:
                continue
        if clicked:
            break
    if not clicked:
        return field_error(platform, "publish_button", "没有找到可用的最终发表按钮，未执行发表")
    page.wait_for_timeout(2000)
    confirmations = page.get_by_role("button", name=re.compile("确定|确认发表|确认发布|继续发布"))
    for index in range(confirmations.count()):
        button = confirmations.nth(index)
        try:
            if button.is_visible() and button.is_enabled():
                button.click()
                break
        except Exception:
            continue
    page.wait_for_timeout(5000)
    success = page.get_by_text(re.compile("发布成功|发表成功|提交成功"))
    if success.count():
        return evidence(page, target_id, "published", {"published"}, {"status": "published", "published_evidence": success.first.inner_text()[:300], "url": None})
    return evidence(page, target_id, "unknown", set(), {"status": "unknown_remote", "error": "已执行点击，但未读到明确成功证据，请到平台后台核对"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("login", "prepare", "execute"), required=True)
    parser.add_argument("--platform", choices=tuple(URLS), required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--payload-file")
    args = parser.parse_args()
    with sync_playwright() as playwright:
        context = open_context(playwright, Path(args.profile).resolve())
        try:
            page = context.pages[0] if context.pages else context.new_page()
            if args.action == "login":
                page.goto(URLS[args.platform], wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(300000)
                result = {"status": "browser_closed", "login_verified": False, "next_action": "返回发布中心重新生成预览"}
            else:
                data = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
                if args.platform == "douyin":
                    result = prepare_douyin(page, data, args.action)
                elif args.platform == "xiaohongshu" and data["source"]["kind"] == "video":
                    result = prepare_xhs_video(page, data, args.action)
                elif args.platform == "xiaohongshu":
                    result = prepare_xhs_article(page, data, args.action)
                elif args.platform == "wechat_official_account":
                    result = prepare_wechat_article(page, data, args.action)
                else:
                    page.goto(URLS[args.platform], wait_until="domcontentloaded", timeout=60000)
                    result = {"status": "login_required"} if "login" in page.url else field_error(args.platform, "connector", "视频号字段尚未完成验证，未执行发布")
            if result.get("status") == "error":
                diagnostic = evidence(page, locals().get("data", {}).get("target_id"), "error", set())
                result["screenshot"] = diagnostic["screenshot"]
                result["page_text"] = page.locator("body").inner_text()[-2000:]
            print(json.dumps(result, ensure_ascii=False))
        except Exception as error:
            result = {"status": "error", "error": str(error)[:800]}
            try:
                diagnostic = evidence(page, locals().get("data", {}).get("target_id"), "error", set())
                result["screenshot"] = diagnostic["screenshot"]
                result["page_text"] = page.locator("body").inner_text()[-2000:]
            except Exception:
                pass
            print(json.dumps(result, ensure_ascii=False))
        finally:
            context.close()


if __name__ == "__main__":
    main()
