import csv
import json
import re
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from content_workbench.storage.db import PROJECT_ROOT

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def read_xlsx(path):
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(text.text or "" for text in item.iter("{%s}t" % MAIN)) for item in root]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.get("Id"): item.get("Target") for item in relationships}
        result = {}
        for sheet in workbook.find("{%s}sheets" % MAIN):
            target = targets[sheet.get("{%s}id" % REL)].lstrip("/")
            target = target if target.startswith("xl/") else "xl/" + target
            root = ET.fromstring(archive.read(target))
            rows = []
            for row in root.findall(".//{%s}sheetData/{%s}row" % (MAIN, MAIN)):
                values = []
                for cell in row.findall("{%s}c" % MAIN):
                    kind = cell.get("t")
                    value = cell.find("{%s}v" % MAIN)
                    inline = cell.find("{%s}is" % MAIN)
                    if inline is not None:
                        text = "".join(part.text or "" for part in inline.iter("{%s}t" % MAIN))
                    elif value is None:
                        text = ""
                    elif kind == "s":
                        text = shared[int(value.text)]
                    else:
                        text = value.text
                    values.append(text or "")
                rows.append(values)
            result[sheet.get("name")] = rows
        return result


def number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", "")
    if not text or text == "-":
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    value = float(match.group(0))
    return int(value) if value.is_integer() else value


def summary(path):
    rows = list(read_xlsx(path).values())[0]
    return {row[0]: number(row[1]) for row in rows[1:] if len(row) >= 2}


def table(path):
    rows = list(read_xlsx(path).values())[0]
    if not rows:
        return []
    return [dict(zip(rows[0], row)) for row in rows[1:]]


def total(rows, key):
    values = [number(row.get(key)) for row in rows]
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def trend(path):
    result = {}
    for name, rows in list(read_xlsx(path).items())[1:]:
        result[name] = [{"date": row[0], "value": number(row[1])} for row in rows[1:] if len(row) >= 2]
    return result


def read_xls(path):
    python = PROJECT_ROOT / ".venv-accounts/Scripts/python.exe" if (PROJECT_ROOT / ".venv-accounts/Scripts/python.exe").is_file() \
        else PROJECT_ROOT / ".venv-accounts/bin/python"
    process = subprocess.run([str(python), str(PROJECT_ROOT / "workers/xls_reader.py"), str(path)],
                             capture_output=True, text=True, timeout=60)
    if process.returncode:
        raise ValueError("XLS 读取失败：" + (process.stderr or "无法解析文件")[:300])
    return json.loads(process.stdout)


def official_metrics(path):
    rows = read_xls(path)
    history = []
    for row in rows:
        if row.get("渠道") != "全部":
            continue
        history.append({"date": row.get("日期"), "views": number(row.get("阅读次数")), "readers": number(row.get("阅读人数")),
                        "shares": number(row.get("分享次数")), "favorites": number(row.get("收藏次数")),
                        "publications": number(row.get("群发篇数"))})
    latest = history[0] if history else {}
    return {"views": latest.get("views"), "readers": latest.get("readers"), "shares": latest.get("shares"),
            "favorites": latest.get("favorites"), "daily_history": history, "analytics_source": "公众号内容分析官方明细"}


def channels_metrics(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle.readlines()[2:]))
    history = [{"date": row.get("时间"), "views": number(row.get("播放")), "likes": number(row.get("喜欢")),
                "comments": number(row.get("评论")), "shares": number(row.get("分享")),
                "newFollowers": number(row.get("关注"))} for row in rows]
    return {"views": history[0]["views"] if history else None, "daily_history": history,
            "periodViews": total(history, "views"), "likes": total(history, "likes"),
            "comments": total(history, "comments"), "shares": total(history, "shares"),
            "newFollowers": total(history, "newFollowers"), "analytics_source": "视频号官方逐日导出"}


def xhs_metrics(paths):
    watch = summary(paths["watch"])
    interaction = summary(paths["interaction"])
    followers = summary(paths["followers"])
    publishing = summary(paths["publishing"])
    return {
        "impressions": watch.get("曝光"), "views": watch.get("观看"), "coverClickRate": watch.get("封面点击率(%)"),
        "avgConsumptionSeconds": watch.get("平均观看时长(s)"), "totalConsumptionSeconds": watch.get("总观看时长(s)"),
        "completionRate": watch.get("总完播率(%)"), "likes": interaction.get("点赞"), "comments": interaction.get("评论"),
        "favorites": interaction.get("收藏"), "shares": interaction.get("分享"), "newFollowers": followers.get("净涨粉"),
        "gainedFollowers": followers.get("新增关注"), "lostFollowers": followers.get("取消关注"),
        "profileVisits": followers.get("主页访客"), "profileConversionRate": followers.get("主页转粉率(%)"),
        "periodPublications": publishing.get("总发布"), "videoPublications": publishing.get("发布视频"),
        "imagePublications": publishing.get("发布图文"), "analytics_source": "小红书数据看板官方导出",
        "daily_history": {"watch": trend(paths["watch"]), "interaction": trend(paths["interaction"]),
                          "followers": trend(paths["followers"]), "publishing": trend(paths["publishing"])},
    }


def weighted_metric(rows, key):
    values = []
    for row in rows:
        weight = number(row.get("总播放量"))
        value = number(row.get(key))
        if weight and value is not None:
            values.append((value, weight))
    total_weight = sum(weight for _, weight in values)
    return round(sum(value * weight for value, weight in values) / total_weight, 2) if total_weight else None


def douyin_metrics(work_path, fans_path):
    work = table(work_path)
    fans = table(fans_path)
    latest_fans = fans[-1] if fans else {}
    return {
        "avgConsumptionSeconds": weighted_metric(work, "平均播放时长"),
        "fiveSecondCompletionRate": weighted_metric(work, "5秒完播率"),
        "coverClickRate": weighted_metric(work, "封面点击率"),
        "views": total(work, "总播放量"), "likes": total(work, "总点赞量"), "shares": total(work, "总分享量"),
        "comments": total(work, "总评论量"), "periodPublications": total(work, "投稿量"),
        "fans": number(latest_fans.get("总粉丝量")), "newFollowers": total(fans, "粉丝净增"),
        "gainedFollowers": total(fans, "吸粉量"), "lostFollowers": total(fans, "脱粉量"),
        "returningFans": total(fans, "回访粉丝量"), "analytics_source": "抖音数据中心官方导出",
        "daily_history": work,
    }
