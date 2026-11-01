def video_brief(task):
    source = task.get("source", {})
    return {
        "source": {"type": source.get("type", "manual"), "references": [source] if source else []},
        "title": task["title"],
        "content": task.get("scripts", {}).get("douyin") or task.get("scripts", {}).get("master") or "",
        "audience": task["audience"],
        "platform": source.get("platform", "douyin"),
        "constraints": {"angle": task.get("angle", ""), "pain_point": task.get("pain_point", "")},
        "production_preset": source.get("production_preset", "enterprise_ai_default"),
        "review_mode": source.get("review_mode", "agent"),
        "publish_mode": source.get("publish_mode", "local_only"),
    }


def video_package(task):
    return {
        "content_id": task["content_id"],
        "production_job_id": task.get("active_job_id"),
        "shared": {
            "scripts": task.get("scripts", {}),
            "script_meta": task.get("script_meta", {}),
            "asset_plan": task.get("asset_plan", []),
        },
        "variants": [
            {
                "variant_id": item["id"], "file_id": item["file_id"], "file_sha256": item["file_sha256"],
                "template_id": item["template_id"], "template_version": item["template_version"],
                "approved": bool(item.get("approved_at")), "quality": item.get("quality", {}),
            }
            for item in task.get("variants", [])
        ],
        "machine_review_summary": task.get("quality", {}),
        "stage_timings": task.get("stage_timings", []),
        "review_mode": task.get("source", {}).get("review_mode", "agent"),
        "publish_mode": task.get("source", {}).get("publish_mode", "local_only"),
        "local_output_directory": "renders/{}".format(task["content_id"]),
    }
