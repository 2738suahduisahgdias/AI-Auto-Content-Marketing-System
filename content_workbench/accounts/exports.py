import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

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
