#!/usr/bin/env python3
"""Image acquisition uses explicit queries/prompts; project files stay local."""

import html
import json
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from content_workbench.agents.registry import require_agent_enabled
from content_workbench.domain.errors import DomainError
from content_workbench.providers.system import provider_for
from content_workbench.storage.db import PROJECT_ROOT

API = "https://commons.wikimedia.org/w/api.php"
UA = "YingxuLocalWorkbench/1.0 (local editorial image search)"
MAX_IMAGE = 20 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DomainError("IMAGE_REDIRECT", "图片服务发生重定向，请检查服务地址", 502)


def request_bytes(url, data=None, headers=None, limit=MAX_IMAGE, timeout=45):
    request = urllib.request.Request(
        url, data=data, headers={"User-Agent": UA, **(headers or {})}
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(
            request, timeout=timeout
        ) as response:
            value = response.read(limit + 1)
            if len(value) > limit:
                raise DomainError("IMAGE_TOO_LARGE", "图片服务返回内容过大", 422)
            return value
    except urllib.error.HTTPError as error:
        raise DomainError(
            "IMAGE_SERVICE_HTTP",
            f"图片服务返回 HTTP {error.code}",
            502,
            action="检查素材源与网络连接；请求没有自动重试",
        )
    except (urllib.error.URLError, TimeoutError):
        raise DomainError(
            "IMAGE_SERVICE_UNAVAILABLE",
            "无法连接图片服务或请求超时",
            502,
            action="检查网络后重试素材搜索或下载",
        )


def commons(params):
    url = (
        API
        + "?"
        + urllib.parse.urlencode({"action": "query", "format": "json", **params})
    )
    try:
        data = json.loads(request_bytes(url, limit=2 * 1024 * 1024))
        if "error" in data:
            raise ValueError()
        return list(data.get("query", {}).get("pages", {}).values())
    except (ValueError, TypeError):
        raise DomainError("IMAGE_SEARCH_PROTOCOL", "素材源返回无效数据", 502)


def clean(value):
    return html.unescape(re.sub("<[^>]+>", "", str(value or ""))).strip()


def candidate(page):
    info = (page.get("imageinfo") or [{}])[0]
    if info.get("mime") not in ("image/png", "image/jpeg", "image/webp"):
        return None
    meta = info.get("extmetadata", {})
    return {
        "title": page["title"],
        "url": info.get("url"),
        "preview_url": info.get("thumburl") or info.get("url"),
        "source_url": info.get("descriptionurl"),
        "mime_type": info["mime"],
        "author": clean(meta.get("Artist", {}).get("value")),
        "license": clean(meta.get("LicenseShortName", {}).get("value")),
        "license_url": meta.get("LicenseUrl", {}).get("value", ""),
        "attribution": clean(meta.get("Credit", {}).get("value")),
    }


def search_images(query):
    query = str(query or "").strip()
    if not 1 <= len(query) <= 200:
        raise DomainError("IMAGE_QUERY_REQUIRED", "搜索词需为 1～200 字", 422)
    pages = commons(
        {
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": 12,
            "prop": "imageinfo",
            "iiprop": "url|mime|extmetadata",
            "iiurlwidth": 400,
        }
    )
    return {
        "items": [row for row in (candidate(p) for p in pages) if row],
        "provider": "Wikimedia Commons",
    }


def store_image(workbench, data, source, rights="research_only"):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        suffix = ".png"
    elif data.startswith(b"\xff\xd8\xff"):
        suffix = ".jpg"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        suffix = ".webp"
    else:
        raise DomainError(
            "IMAGE_FORMAT_INVALID", "图片服务没有返回 PNG、JPEG 或 WebP", 502
        )
    if len(data) > MAX_IMAGE:
        raise DomainError("IMAGE_TOO_LARGE", "图片超过 20 MB", 422)
    with tempfile.TemporaryDirectory(prefix="yingxu-image-", dir=workbench.root) as tmp:
        path = Path(tmp) / ("image" + suffix)
        path.write_bytes(data)
        asset_id = workbench.register_asset(path, source, rights)
    return {"asset_id": asset_id, "source": source}


def adopt_image(workbench, title):
    if not isinstance(title, str) or not title.startswith("File:") or len(title) > 500:
        raise DomainError("IMAGE_CANDIDATE_INVALID", "请选择搜索结果中的图片", 422)
    pages = commons(
        {"titles": title, "prop": "imageinfo", "iiprop": "url|mime|extmetadata"}
    )
    item = candidate(pages[0]) if pages else None
    if not item:
        raise DomainError("IMAGE_CANDIDATE_MISSING", "素材源中已找不到这张图片", 404)
    url = urllib.parse.urlsplit(item["url"])
    if (
        url.scheme != "https"
        or url.hostname != "upload.wikimedia.org"
        or url.port not in (None, 443)
    ):
        raise DomainError("IMAGE_HOST_INVALID", "素材下载地址不属于已配置的素材源", 422)
    return store_image(
        workbench,
        request_bytes(item["url"]),
        {"kind": "image_search", "provider": "Wikimedia Commons", **item},
    )


def image_config(root, public=False):
    from content_workbench.agents.registry import agent_config
    from content_workbench.providers.system import model_settings
    from content_workbench.providers.text import discover_cli

    db_path = Path(root) / "data/content-agent.db"
    config = agent_config(db_path, "article_image_agent")
    engine = config["engine"]
    if engine == "model_api":
        settings = model_settings(db_path)
        configured = bool(settings.get("base_url") and settings.get("model"))
    else:
        configured = bool(discover_cli("kimi" if engine == "kimi_cli" else "codex"))
    return {
        "engine": engine,
        "configured": configured,
        "model": config["model"],
        "authentication": "在 Agent 配置中心独立选择；本地渲染由客户端完成",
    }


def validate_svg(value):
    from xml.etree import ElementTree

    text = value.strip()
    if text.startswith("```") and text.endswith("```"):
        text = "\n".join(text.splitlines()[1:-1]).strip()
    if not text or len(text.encode("utf-8")) > 512 * 1024:
        raise DomainError("IMAGE_SVG_INVALID", "Kimi 返回的矢量插画为空或过大", 502)
    allowed = {
        "svg",
        "g",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "path",
        "text",
        "tspan",
        "defs",
        "linearGradient",
        "radialGradient",
        "stop",
        "filter",
        "feGaussianBlur",
    }
    try:
        root = ElementTree.fromstring(text)
        for element in root.iter():
            tag = element.tag.rsplit("}", 1)[-1]
            if tag not in allowed:
                raise DomainError(
                    "IMAGE_SVG_INVALID", "矢量插画包含不允许的元素 " + tag, 502
                )
            for key, attribute in element.attrib.items():
                name = key.rsplit("}", 1)[-1].lower()
                normalized = attribute.strip().lower().replace(" ", "")
                if name != "xmlns" and any(
                    value in normalized
                    for value in (
                        "javascript:",
                        "http://",
                        "https://",
                        "data:",
                        "expression(",
                    )
                ):
                    raise DomainError(
                        "IMAGE_SVG_INVALID", "矢量插画包含脚本或外部资源", 502
                    )
                if name.startswith("on") or name in ("href", "src"):
                    raise DomainError(
                        "IMAGE_SVG_INVALID", "矢量插画包含脚本或外部资源", 502
                    )
                if "url(" in normalized and "url(#" not in normalized:
                    raise DomainError(
                        "IMAGE_SVG_INVALID", "矢量插画包含外部样式引用", 502
                    )
        if root.tag.rsplit("}", 1)[-1] != "svg":
            raise DomainError("IMAGE_SVG_INVALID", "Kimi 必须返回 SVG 根元素", 502)
    except ElementTree.ParseError:
        raise DomainError(
            "IMAGE_SVG_INVALID", "Kimi 返回的 SVG 格式无效", 502
        ) from None
    return text


def generate_image(workbench, job, context):
    import shutil

    prompt = str(job["input"].get("prompt") or "").strip()
    if not 1 <= len(prompt) <= 8000:
        raise DomainError("IMAGE_PROMPT_REQUIRED", "生图提示词需为 1～8000 字", 422)
    config = require_agent_enabled(workbench.db_path, "article_image_agent")
    context.progress("image_generate", 0.1)
    svg = validate_svg(
        provider_for(workbench.root, config["engine"]).complete_text(
            prompt,
            context,
            PROJECT_ROOT / "agents/article-image-agent.md",
            timeout=config["timeout_seconds"],
            stage="image_generate",
            model=config["model"],
        )
    )
    node = shutil.which("node")
    if not node:
        raise DomainError("NODE_NOT_FOUND", "缺少本地 Node.js，无法渲染文章插画", 503)
    generated = PROJECT_ROOT / "remotion-app/generated"
    generated.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="article-image-", dir=generated
    ) as directory:
        root = Path(directory)
        output = root / "image.png"
        entry = root / "index.tsx"
        props = root / "props.json"
        entry.write_text(
            "import React from 'react';\nimport {Composition,registerRoot} from 'remotion';\n"
            "const Art=()=> <div style={{width:'1200px',height:'1200px',overflow:'hidden'}} dangerouslySetInnerHTML={{__html:"
            + json.dumps(svg, ensure_ascii=False)
            + "}}/>;\n"
            'const Root=()=> <Composition id="ArticleImage" component={Art} width={1200} height={1200} fps={30} durationInFrames={46}/>;\n'
            "registerRoot(Root);\n",
            encoding="utf-8",
        )
        props.write_text("{}", encoding="utf-8")
        context.run_process(
            [
                node,
                "scripts/render.mjs",
                "--props",
                str(props),
                "--output",
                str(output),
                "--composition-id",
                "ArticleImage",
                "--entry",
                str(entry),
            ],
            timeout=600,
            stage="kimi_image_render",
            cwd=PROJECT_ROOT / "remotion-app",
        )
        data = output.read_bytes()
    return store_image(
        workbench,
        data,
        {
            "kind": "image_generation",
            "provider": config["engine"],
            "model": config["model"],
            "renderer": "remotion_still",
            "prompt": prompt,
            "job_id": job["id"],
        },
        "generated",
    )
