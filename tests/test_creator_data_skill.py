import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from content_workbench.storage.db import PROJECT_ROOT


class CreatorDataSkillCase(unittest.TestCase):
    def test_reads_channels_export_without_network(self):
        with tempfile.TemporaryDirectory(prefix="creator-data-skill-") as directory:
            path = Path(directory) / "channels.csv"
            path.write_text("视频号视频详情数据,,,,,\n说明,,,,,\n时间,播放,推荐,喜欢,评论,分享,关注\n2026/10/28,10,0,1,0,0,0\n", encoding="utf-8-sig")
            result = subprocess.run(
                [sys.executable, "agent/skills/creator-data-import/scripts/read_export.py", "--platform", "wechat_channels", "--files", str(path)],
                cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("success", payload["status"])
            self.assertEqual(10, payload["metrics"]["views"])
            self.assertEqual("视频号官方逐日导出", payload["metrics"]["analytics_source"])

    def test_reports_file_count_and_remediation(self):
        result = subprocess.run(
            [sys.executable, "agent/skills/creator-data-import/scripts/read_export.py", "--platform", "douyin", "--files", "only-one.xlsx"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30, check=False,
        )
        self.assertEqual(2, result.returncode)
        payload = json.loads(result.stderr)
        self.assertEqual("OFFICIAL_EXPORT_READ_FAILED", payload["error_code"])
        self.assertIn("需要 2 份文件", payload["message"])
        self.assertIn("短视频全量指标", payload["action"])


if __name__ == "__main__":
    unittest.main()
