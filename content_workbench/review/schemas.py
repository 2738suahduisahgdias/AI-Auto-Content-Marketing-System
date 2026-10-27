from content_workbench.domain.errors import DomainError

DEFAULT_RULES = {
    "target_width": 1080, "target_height": 1920, "min_duration": 1.0, "max_duration": 180.0,
    "black_min_duration": 0.5, "silence_min_duration": 1.0, "silence_noise_db": -45.0,
    "low_mean_volume_db": -35.0, "high_mean_volume_db": -8.0, "ocr_interval": 2.0,
    "ocr_max_frames": 60, "check_ocr": True, "ai_risk": True,
}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv"}


def validate_rules(values):
    if not isinstance(values, dict):
        raise DomainError("REVIEW_RULES_INVALID", "审核规则必须是对象", 422, "rules", "恢复默认规则后重试")
    rules = {**DEFAULT_RULES, **values}
    for key in ("target_width", "target_height", "ocr_max_frames"):
        value = rules[key]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise DomainError("REVIEW_RULES_INVALID", key + " 必须是正整数", 422, key, "填写大于零的整数")
    for key in ("min_duration", "max_duration", "black_min_duration", "silence_min_duration", "ocr_interval"):
        value = rules[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise DomainError("REVIEW_RULES_INVALID", key + " 必须大于零", 422, key, "填写大于零的秒数")
    if rules["min_duration"] >= rules["max_duration"]:
        raise DomainError("REVIEW_RULES_INVALID", "最短时长必须小于最长时长", 422, "max_duration", "调整时长范围")
    for key in ("check_ocr", "ai_risk"):
        if not isinstance(rules[key], bool):
            raise DomainError("REVIEW_RULES_INVALID", key + " 必须是布尔值", 422, key, "选择开启或关闭")
    return rules
