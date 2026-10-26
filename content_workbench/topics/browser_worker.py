import argparse
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HOT_URL = "https://www.douyin.com/hot"
PROFILE_URL = "https://www.douyin.com/user/self?showSubTab=favorite_folder&showTab=favorite_collection"
VIDEO_LINK = r"/(?:video|note)/"


def public_items(page, limit=20):
    return page.evaluate("""({limit}) => {
      const result=[]; const seen=new Set();
      for (const heading of document.querySelectorAll('h3')) {
        const a=heading.closest('a[href*="/hot/"]');
        if (!a) continue;
        const title=(heading.innerText||'').trim();
        if (!title || title==='抖音热榜' || seen.has(title)) continue;
        seen.add(title);
        const href=a.href;
        const container=(a.parentElement?.parentElement?.innerText||a.parentElement?.innerText||'');
        const heat=(container.match(/\\d+(?:\\.\\d+)?万(?=\\s*热度)/)||[])[0]||'';
        result.push({title,canonical_url:href,heat,metadata:{title,heat}});
        if (result.length>=limit) break;
      }
      return result;
    }""", {"limit": limit})


def visible_videos(page, limit=100):
    return page.evaluate("""({limit}) => {
      const result=[]; const seen=new Set();
      for (const a of document.querySelectorAll('a[href*="/video/"]:has(img),a[href*="/note/"]:has(img)')) {
        const href=a.href; if (seen.has(href)) continue;
        const box=(a.innerText||a.closest('li')?.innerText||'').trim();
        const lines=box.split('\\n').map(x=>x.trim()).filter(Boolean);
        const title=lines.filter(x=>x.length>1 && !/^\\d+(\\.\\d+)?[万wW]?$/.test(x)).sort((a,b)=>b.length-a.length)[0]||'未读取标题';
        const match=href.match(/(?:video|note)\\/([0-9A-Za-z_-]+)/);
        const like_count=lines.find(x=>/^\\d+(\\.\\d+)?[万wW]?$/.test(x))||'';
        const cover_url=a.querySelector('img')?.src||'';
        seen.add(href); result.push({title,canonical_url:href,platform_item_id:match?match[1]:null,metadata:{title,visible_text:box.slice(0,1000),cover_url,like_count}});
        if (result.length>=limit) break;
      }
      return result;
    }""", {"limit": limit})


def logged_in(context):
    names = {cookie["name"] for cookie in context.cookies("https://www.douyin.com")}
    return bool(names & {"sessionid", "sessionid_ss", "sid_guard", "uid_tt"})


def open_context(playwright, profile):
    return playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile), channel="chrome", headless=False,
        viewport={"width": 1440, "height": 960}, accept_downloads=True,
    )


