import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from routes.admin import _extract_skill_request  # noqa: E402


class NaturalLanguageSkillCreateTests(unittest.TestCase):
    def assert_no_skill(self, text: str):
        self.assertIsNone(_extract_skill_request(text), text)

    def test_correction_routing_meta_discussion_does_not_create_skill(self):
        self.assert_no_skill(
            "我再说一遍，跟你讲的话，我是让你直接创建 skill 是在优化创建 skill 的策略。"
            "你不要自己弄了，直接调用 open code，用 open code 去做"
        )

    def test_negative_and_routing_phrases_do_not_create_skill(self):
        negatives = [
            "我再说一遍，请创建 skill：发布流程 内容：先构建再验证",
            "你不要自己弄了，创建 skill：发布流程 内容：先构建再验证",
            "调用 open code 创建 skill：发布流程 内容：先构建再验证",
            "这是在优化创建 skill 的策略，不是要保存技能",
        ]
        for text in negatives:
            with self.subTest(text=text):
                self.assert_no_skill(text)

    def test_plain_discussion_containing_create_skill_does_not_create_skill(self):
        samples = [
            "我们讨论一下创建 skill 的策略，怎么避免误触发？",
            "普通讨论里包含 创建 skill 这几个字，不应该触发持久化。",
            "创建 skill 的时候是不是需要标题和内容？",
            "请帮我创建 skill",  # no explicit title/content delimiter
            "请创建 skill：发布流程",  # no explicit content section
        ]
        for text in samples:
            with self.subTest(text=text):
                self.assert_no_skill(text)

    def test_explicit_command_with_title_and_content_creates_skill(self):
        result = _extract_skill_request(
            "请创建 skill：发布流程\n内容：1. 运行构建。\n2. 执行回归测试。\n3. 发布前确认结果。"
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["name"], "发布流程")
        self.assertIn("运行构建", result["content"])

    def test_source_prefix_is_ignored_for_valid_command(self):
        result = _extract_skill_request(
            "[user]: 请创建 skill《测试流程》\n步骤：先运行单测，再记录结果。"
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["name"], "测试流程")


if __name__ == "__main__":
    unittest.main()
