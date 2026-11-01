import ipaddress
import json
import re
import socket
from html import unescape

PLATFORM_LABELS = {"douyin": "抖音", "xiaohongshu": "小红书", "wechat_channels": "视频号",
                   "wechat_official_account": "公众号", "bilibili": "B站", "weibo": "微博", "generic": "网页"}


def detect_platform(url):
    host = (urlsplit(url).hostname or "").lower()
    for domain, platform in (("douyin.com", "douyin"), ("iesdouyin.com", "douyin"), ("xiaohongshu.com", "xiaohongshu"),
                             ("xhslink.com", "xiaohongshu"), ("channels.weixin.qq.com", "wechat_channels"),
                             ("mp.weixin.qq.com", "wechat_official_account"), ("bilibili.com", "bilibili"),
                             ("b23.tv", "bilibili"), ("weibo.com", "weibo"), ("weibo.cn", "weibo")):
        if host == domain or host.endswith("." + domain):
            return platform
    return "generic"


def embedded_author(html, platform):
    if platform in ("douyin", "xiaohongshu", "wechat_channels"):
        match = re.search(r'"nick(?:N|n)ame"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', html)
        if match:
            try:
                return json.loads('"' + match.group(1) + '"')
            except json.JSONDecodeError:
                return match.group(1)
    if platform == "wechat_official_account":
        match = re.search(r"var\s+nickname\s*=\s*['\"]([^'\"]+)['\"]", html)
        return match.group(1) if match else None
    return None


def json_value(value, key):
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            found = json_value(child, key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = json_value(child, key)
            if found is not None:
                return found
    return None


def author_name(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("name") or value.get("nickname")
    if isinstance(value, list) and value:
        return author_name(value[0])
    return None


from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import utcnow

MAX_HTML = 2 * 1024 * 1024


class MetadataParser(HTMLParser):
    def __init__(self, source_url):
        super().__init__(convert_charrefs=True)
        self.source_url = source_url
        self.meta = {}
        self.title = []
        self.text = []
        self.json_ld = []
        self.in_title = False
        self.in_json_ld = False
        self.ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        values = {key.lower(): value for key, value in attrs}
        if tag == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            content = values.get("content") or ""
            if key and content:
                self.meta[key] = unescape(content).strip()
        elif tag == "title":
            self.in_title = True
        elif tag == "script" and values.get("type") == "application/ld+json":
            self.in_json_ld = True
            self.json_ld.append("")
        elif tag in ("script", "style", "noscript", "svg"):
            self.ignored_depth += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "script" and self.in_json_ld:
            self.in_json_ld = False
        elif tag in ("script", "style", "noscript", "svg") and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if self.in_json_ld:
            self.json_ld[-1] += data
        elif not self.ignored_depth and not self.in_title and data.strip():
            self.text.append(data.strip())


def validate_public_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise DomainError("SNAPSHOT_URL_INVALID", "链接协议或主机无效", 422, "original_url", "只解析公开 HTTP(S) 页面")
    if parsed.port not in (None, 80, 443):
        raise DomainError("SNAPSHOT_URL_INVALID", "链接端口不在允许范围", 422, "original_url", "使用默认 80 或 443 端口")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as error:
        raise DomainError("SNAPSHOT_DNS_FAILED", "无法解析链接主机：" + str(error)[:200], 502, "original_url", "检查链接域名是否正确")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise DomainError("SNAPSHOT_PRIVATE_URL_BLOCKED", "禁止解析本机或内网地址", 403, "original_url", "只使用公开互联网链接")


class SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def parse_html(html, source_url):
    parser = MetadataParser(source_url)
    parser.feed(html)
    documents = []
    for raw in parser.json_ld:
        try:
            documents.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    platform = detect_platform(source_url)
    title = parser.meta.get("og:title") or next((json_value(document, "headline") for document in documents if json_value(document, "headline")), None) or " ".join(parser.title).strip()
    description = parser.meta.get("og:description") or parser.meta.get("description") or next((json_value(document, "description") for document in documents if json_value(document, "description")), "")
    canonical = parser.meta.get("og:url") or source_url
    site_name = parser.meta.get("og:site_name") or urlsplit(canonical).hostname or ""
    cover = parser.meta.get("og:image") or parser.meta.get("twitter:image") or next((json_value(document, "image") for document in documents if json_value(document, "image")), "")
    if isinstance(cover, dict):
        cover = cover.get("url") or cover.get("contentUrl") or ""
    if isinstance(cover, list):
        cover = cover[0] if cover else ""
    author = parser.meta.get("article:author") or parser.meta.get("og:video:actor") or parser.meta.get("author") or parser.meta.get("twitter:creator")
    if not author:
        author = next((author_name(json_value(document, "author")) for document in documents if json_value(document, "author")), None)
    author = author or embedded_author(html, platform)
    published_at = parser.meta.get("article:published_time") or next((json_value(document, "datePublished") or json_value(document, "uploadDate") for document in documents), None)
    excerpt = " ".join(" ".join(parser.text).split())[:1200]
    return {"title": title[:500] or None, "description": description[:1200] or None,
            "site_name": site_name[:200] or None, "cover_url": urljoin(canonical, cover) if cover else None,
            "canonical_url": canonical, "source_url": source_url, "excerpt": excerpt or None,
            "platform": platform, "platform_label": PLATFORM_LABELS[platform], "author": author,
            "author_followers": None, "published_at": published_at,
            "captured_at": utcnow(), "parser": "public_html_og_v2", "limited": not bool(title or description or excerpt),
            "dynamic_attempted": False, "dynamic_error": None}


def fetch_public_snapshot(url):
    validate_public_url(url)
    request = Request(url, headers={"User-Agent": "ContentTopicInbox/1.0 (+public metadata only)",
                                    "Accept": "text/html,application/xhtml+xml"})
    try:
        with build_opener(SafeRedirectHandler()).open(request, timeout=15) as response:
            content_type = response.headers.get_content_type()
            if content_type not in ("text/html", "application/xhtml+xml"):
                raise DomainError("SNAPSHOT_UNSUPPORTED", "链接不是可解析的公开 HTML 页面", 415, "original_url", "保留原链接，不上传非 HTML 文件进行冒充解析")
            body = response.read(MAX_HTML + 1)
            charset = response.headers.get_content_charset() or "utf-8"
            final_url = response.url
    except DomainError:
        raise
    except Exception as error:
        raise DomainError("SNAPSHOT_FETCH_FAILED", "公开页面读取失败：" + str(error)[:300], 502, "original_url",
                          "检查链接是否公开可访问；不自动重试，可稍后手动重新解析")
    result = parse_html(body.decode(charset, errors="replace"), final_url)
    result["truncated"] = len(body) > MAX_HTML
    return result
