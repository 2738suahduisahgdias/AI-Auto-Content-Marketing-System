import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from playwright.sync_api import sync_playwright

from content_workbench.topics.browser_worker import open_context, visible_videos


def xhs_logged_in(context):
    names = {cookie["name"] for cookie in context.cookies("https://creator.xiaohongshu.com")}
    return bool(names & {"web_session", "webId", "a1", "web_sessionid"})


def xhs_notes(page):
    page.goto("https://creator.xiaohongshu.com/new/note-manager", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)
    if "login" in page.url:
        return {"status": "login_required"}
    items = page.evaluate("""() => {
      const result=[];const seen=new Set();
      for(const a of document.querySelectorAll('a[href]')){
        const href=a.href;
        if(!/explore|note-manager|notes|note_detail/.test(href))continue;
        const text=(a.innerText||'').trim();if(!text||seen.has(href))continue;
        const title=text.split('\\n').map(x=>x.trim()).filter(x=>x.length>1).sort((a,b)=>b.length-a.length)[0];
        if(!title)continue;
        const image=a.querySelector('img')?.src||a.parentElement?.querySelector('img')?.src||'';
        const metrics=text.match(/\\d+(?:\\.\\d+)?[万wW]?/g)||[];
        seen.add(href);result.push({title,canonical_url:href,metadata:{title,cover_url:image,visible_metrics:metrics,visible_text:text.slice(0,1000)}});
        if(result.length>=50)break;
      }
      return result;
    }""")
    return {"status": "ok", "items": items}


def douyin_account(page):
    page.goto("https://www.douyin.com/user/self", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3500)
    body = page.locator("body").inner_text()
    def match(pattern):
        found = re.search(pattern, body)
        return found.group(1) if found else None
    profile = {"account_name": match(r"抖音号：([^\n]+)"), "fans": match(r"粉丝\s*(\d+(?:\.\d+)?[万wW]?)"),
               "likes": match(r"获赞\s*(\d+(?:\.\d+)?[万wW]?)"), "works_count": match(r"作品\s*(\d+)") }
    items = visible_videos(page, 20)
    return {"status": "ok", "profile": profile, "items": items}


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("xhs_notes", "douyin_account", "publish_preview", "xiaohongshu_login", "douyin_publish_login"), required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--video")
    parser.add_argument("--title", default="")
    parser.add_argument("--description", default="")
    args = parser.parse_args()
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
            elif args.action in ("xiaohongshu_login", "douyin_publish_login"):
                url = "https://creator.xiaohongshu.com/" if args.action == "xiaohongshu_login" else "https://creator.douyin.com/creator-micro/content/upload"
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(300000)
                print(json.dumps({"status": "browser_closed", "login_verified": False, "next_action": "返回工作台重新同步或创建发布预览"}, ensure_ascii=False))
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
