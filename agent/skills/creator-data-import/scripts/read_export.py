import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from content_workbench.accounts.exports import channels_metrics, douyin_metrics, official_metrics, xhs_metrics

EXPECTED_FILES = {
    "douyin": 2,
    "xiaohongshu": 4,
    "wechat_channels": 1,
    "wechat_official_account": 1,
}
FILE_GUIDES = {
    "douyin": "依次选择短视频全量指标 XLSX、粉丝全量指标 XLSX",
    "xiaohongshu": "依次选择观看、互动、涨粉、发布四份 XLSX",
    "wechat_channels": "选择视频号官方逐日 CSV",
    "wechat_official_account": "选择公众号内容分析官方 XLS 明细",
}


def read_metrics(platform, files):
    if len(files) != EXPECTED_FILES[platform]:
        raise ValueError(f"{platform} 需要 {EXPECTED_FILES[platform]} 份文件，实际收到 {len(files)} 份")
    for file in files:
        if not file.is_file():
            raise ValueError(f"文件不存在或不可读：{file}")
    if platform == "douyin":
        return douyin_metrics(*files)
    if platform == "xiaohongshu":
        return xhs_metrics(dict(zip(("watch", "interaction", "followers", "publishing"), files)))
    if platform == "wechat_channels":
        return channels_metrics(files[0])
    return official_metrics(files[0])


def main():
    parser = argparse.ArgumentParser(description="读取平台创作者后台官方导出，不访问网络或修改账号数据")
    parser.add_argument("--platform", required=True, choices=tuple(EXPECTED_FILES))
    parser.add_argument("--files", required=True, nargs="+", type=Path)
    args = parser.parse_args()
    try:
        metrics = read_metrics(args.platform, args.files)
    except Exception as error:
        result = {
            "status": "error",
            "error_code": "OFFICIAL_EXPORT_READ_FAILED",
            "message": f"官方导出读取失败：{str(error)[:300]}",
            "action": f"{FILE_GUIDES[args.platform]}；确认文件未损坏且来自对应平台数据中心后重新运行，不自动重试",
        }
        print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({
        "status": "success",
        "platform": args.platform,
        "files": [file.name for file in args.files],
        "metrics": metrics,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
