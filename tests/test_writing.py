import unittest

from content_workbench.agents.writing import (
    apply_generated_scripts,
    initial_script_meta,
    load_writing_skills,
    merge_manual_scripts,
    missing_script_fields,
    validate_generated_scripts,
    writing_context,
)
from content_workbench.storage.db import PROJECT_ROOT


class WritingCase(unittest.TestCase):
    def test_manual_merge_does_not_require_master(self):
        scripts, metadata = merge_manual_scripts({}, {}, {"douyin": "我的手填口播"})
        self.assertEqual("我的手填口播", scripts["douyin"])
        self.assertEqual("manual", metadata["douyin"]["origin"])
        self.assertEqual(1, metadata["douyin"]["revision_no"])
        self.assertNotIn("master", missing_script_fields(scripts))

    def test_generation_only_returns_requested_fields(self):
        self.assertEqual({"douyin": "内容"}, validate_generated_scripts({"douyin": "内容"}, ["douyin"]))
        with self.assertRaises(ValueError):
            validate_generated_scripts({"douyin": "内容", "master": "不应生成"}, ["douyin"])

    def test_cas_preserves_new_manual_edit_as_candidate(self):
        scripts = {"douyin": "生成期间的新手填"}
        metadata = initial_script_meta(scripts, {"douyin": {"origin": "manual", "revision_no": 2}})
        updated, meta, conflicts = apply_generated_scripts(
            scripts, metadata, {"douyin": "AI 结果"}, "request-1", {"model": "test"}, {"douyin": 1})
        self.assertEqual("生成期间的新手填", updated["douyin"])
        self.assertEqual("AI 结果", meta["douyin"]["candidate"]["text"])
        self.assertEqual(["douyin"], conflicts)

    def test_unchanged_revision_accepts_generated_text(self):
        scripts = {"douyin": ""}
        metadata = initial_script_meta(scripts, {})
        updated, meta, conflicts = apply_generated_scripts(
            scripts, metadata, {"douyin": "AI 结果"}, "request-1", {"model": "test"}, {"douyin": 0})
        self.assertEqual("AI 结果", updated["douyin"])
        self.assertEqual("agent", meta["douyin"]["origin"])
        self.assertEqual([], conflicts)

    def test_default_skills_are_readonly_markdown_and_injected(self):
        documents = load_writing_skills(PROJECT_ROOT)
        self.assertEqual(2, len(documents))
        prompt, snapshot = writing_context({"model": "default_unpinned", "custom": {}}, PROJECT_ROOT)
        self.assertIn("去 AI 味儿", documents[0]["text"] or prompt)
        self.assertEqual(2, len(snapshot["skills"]))


if __name__ == "__main__":
    unittest.main()
