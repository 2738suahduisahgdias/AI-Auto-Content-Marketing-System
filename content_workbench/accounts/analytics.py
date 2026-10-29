from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from content_workbench.storage.db import connect, loads

PLATFORMS = ("douyin", "wechat_channels", "xiaohongshu", "wechat_official_account")
RANGES = ("today", "yesterday", "7d", "30d")
METRICS = ("reach", "likes", "comments", "shares", "favorites", "avgConsumptionSeconds",
           "completionRate", "engagementRate", "profileVisits", "newFollowers")


def parse_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=ZoneInfo("UTC"))
    except (TypeError, ValueError):
        return None


def public_number(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().lower().replace(",", "")
    if not text:
        return None
    multiplier = 10000 if text.endswith(("万", "w")) else 1
    if multiplier != 1:
        text = text[:-1]
    try:
        number = float(text) * multiplier
        return int(number) if number.is_integer() else number
    except ValueError:
        return None


def item_metric(item, key):
    metadata = item.get("metadata") or {}
    metrics = item.get("metrics") or {}
    aliases = {"likes": ("likes", "like_count", "digg_count"),
               "reach": ("reach", "views", "readers", "play_count"),
               "comments": ("comments", "comment_count"),
               "shares": ("shares", "share_count"),
               "favorites": ("favorites", "favorite_count", "collect_count")}
    for candidate in aliases.get(key, (key,)):
        for source in (metrics, item, metadata):
            if candidate in source:
                return public_number(source.get(candidate))
    return None


def empty_metrics():
    return {"originals": 0, "publications": 0, "articles": 0, "videos": 0,
            **{key: None for key in METRICS},
            "inquiries": None, "qualifiedLeads": None, "highIntentLeads": None,
            "meetings": None, "deals": None, "revenue": None}


def apply_leads(metrics, leads, deal_leads):
    qualified = {"qualified", "high_intent", "meeting", "deal"}
    high_intent = {"high_intent", "meeting", "deal"}
    metrics.update({"inquiries": len(leads),
                    "qualifiedLeads": sum(lead["stage"] in qualified for lead in leads),
                    "highIntentLeads": sum(lead["stage"] in high_intent for lead in leads),
                    "meetings": sum(lead["stage"] in {"meeting", "deal"} for lead in leads),
                    "deals": len(deal_leads)})
    revenue = [lead["revenue"] for lead in deal_leads if lead["revenue"] is not None]
    metrics["revenue"] = sum(revenue) if revenue else None


class AccountAnalytics:
    def __init__(self, db_path):
        self.db_path = str(db_path)

    def conn(self):
        return connect(self.db_path, readonly=True)

    def tables(self, conn):
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    def publications(self, conn, tables, local_now):
        if not {"publish_targets", "publish_batches"}.issubset(tables):
            return []
        rows = conn.execute("""SELECT t.id,t.platform,t.payload_json,t.preview_json,t.external_url,t.updated_at,
                                      b.content_kind,b.source_id
                               FROM publish_targets t JOIN publish_batches b ON b.id=t.batch_id
                               WHERE t.status='published'""").fetchall()
        result = []
        for row in rows:
            payload = loads(row["payload_json"], {})
            preview = loads(row["preview_json"], {})
            verified_at = preview.get("reconciled_at") or row["updated_at"]
            local_time = parse_time(verified_at)
            if not local_time:
                continue
            result.append({"id": row["id"], "source_id": row["source_id"], "platform": row["platform"],
                           "kind": row["content_kind"], "title": payload.get("title") or row["source_id"],
                           "published_at": local_time.astimezone(ZoneInfo("Asia/Shanghai")).isoformat(),
                           "url": row["external_url"], "verified": True,
                           "_time": local_time.astimezone(ZoneInfo("Asia/Shanghai"))})
        return result

    def snapshots(self, conn, tables):
        if "account_daily_snapshots" not in tables:
            return {}
        rows = conn.execute("SELECT * FROM account_daily_snapshots ORDER BY captured_at DESC").fetchall()
        result = {}
        previous = {}
        for row in rows:
            platform = row["platform"]
            if platform in result:
                if platform not in previous:
                    value = loads(row["snapshot_json"], {})
                    previous_totals = {}
                    for key in METRICS[:5]:
                        values = [item_metric(item, key) for item in value.get("items") or []]
                        present = [value for value in values if value is not None]
                        previous_totals[key] = sum(present) if present else None
                    previous[platform] = {"totals": previous_totals}
                    result[platform]["delta"] = {key: result[platform]["totals"][key] - previous[platform]["totals"][key]
                        if result[platform]["totals"][key] is not None and previous[platform]["totals"][key] is not None else None
                        for key in METRICS[:5]}
                    result[platform]["baseline_available"] = True
                continue
            value = loads(row["snapshot_json"], {})
            items = value.get("items") or []
            totals = {}
            for key in METRICS[:5]:
                values = [item_metric(item, key) for item in items]
                present = [value for value in values if value is not None]
                totals[key] = sum(present) if present else None
            result[platform] = {"captured_at": row["captured_at"], "profile": value.get("profile") or {},
                                "totals": totals, "items": items, "baseline_available": False,
                                "delta": {key: None for key in METRICS[:5]}}
        return result

    def leads(self, conn, tables):
        if "account_leads" not in tables:
            return []
        result = []
        for row in conn.execute("SELECT * FROM account_leads ORDER BY occurred_at DESC"):
            value = dict(row)
            value["_time"] = parse_time(value["occurred_at"])
            value["_deal_time"] = parse_time(value.get("deal_at"))
            if value["_time"]:
                result.append(value)
        return result

    def competitors(self, conn, tables):
        if "wb_research_items" not in tables:
            return {"items": [], "summary": {"total": 0, "authors": 0, "complete": 0, "partial": 0}}
        rows = conn.execute("SELECT * FROM wb_research_items ORDER BY last_seen_at DESC").fetchall()
        items = []
        for row in rows:
            metadata = loads(row["metadata_json"], {})
            source = metadata.get("source_key")
            if source not in ("competitor", "high_praise"):
                continue
            likes = item_metric({"metadata": metadata}, "likes")
            comments = item_metric({"metadata": metadata}, "comments")
            shares = item_metric({"metadata": metadata}, "shares")
            favorites = item_metric({"metadata": metadata}, "favorites")
            visible = [value for value in (likes, comments, shares, favorites) if value is not None]
            items.append({"id": row["id"], "platform": row["platform"], "title": metadata.get("title") or "未读取标题",
                          "author": metadata.get("author") or "未识别作者", "url": row["canonical_url"],
                          "source": source, "likes": likes, "comments": comments, "shares": shares, "favorites": favorites,
                          "visible_interactions": sum(visible) if visible else None,
                          "captured_at": row["last_seen_at"], "published_at": metadata.get("published_at"),
                          "completeness": "complete" if len(visible) >= 2 else "partial"})
        return {"items": items, "summary": {"total": len(items), "authors": len({item["author"] for item in items}),
                "complete": sum(item["completeness"] == "complete" for item in items),
                "partial": sum(item["completeness"] == "partial" for item in items)}}

    def bootstrap(self, now=None):
        local_now = (now or datetime.now(ZoneInfo("Asia/Shanghai"))).astimezone(ZoneInfo("Asia/Shanghai"))
        today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        boundaries = {"today": (today, local_now), "yesterday": (today - timedelta(days=1), today),
                      "7d": (local_now - timedelta(days=7), local_now),
                      "30d": (local_now - timedelta(days=30), local_now)}
        with self.conn() as conn:
            tables = self.tables(conn)
            publications = self.publications(conn, tables, local_now)
            snapshots = self.snapshots(conn, tables)
            leads = self.leads(conn, tables)
            competitors = self.competitors(conn, tables)
        platforms = {}
        for platform in PLATFORMS:
            ranges = {}
            for range_key in RANGES:
                start, end = boundaries[range_key]
                selected = [item for item in publications if item["platform"] == platform and start <= item["_time"] < end]
                selected_leads = [lead for lead in leads if lead["platform"] == platform and start <= lead["_time"].astimezone(ZoneInfo("Asia/Shanghai")) < end]
                selected_deals = [lead for lead in leads if lead["platform"] == platform and lead["_deal_time"] and start <= lead["_deal_time"].astimezone(ZoneInfo("Asia/Shanghai")) < end]
                metrics = empty_metrics()
                metrics.update({"originals": len({item["source_id"] for item in selected}), "publications": len(selected),
                                "articles": len({item["source_id"] for item in selected if item["kind"] == "article"}),
                                "videos": len({item["source_id"] for item in selected if item["kind"] == "video"})})
                apply_leads(metrics, selected_leads, selected_deals)
                if range_key == "today" and snapshots.get(platform, {}).get("baseline_available"):
                    for key in METRICS[:5]:
                        metrics[key] = snapshots[platform]["delta"][key]
                ranges[range_key] = metrics
            snapshot = snapshots.get(platform)
            platforms[platform] = {"metrics": ranges, "snapshot": snapshot}
        totals = {}
        for range_key in RANGES:
            start, end = boundaries[range_key]
            selected = [item for item in publications if start <= item["_time"] < end]
            selected_leads = [lead for lead in leads if start <= lead["_time"].astimezone(ZoneInfo("Asia/Shanghai")) < end]
            selected_deals = [lead for lead in leads if lead["_deal_time"] and start <= lead["_deal_time"].astimezone(ZoneInfo("Asia/Shanghai")) < end]
            metrics = empty_metrics()
            metrics.update({"originals": len({item["source_id"] for item in selected}), "publications": len(selected),
                            "articles": len({item["source_id"] for item in selected if item["kind"] == "article"}),
                            "videos": len({item["source_id"] for item in selected if item["kind"] == "video"})})
            apply_leads(metrics, selected_leads, selected_deals)
            if range_key == "today":
                for key in METRICS[:5]:
                    values = [snapshot["delta"][key] for snapshot in snapshots.values() if snapshot.get("baseline_available") and snapshot["delta"][key] is not None]
                    metrics[key] = sum(values) if values else None
            totals[range_key] = metrics
        contents = [{key: value for key, value in item.items() if key != "_time"} for item in sorted(publications, key=lambda value: value["_time"], reverse=True)]
        for platform, snapshot in snapshots.items():
            for index, item in enumerate(snapshot["items"]):
                metadata = item.get("metadata") or {}
                contents.append({"id": "{}-{}".format(platform, index), "source_id": None, "platform": platform,
                                 "kind": "article" if platform == "wechat_official_account" else "video",
                                 "title": item.get("title") or metadata.get("title") or "未读取标题",
                                 "published_at": metadata.get("published_at"), "url": item.get("canonical_url") or item.get("url"),
                                 "verified": False, "captured_at": snapshot["captured_at"],
                                 "metrics": {key: item_metric(item, key) for key in METRICS[:5]}})
        labels = [(today - timedelta(days=6 - index)) for index in range(7)]
        trend = []
        for day in labels:
            next_day = day + timedelta(days=1)
            trend.append(sum(day <= item["_time"] < next_day for item in publications))
        sync = [{"platform": platform, "status": "succeeded" if platform in snapshots else "not_connected",
                 "captured_at": snapshots.get(platform, {}).get("captured_at"),
                 "detail": "累计公开快照，不代表今日新增" if platform in snapshots else "尚无真实账号快照"}
                for platform in PLATFORMS]
        return {"timezone": "Asia/Shanghai", "generated_at": local_now.isoformat(), "platforms": platforms,
                "totals": totals, "contents": contents,
                "trends": {"publications": {"labels": [day.strftime("%m/%d") for day in labels], "values": trend}},
                "sync": sync, "competitor_analytics": competitors,
                "leads": [{key: value for key, value in lead.items() if key not in {"_time", "_deal_time"}} for lead in leads],
                "data_boundaries": ["发布数量仅来自已核验发布记录。", "账号快照为累计值；没有前后快照时不计算今日新增。",
                                    "私信线索与成交仅来自本地人工记录；完播和留存未接入时保持未读取。"]}
