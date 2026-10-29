from .contracts import contract_fields


def unsupported_payload_field(platform, content_kind, payload, supported):
    for definition in contract_fields(platform, content_kind):
        name = definition["name"]
        if definition["control"] == "source" or name in supported:
            continue
        default = definition["default"]
        value = payload.get(name, default)
        if value == default or value in (None, "", "[]", [], {}):
            continue
        return {"status": "error", "field": name,
                "error": definition["label"] + "已保存，但当前连接器尚未接入，不能静默忽略",
                "action": "清空该字段后重试，或在平台后台人工设置；完成连接器验收前不会公开发布"}
    return None
