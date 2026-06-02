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
    def _candidate(self, source="dev", target="tester", depth=0, kind="text_mention"):
        return {
            "source": kind,
            "source_agent_id": source,
            "target": target,
            "chain_depth": depth,
        }

    def _evaluate(self, state, reply, source="dev", target="tester", tools=None, settings=None, depth=0):
        return ai_engine._evaluate_handoff_candidate(
            self._candidate(source, target, depth),
            reply,
            tools or [],
            state,
            settings or {"collaboration_mode": "guided"},
        )

    def test_low_value_reply_blocks_handoff(self):
        self.assertTrue(ai_engine._is_low_value_handoff_reply("@开发 收到，谢谢，没有补充"))
        self.assertTrue(ai_engine._is_low_value_handoff_reply("@产品 开发同学辛苦了，总结到位"))
        self.assertTrue(ai_engine._is_low_value_handoff_reply("@测试 请继续"))
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

    def test_allows_dev_tester_rework_with_progress(self):
        state = ai_engine._init_handoff_state()
        settings = {"collaboration_mode": "guided"}

        decisions = [
            self._evaluate(state, "已完成登录修复。@tester 请执行回归测试。", "dev", "tester", settings=settings),
            self._evaluate(state, "测试失败：登录接口返回 500。@dev 请修复。", "tester", "dev", settings=settings),
            self._evaluate(state, "已修复空指针并新增校验。@tester 请复测。", "dev", "tester", tools=[{"name": "run_command"}], settings=settings),
            self._evaluate(state, "复测通过，登录流程正常。@summary 请总结。", "tester", "summary", settings=settings),
        ]

        self.assertEqual([d["decision"] for d in decisions], ["allowed", "allowed", "allowed", "allowed"])
        self.assertEqual(state["edge_counts"]["dev->tester"], 2)
        self.assertTrue(decisions[2]["progress_signals"]["tool_calls"])

    def test_blocks_low_value_mutual_mentions(self):
        state = ai_engine._init_handoff_state()
        first = self._evaluate(state, "@tester 收到，好的，请继续", "dev", "tester")
        second = self._evaluate(state, "@dev 好的，请继续", "tester", "dev")

        self.assertEqual(first["decision"], "suppressed")
        self.assertEqual(first["reason"], "low_value_reply")
        self.assertEqual(second["decision"], "suppressed")
        self.assertEqual(second["reason"], "low_value_reply")

    def test_blocks_repeated_same_failure_without_tools(self):
        state = ai_engine._init_handoff_state()
        settings = {"collaboration_mode": "guided", "handoff_same_failure_limit": 2}
        reply = "测试失败：登录接口返回 500。@dev 请修复。"

        first = self._evaluate(state, reply, "tester", "dev", settings=settings)
        second = self._evaluate(state, reply, "tester", "dev", settings=settings)
        third = self._evaluate(state, reply, "tester", "dev", settings=settings)

        self.assertEqual(first["decision"], "allowed")
        self.assertEqual(second["decision"], "allowed")
        self.assertEqual(third["decision"], "suppressed")
        self.assertEqual(third["reason"], "same_failure_signature")

    def test_manual_mode_suppresses_mentions(self):
        state = ai_engine._init_handoff_state()
        decision = self._evaluate(
            state,
            "已完成实现。@tester 请复测。",
            settings={"collaboration_mode": "manual"},
        )

        self.assertEqual(decision["decision"], "suppressed")
        self.assertEqual(decision["reason"], "manual_mode")

    def test_max_chain_depth_still_blocks(self):
        state = ai_engine._init_handoff_state()
        decision = self._evaluate(
            state,
            "已修复。@tester 请复测。",
            settings={"collaboration_mode": "guided", "max_chain_depth": 2},
            depth=1,
        )

        self.assertEqual(decision["decision"], "suppressed")
        self.assertEqual(decision["reason"], "max_chain_depth")
        self.assertEqual(decision["budget_remaining"], 0)


if __name__ == "__main__":
    unittest.main()
