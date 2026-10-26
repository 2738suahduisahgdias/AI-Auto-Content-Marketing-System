import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def fetch_industry(scope, limit=20):
    query = urllib.parse.urlencode({"q": scope, "hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans"})
    url = "https://news.google.com/rss/search?" + query
    request = urllib.request.Request(url, headers={"User-Agent": "ContentWorkflowTopicResearch/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(2 * 1024 * 1024)
    root = ET.fromstring(body)
    items = []
    for node in root.findall(".//item")[:limit]:
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        if not title or not link.startswith(("http://", "https://")):
            continue
        items.append({"title": title, "canonical_url": link,
                      "published_at": node.findtext("pubDate") or "",
                      "metadata": {"title": title, "source_name": node.findtext("source") or "Google News RSS",
                                   "published_at": node.findtext("pubDate") or ""}})
    if not items:
        raise RuntimeError("行业公开资讯未返回有效条目，请调整行业范围或稍后重试")
    return items
