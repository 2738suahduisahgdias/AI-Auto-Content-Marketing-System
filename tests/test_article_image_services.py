#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from content_workbench.articles.images import (
    adopt_image,
    generate_image,
    search_images,
    validate_svg,
)
from content_workbench.domain.errors import DomainError


class ImageServicesTest(unittest.TestCase):
    def test_search_rejects_empty_without_network(self):
        with patch("content_workbench.articles.images.commons") as network:
            with self.assertRaises(DomainError):
                search_images(" ")
            network.assert_not_called()

    def test_download_refuses_foreign_host(self):
        page = {
            "title": "File:test.png",
            "imageinfo": [
                {"mime": "image/png", "url": "https://localhost/private.png"}
            ],
        }
        with (
            patch("content_workbench.articles.images.commons", return_value=[page]),
            patch("content_workbench.articles.images.request_bytes") as network,
        ):
            with self.assertRaises(DomainError) as error:
                adopt_image(Mock(), "File:test.png")
            self.assertEqual(error.exception.code, "IMAGE_HOST_INVALID")
            network.assert_not_called()

    def test_kimi_svg_rejects_scripts_and_external_resources(self):
        with self.assertRaises(DomainError) as error:
            validate_svg(
                '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
            )
        self.assertEqual(error.exception.code, "IMAGE_SVG_INVALID")
        with self.assertRaises(DomainError):
            validate_svg(
                '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.com/a.png"/></svg>'
            )

    def test_pagination_preserves_text_and_bounds(self):
        from content_workbench.articles.page_worker import BOTTOM, render_pages

        font = Path("/System/Library/Fonts/STHeiti Light.ttc")
        if not font.exists():
            self.skipTest("CJK font unavailable")
        text = "".join(f"验收条目{i}，知识库检索与人工处理。" for i in range(180))
        with tempfile.TemporaryDirectory() as tmp:
            pages = render_pages({"title": "验收", "text": text}, tmp, font)
            self.assertGreater(len(pages), 1)
            blocks = [b for p in pages for b in p["blocks"]]
            self.assertEqual("".join(b["text"] for b in blocks), "验收" + text)
            for b in blocks:
                self.assertLessEqual(b["y"] + b["height"], BOTTOM)
            for p in pages:
                self.assertTrue((Path(tmp) / p["file"]).exists())

    def test_xhs_upload_uses_ordered_pages_and_never_publishes(self):
        from content_workbench.publishing.webbridge_worker import prepare_xhs_images

        bridge = Mock()
        bridge.snapshot.return_value = {"tree": []}
        bridge.click_text.return_value = True
        bridge.evaluate.return_value = {
            "title": "验收",
            "body": "简介\n\n#验收",
            "count": 2,
            "loaded": True,
            "ready": True,
        }
        bridge.result.side_effect = lambda target, status, fields, extra: {
            "status": status,
            **extra,
        }
        source = {
            "title": "简介",
            "article_pages": [
                {"asset_id": "a", "absolute_path": "/local/1.png"},
                {"asset_id": "b", "absolute_path": "/local/2.png"},
            ],
        }
        with patch("content_workbench.publishing.webbridge_worker.fill"):
            result = prepare_xhs_images(
                bridge,
                {
                    "source": source,
                    "payload": {"title": "验收", "tags": "#验收"},
                    "target_id": "t",
                },
                "prepare",
            )
        self.assertTrue(result["article_images_verified"])
        self.assertFalse(result["auto_published"])
        bridge.call.assert_any_call(
            "upload",
            {"selector": "input[type=file]", "files": ["/local/1.png", "/local/2.png"]},
        )
        bridge.click_text.assert_called_once_with("上传图文")

    def test_xhs_login_stops_before_upload(self):
        from content_workbench.publishing.webbridge_worker import prepare_xhs_images

        bridge = Mock()
        bridge.snapshot.return_value = {"tree": ["扫码登录"]}
        result = prepare_xhs_images(
            bridge,
            {
                "source": {
                    "title": "说明",
                    "article_pages": [{"asset_id": "a", "absolute_path": "/1.png"}],
                },
                "payload": {"title": "标题"},
                "target_id": "t",
            },
            "prepare",
        )
        self.assertEqual(result["status"], "login_required")
        self.assertNotIn(
            "upload", [call.args[0] for call in bridge.call.call_args_list]
        )

    def test_kimi_svg_is_rendered_without_api_credentials(self):
        from tests.test_article_images import PNG

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = Mock()
            workbench = Mock(root=root, db_path=root / "data/content-agent.db")
            workbench.register_asset.return_value = "asset-real"
            provider = Mock()
            provider.complete_text.return_value = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1200"><rect width="1200" height="1200" fill="#fff"/><text x="80" y="160">验收</text></svg>'

            def execute(args, **kwargs):
                Path(args[args.index("--output") + 1]).write_bytes(PNG)

            context.run_process.side_effect = execute
            with (
                patch(
                    "content_workbench.articles.images.provider_for",
                    return_value=provider,
                ) as factory,
                patch(
                    "content_workbench.articles.images.require_agent_enabled",
                    return_value={
                        "engine": "model_api",
                        "model": "image-agent-model",
                        "timeout_seconds": 600,
                    },
                ),
            ):
                result = generate_image(
                    workbench, {"id": "job", "input": {"prompt": "diagram"}}, context
                )
            self.assertEqual(result["asset_id"], "asset-real")
            self.assertEqual(result["source"]["provider"], "model_api")
            self.assertEqual(result["source"]["model"], "image-agent-model")
            self.assertEqual(result["source"]["renderer"], "remotion_still")
            factory.assert_called_once_with(root, "model_api")
            self.assertEqual(
                provider.complete_text.call_args.kwargs["model"], "image-agent-model"
            )
            context.run_process.assert_called_once()
