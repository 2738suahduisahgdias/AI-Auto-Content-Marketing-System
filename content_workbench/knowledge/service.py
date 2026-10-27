import hashlib

from content_workbench.agents.registry import AGENTS
from content_workbench.storage.db import PROJECT_ROOT, connect, dumps, immediate, loads, new_id, utcnow

PREDICATES = {"targets", "solves", "supported_by", "derived_from", "mentions", "produced_by", "published_on", "measured_by", "authorized_for", "uses_model", "executes", "related_to"}


def stable(prefix, value):
    return prefix + "_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


class KnowledgeService:
    def __init__(self, db_path, root):
        self.db_path = str(db_path)
        self.root = root
        self.ensure_schema()

    def conn(self, readonly=False):
        return connect(self.db_path, readonly=readonly)

    def ensure_schema(self):
        with self.conn() as conn:
            conn.executescript((PROJECT_ROOT / "migrations/002_knowledge.sql").read_text())

    def entity(self, entity_type, name, summary="", properties=None):
        entity_id = stable("kb", entity_type + ":" + name)
        with self.conn() as conn, immediate(conn):
            conn.execute("""INSERT INTO kb_entities(id,type,name,summary,properties_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?) ON CONFLICT(type,name) DO UPDATE SET
                summary=excluded.summary,properties_json=excluded.properties_json,updated_at=excluded.updated_at""",
                (entity_id, entity_type, name, summary, dumps(properties or {}), utcnow(), utcnow()))
        return entity_id

    def relate(self, source_type, source_id, predicate, target_type, target_id, evidence=None, properties=None, confidence=1):
        if predicate not in PREDICATES:
            raise ValueError("不支持的关系类型")
        evidence = evidence or {}
        relation_id = stable("rel", dumps([source_type, source_id, predicate, target_type, target_id, evidence]))
        with self.conn() as conn, immediate(conn):
            conn.execute("INSERT OR IGNORE INTO kb_relations VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (relation_id, source_type, source_id, predicate, target_type, target_id,
                          dumps(properties or {}), dumps(evidence), confidence, utcnow()))
        return relation_id

    def backfill(self):
        seed = __import__("json").loads((PROJECT_ROOT / "data/seed.json").read_text())
        strategy = seed["strategy"]
        brand = strategy["brand"]
        account = self.entity("Account", brand["name"], brand["positioning"], {"goal": brand["primary_goal"]})
        for key, audience in strategy["audiences"].items():
            audience_id = self.entity("Audience", audience["description"], properties={"key": key})
            self.relate("Account", account, "targets", "Audience", audience_id, {"source": "account-strategy"})
        for pain in strategy["core_pain_points"]:
            pain_id = self.entity("PainPoint", pain["title"], pain["underlying_problem"], {"key": pain["id"]})
            self.relate("Account", account, "solves", "PainPoint", pain_id, {"source": "account-strategy"})
        for key, pillar in strategy["content_pillars"].items():
            pillar_id = self.entity("ContentPillar", key, pillar["goal"], {"ratio": pillar["ratio"], "topics": pillar["topics"]})
            self.relate("Account", account, "related_to", "ContentPillar", pillar_id, {"source": "account-strategy"})
        for platform, value in seed["platforms"]["platforms"].items():
            self.entity("Platform", platform, value.get("role", ""), {"content_focus": value.get("content_focus", [])})
        for agent_id, definition in AGENTS.items():
            self.entity("Agent", definition["name"], definition["description"], {"agent_id": agent_id, "engine": definition["engine"], "connected": definition["connected"]})
        for rule in strategy["editorial_rules"]:
            rule_id = stable("rule", rule)
            with self.conn() as conn, immediate(conn):
                conn.execute("INSERT OR IGNORE INTO kb_rules VALUES (?,?,?,?)", (rule_id, rule, dumps({"type": "editorial_rule", "text": rule}), utcnow()))
        with self.conn(readonly=True) as conn:
            research = [dict(row) for row in conn.execute("SELECT * FROM wb_research_items")]
            candidates = [dict(row) for row in conn.execute("SELECT * FROM wb_topic_candidates")]
            tasks = [dict(row) for row in conn.execute("SELECT * FROM tasks")]
        research_keys = {}
        for item in research:
            metadata = loads(item["metadata_json"], {})
            evidence_key = metadata.get("title") or item["canonical_url"]
            research_keys[item["id"]] = evidence_key
            evidence_id = self.entity("Evidence", evidence_key, item["canonical_url"], {"platform": item["platform"], "source_key": metadata.get("source_key")})
            self.relate("Evidence", evidence_id, "derived_from", "Platform", stable("kb", "Platform:" + item["platform"]), {"url": item["canonical_url"], "observed_at": item["observed_at"]})
        for row in candidates:
            payload = loads(row["payload_json"], {})
            title = payload.get("title")
            if not title:
                continue
            topic_id = self.entity("Topic", title, payload.get("angle") or payload.get("reason", ""), {"agent": payload.get("agent")})
            for evidence in payload.get("evidence_ids", []):
                evidence_key = research_keys.get(evidence)
                if evidence_key:
                    self.relate("Topic", topic_id, "supported_by", "Evidence", stable("kb", "Evidence:" + evidence_key), {"candidate_id": row["id"]})
        for task in tasks:
            item_id = self.entity("ContentItem", task["title"], task["angle"], {"legacy_task_id": task["content_id"], "state": task["state"]})
            audience_name = strategy["audiences"].get(task["audience"], {}).get("description")
            if audience_name:
                self.relate("ContentItem", item_id, "targets", "Audience", stable("kb", "Audience:" + audience_name), {"legacy_task_id": task["content_id"]})
            pillar_id = stable("kb", "ContentPillar:" + task["pillar"])
            self.relate("ContentItem", item_id, "related_to", "ContentPillar", pillar_id, {"legacy_task_id": task["content_id"]})
        return {"research": len(research), "candidates": len(candidates), "tasks": len(tasks)}

    def bootstrap(self, query="", entity_type=""):
        with self.conn(readonly=True) as conn:
            params = []
            sql = "SELECT * FROM kb_entities WHERE 1=1"
            if query:
                sql += " AND (name LIKE ? OR summary LIKE ?)"
                params += ["%" + query + "%", "%" + query + "%"]
            if entity_type:
                sql += " AND type=?"
                params.append(entity_type)
            sql += " ORDER BY updated_at DESC LIMIT 200"
            entities = [dict(row) for row in conn.execute(sql, params)]
            relations = [dict(row) for row in conn.execute("SELECT * FROM kb_relations ORDER BY created_at DESC LIMIT 400")]
            rules = [dict(row) for row in conn.execute("SELECT * FROM kb_rules ORDER BY name")]
        for entity in entities:
            entity["properties"] = loads(entity.pop("properties_json"), {})
        for relation in relations:
            relation["properties"] = loads(relation.pop("properties_json"), {})
            relation["evidence"] = loads(relation.pop("evidence_json"), {})
        for rule in rules:
            rule["definition"] = loads(rule.pop("definition_json"), {})
        return {"entities": entities, "relations": relations, "rules": rules,
                "types": sorted({row["type"] for row in entities}), "predicates": sorted(PREDICATES)}

    def add_relation(self, source_type, source_id, predicate, target_type, target_id, evidence=None):
        with self.conn(readonly=True) as conn:
            for entity_type, entity_id in ((source_type, source_id), (target_type, target_id)):
                if not conn.execute("SELECT 1 FROM kb_entities WHERE type=? AND id=?", (entity_type, entity_id)).fetchone():
                    raise ValueError("实体不存在：" + entity_type + "/" + entity_id)
        return self.relate(source_type, source_id, predicate, target_type, target_id, evidence or {"source": "manual"})
