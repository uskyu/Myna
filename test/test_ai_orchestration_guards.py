import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import ai_engine  # noqa: E402


class FakeDb:
    def __init__(self, global_limit=None):
        self.global_limit = global_limit

    def get_hub_setting(self, key):
        if key == "context_messages_limit":
            return self.global_limit
        return None


class OrchestrationGuardTests(unittest.TestCase):
    def test_low_value_reply_blocks_handoff(self):
        self.assertTrue(ai_engine._is_low_value_handoff_reply("@开发 收到，谢谢，没有补充"))
        self.assertTrue(ai_engine._is_low_value_handoff_reply("@产品 开发同学辛苦了，总结到位"))
        self.assertFalse(ai_engine._is_low_value_handoff_reply("@测试 请复测刚修复的问题"))

    def test_guided_requires_tasklike_text(self):
        self.assertFalse(ai_engine._is_tasklike_handoff_reply("@产品 总结到位，辛苦了"))
        self.assertTrue(ai_engine._is_tasklike_handoff_reply("@测试 请执行回归测试并给出结果"))

    def test_context_strategy_inherit_fixed_auto(self):
        self.assertEqual(ai_engine._resolve_context_limit(FakeDb("33"), {"context_strategy": "inherit"}), 33)
        self.assertEqual(ai_engine._resolve_context_limit(FakeDb("33"), {
            "context_strategy": "fixed",
            "context_messages_limit": 12,
        }), 12)
        self.assertGreater(ai_engine._resolve_context_limit(FakeDb("33"), {
            "context_strategy": "auto",
        }, {"model": "claude-opus-4.1"}), 33)

    def test_invalid_modes_fall_back_safely(self):
        self.assertEqual(ai_engine._room_collaboration_mode({"collaboration_mode": "weird"}), "guided")
        self.assertEqual(ai_engine._room_context_strategy({"context_strategy": "weird"}), "inherit")


if __name__ == "__main__":
    unittest.main()