def sync_hot(page):
    page.goto(HOT_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector('a[href*="/hot/"] h3', timeout=45000)
    items = public_items(page, 20)
    if not items:
        raise RuntimeError("HOT_STRUCTURE_CHANGED:热榜已打开，但未解析到有效条目")
    for index, item in enumerate(items, 1):
        item["rank"] = index
        item["metadata"]["rank"] = index
    return items


def sync_collection(page, title):
    page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
    page.get_by_text("收藏夹", exact=True).first.wait_for(timeout=45000)
    target = page.get_by_text(title, exact=True).first
    try:
        target.wait_for(timeout=45000)
    except Exception:
        raise RuntimeError("COLLECTION_NOT_FOUND:" + title)
    target.scroll_into_view_if_needed()
    target.click(timeout=15000)
    page.wait_for_timeout(3000)
    collected = {}
    quiet = 0
    while len(collected) < 100 and quiet < 5:
        for item in visible_videos(page):
            collected[item["canonical_url"]] = item
        previous = len(collected)
        page.mouse.wheel(0, 1800)
        page.wait_for_timeout(1800)
        for item in visible_videos(page):
            collected[item["canonical_url"]] = item
        quiet = quiet + 1 if len(collected) == previous else 0
    return list(collected.values())


def download_video(context, page, url, output):
    network_candidates = []
    def capture_response(response):
        if "douyinvod" in response.url and response.headers.get("content-type", "").startswith("video/"):
            network_candidates.append(response.url)
    page.on("response", capture_response)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("video", timeout=30000)
    page.wait_for_timeout(5000)
    candidates = page.evaluate("""() => {
      const urls=[];
      for (const el of document.querySelectorAll('video,video source')) if (el.src) urls.push(el.src);
      for (const entry of performance.getEntriesByType('resource')) {
        const url=entry.name;
        if (/\\.mp4|play.*video|video.*play/.test(url) && !url.includes('log') && !url.includes('report')) urls.push(url);
      }
      return [...new Set(urls)].filter(x=>x.startsWith('https://'));
    }""")
    candidates.extend(network_candidates)
    candidates = list(dict.fromkeys(candidates))
    if not candidates:
        try:
            page.locator("video").first.click(timeout=3000)
            page.wait_for_timeout(3000)
            candidates = page.evaluate("() => [...document.querySelectorAll('video,video source')].map(x=>x.src).filter(Boolean)")
        except Exception:
            pass
    for candidate in candidates:
        if not candidate.startswith("https://") or "douyinstatic.com" in candidate:
            continue
        try:
            response = context.request.get(candidate, headers={"Referer": page.url, "Accept": "video/*,*/*"}, timeout=90000)
            if not response.ok:
                continue
            body = response.body()
            if body.startswith(b"{") and b"play_addr" in body:
                payload = json.loads(body)
                play = payload.get("play_addr") or payload.get("data", {}).get("play_addr") or {}
                urls = play.get("url_list") or play.get("urlList") or []
                if urls:
                    response = context.request.get(urls[0], headers={"Referer": page.url, "Accept": "video/*,*/*"}, timeout=90000)
                    body = response.body() if response.ok else b""
            if len(body) < 1000 or len(body) > 500 * 1024 * 1024 or body.startswith(b"{"):
                continue
            output.write_bytes(body)
            return {"downloaded": len(body)}
        except Exception:
            continue
    return {"needs_upload": True, "candidate_count": len(candidates)}


def video_details(context, page, url, cover_url, output):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("body", timeout=30000)
    page.wait_for_timeout(2500)
    details = page.evaluate("""() => {
      const links=[...document.querySelectorAll('a[href*="/user/"]')];
      const author=links.find(a=>(a.innerText||'').trim() && (a.innerText||'').trim()!=='我的');
      const body=document.body.innerText;
      const followers=(body.match(/粉丝\\s*([0-9.]+[万亿]?)/)||[])[1]||'';
      return {author_name:author?(author.innerText||'').trim():'',author_url:author?author.href:'',author_followers:followers};
    }""")
    if output and cover_url:
        try:
            response = context.request.get(cover_url, headers={"Referer": page.url}, timeout=30000)
            if response.ok:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(response.body())
                details["cover_cached"] = True
        except Exception:
            details["cover_cached"] = False
    return details


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("hot", "favorites", "login", "download", "details"), required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--collection")
    parser.add_argument("--url")
    parser.add_argument("--cover-url")
    parser.add_argument("--output")
    parser.add_argument("--wait-seconds", type=int, default=30)
    args = parser.parse_args()
    with sync_playwright() as playwright:
        context = open_context(playwright, Path(args.profile).resolve())
        try:
            page = context.pages[0] if context.pages else context.new_page()
            if args.action == "hot":
                print(json.dumps({"status": "ok", "items": sync_hot(page)}, ensure_ascii=False))
                return
            if args.action == "login":
                page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
                deadline = time.monotonic() + args.wait_seconds
                while time.monotonic() < deadline:
                    if logged_in(context):
                        print(json.dumps({"status": "ready"}, ensure_ascii=False))
                        return
                    page.wait_for_timeout(2000)
                print(json.dumps({"status": "login_required", "action": "在专用采集窗口完成登录后重试"}, ensure_ascii=False))
                return
            if args.action == "favorites" and not logged_in(context):
                print(json.dumps({"status": "login_required", "action": "先点击“连接采集窗口”完成抖音登录"}, ensure_ascii=False))
                return
            if args.action == "favorites":
                print(json.dumps({"status": "ok", "items": sync_collection(page, args.collection)}, ensure_ascii=False))
                return
            if args.action == "details":
                print(json.dumps({"status": "ok", "details": video_details(context, page, args.url, args.cover_url, Path(args.output).resolve() if args.output else None)}, ensure_ascii=False))
                return
            result = download_video(context, page, args.url, Path(args.output).resolve())
            print(json.dumps({"status": "ok", **result}, ensure_ascii=False))
        except Exception as error:
            message = str(error)[:500]
            print(json.dumps({"status": "error", "error": message}, ensure_ascii=False))
        finally:
            context.close()


if __name__ == "__main__":
    main()
