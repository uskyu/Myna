import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
ADMIN_PATH = BACKEND / "routes" / "admin.py"
sys.path.insert(0, str(BACKEND))


def load_tests(loader, standard_tests, pattern):
    suite = unittest.TestSuite()
    module = sys.modules[__name__]
    for name in sorted(dir(module)):
        if name.startswith("test_"):
            suite.addTest(unittest.FunctionTestCase(getattr(module, name)))
    return suite


def _load_admin_module():
    spec = importlib.util.spec_from_file_location("planning_admin", ADMIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compact_task_name_strips_home_shortcuts():
    admin = _load_admin_module()
    samples = {
        "请帮我制作一个智慧农业平台": "智慧农业平",
        "请根据以下主题生成一份结构完整、可演示的 PPT：东农智能体产品发布": "东农智能体",
        "请根据以下需求生成高质量图像，并先完善视觉提示词：未来农业城市": "未来农业城",
    }
    for prompt, expected in samples.items():
        assert admin._compact_task_name(prompt) == expected
        assert 3 <= len(admin._compact_task_name(prompt)) <= 5


def test_compact_task_name_has_safe_fallback():
    admin = _load_admin_module()
    assert admin._compact_task_name("!!") == "任务规划"


class _FakeDB:
    def __init__(self):
        self.settings = {}
        self.agents = {}
        self.created = []

    def get_hub_setting(self, key, default=None):
        return self.settings.get(key, default)

    def set_hub_setting(self, key, value):
        self.settings[key] = value

    def get_agent_by_id(self, agent_id):
        return self.agents.get(agent_id)

    def create_agent(self, name, description=""):
        agent_id = f"agent-{len(self.created) + 1}"
        agent = {"id": agent_id, "name": name, "description": description}
        self.agents[agent_id] = agent
        self.created.append(agent)
        return agent


def test_planning_orchestrator_created_lazily_and_reused():
    admin = _load_admin_module()
    db = _FakeDB()
    first = admin._get_or_create_planning_orchestrator(db)
    assert admin._is_real_agent(first)
    assert db.settings.get("default_orchestrator_agent_id") == first["id"]
    second = admin._get_or_create_planning_orchestrator(db)
    assert second["id"] == first["id"]
    assert len(db.created) == 1


def test_planning_orchestrator_respects_configured_value():
    admin = _load_admin_module()
    db = _FakeDB()
    db.agents["cfg"] = {"id": "cfg", "name": "Coordinator"}
    db.settings["orchestrator_agent_id"] = "cfg"
    orchestrator = admin._get_or_create_planning_orchestrator(db)
    assert orchestrator["id"] == "cfg"
    assert len(db.created) == 0
