import json
import shutil
import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def javascript_function(path: Path, name: str, next_name: str) -> str:
    source = path.read_text()
    start = source.index(f"function {name}(")
    markers = (f"\nfunction {next_name}(", f"\nasync function {next_name}(")
    offsets = [source.index(marker, start) for marker in markers if marker in source[start:]]
    return source[start : min(offsets)]


@unittest.skipUnless(shutil.which("node"), "Node required for legacy UI fixtures")
class LegacyUITest(unittest.TestCase):
    def run_javascript(self, code: str, state: dict) -> dict:
        harness = """
const vm = require('node:vm');
const context = {
  state: JSON.parse(process.argv[2]),
  platformNames: {douyin: '抖音', xiaohongshu: '小红书', wechat_channels: '视频号'},
  esc: value => String(value ?? ''),
};
vm.createContext(context);
vm.runInContext(process.argv[1], context);
const source = context.publishingSource('video');
console.log(JSON.stringify({videos: context.approvedVideos(), source}));
"""
        output = subprocess.check_output(["node", "-e", harness, code, json.dumps(state)], text=True)
        return json.loads(output)

    def test_review_approved_delivery_uses_review_source_for_publishing(self):
        code = "\n".join(
            [
                javascript_function(PROJECT_ROOT / "web/workspaces.js", "approvedVideos", "renderPublishing"),
                javascript_function(PROJECT_ROOT / "web/publishing.js", "publishingSource", "loadPublishingBatch"),
            ]
        )
        state = {
            "data": {
                "tasks": [
                    {
                        "content_id": "legacy-approved",
                        "title": "旧任务",
                        "state": "approved",
                        "files": [{"kind": "video"}],
                    },
                    {
                        "content_id": "yingxu-task",
                        "title": "映序任务",
                        "state": "rendered",
                        "files": [{"kind": "video"}],
                        "source": {"yingxu_handoff": {"status": "approved"}},
                    },
                ],
            },
            "publishing": {
                "videoId": None,
                "queue": [
                    {
                        "id": "reviewitem_1",
                        "title": "映序任务",
                        "body": "已审核正文",
                        "delivery": {"content_id": "yingxu-task"},
                    }
                ],
            },
        }
        result = self.run_javascript(code, state)
        self.assertEqual(["reviewitem_1", "legacy-approved"], [item["content_id"] for item in result["videos"]])
        self.assertEqual("reviewitem_1", result["source"]["id"])
        self.assertEqual("已审核正文", result["source"]["body"])

    def test_research_card_uses_item_platform_instead_of_douyin_default(self):
        code = javascript_function(PROJECT_ROOT / "web/app.js", "researchCard", "syncSummary")
        harness = """
const vm = require('node:vm');
const context = {
  platformNames: {douyin: '抖音', xiaohongshu: '小红书'},
  esc: value => String(value ?? ''),
};
vm.createContext(context);
vm.runInContext(process.argv[1], context);
console.log(context.researchCard({id: 'research_1', platform: 'xiaohongshu', title: '小红书笔记', metadata: {}}, false));
"""
        output = subprocess.check_output(["node", "-e", harness, code], text=True)
        self.assertIn("<b>小红书</b>", output)
        self.assertNotIn("<b>抖音</b>", output)


if __name__ == "__main__":
    unittest.main()
