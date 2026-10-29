def snapshot_has_data(value):
    if value.get("items"):
        return True
    ignored = {"connection", "sync_mode"}
    return any(key not in ignored and item not in (None, "") for key, item in (value.get("profile") or {}).items())
