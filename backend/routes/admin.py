"""
Admin API routes - agents, rooms, threads, workflows, skills, models, messages.
"""
import os
import json
import asyncio
import re
import threading
import time
import secrets
from collections import Counter
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from workspaces import get_room_workspace_info
from paths import APP_ROOT, PROFILES_ROOT
from routes.auth import current_tenant_id, get_current_account, is_admin_account, is_authenticated

router = APIRouter()

MENTION_RE = r"@([^\s@,，.。;；:：!！?？]+)"
RESERVED_AGENT_IDS = {"system", "user", "__system__", "__all__"}

# TRAE experience account message limit
TRAE_MSG_LIMIT_PER_USER = 2
TRAE_MSG_TRACKER_KEY = "traetest_msg_tracker"
TRAE_DEMO_GITHUB_URL = "https://github.com/uskyu/Myna"
TRAE_MSG_LIMIT_TIP = (
    "为了控制公共 Demo 的 token 消耗，体验账号每天仅开放 10 个体验名额，"
    "每位体验用户只能体验 1-2 个问题/任务。深度体验欢迎点击 GitHub 链接自行部署："
    f"{TRAE_DEMO_GITHUB_URL} ，有问题可联系作者一起调整。"
)
_msg_lock = threading.Lock()


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "0.0.0.0"


def _check_traetest_message_limit(db, ip: str) -> tuple[bool, str]:
    with _msg_lock:
        raw = db.get_hub_setting(TRAE_MSG_TRACKER_KEY) or "{}"
        try:
            tracker = json.loads(raw)
        except Exception:
            tracker = {}
        today = time.strftime("%Y-%m-%d")
        if tracker.get("date") != today or not isinstance(tracker.get("ip_counts"), dict):
            tracker = {"date": today, "ip_counts": {}}
        cur = tracker["ip_counts"].get(ip, 0)
        if cur >= TRAE_MSG_LIMIT_PER_USER:
            return False, TRAE_MSG_LIMIT_TIP
        tracker["ip_counts"][ip] = cur + 1
        db.set_hub_setting(TRAE_MSG_TRACKER_KEY, json.dumps(tracker))
        return True, ""


SKILL_CREATE_RE = re.compile(
    r"^(?:请|麻烦|帮我)?\s*(?:(?:给|为|帮)\s*@?[^\s@,，。；;:：!！?？]{2,32}\s*)?"
    r"(?:创建|新建|保存|学习|记录|加入|添加)\s*(?:一个|一条|本次|这个|此)?\s*(?:skill|技能)\s*(?=[：:《\"“'])",
    re.I,
)
SKILL_TITLE_RE = re.compile(r"(?:skill|技能)[：:《\"“']+\s*([^\n,，。；;:：》\"”']{2,48})", re.I)
SKILL_TARGET_RE = re.compile(r"(?:给|为|帮)\s*@?([^\s@,，。；;:：!！?？]{2,32})\s*(?:创建|新建|保存|学习|记录|添加|加入)")


def is_real_agent(agent: dict | None) -> bool:
    return bool(agent and agent.get("id") not in RESERVED_AGENT_IDS and agent.get("name"))


SHARES_DIR = APP_ROOT / "data" / "shares"
SHARES_DIR.mkdir(parents=True, exist_ok=True)


def _account_orchestrator(db, tenant_id: str | None) -> dict | None:
    configured_id = db.get_hub_setting("orchestrator_agent_id") or db.get_hub_setting("default_orchestrator_agent_id")
    base = db.get_agent_by_id(configured_id) if configured_id else None
    if tenant_id is None:
        return base if is_real_agent(base) else None
    own = next((agent for agent in db.list_agents(tenant_id) if agent.get("name") == "马哥"), None)
    if own:
        return own
    if not is_real_agent(base):
        return None
    return db.create_agent("马哥", base.get("description") or "当前账号的隔离主助手", base.get("model_config_id"), tenant_id)


def _share_file(token: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,80}", token or ""):
        raise ValueError("Invalid share token")
    return SHARES_DIR / f"{token}.json"


ASSISTANT_MARKER_RE = re.compile(r"<!--myna-assistant:(?:fast|expert):[\d.]+-->\s*", re.I)


def _clean_assistant_text(text: str) -> str:
    return ASSISTANT_MARKER_RE.sub("", str(text or "")).strip()


def _compact_task_name(text: str) -> str:
    value = _clean_assistant_text(text)
    value = re.sub(r"https?://\S+|/uploads/\S+|\[[^]]+\]\([^)]*\)", " ", value)
    value = re.sub(r"^(?:请|麻烦)?(?:帮我|给我|根据|围绕|生成|创建|制作|做一个|做一份)+", "", value).strip()
    first = re.split(r"[。！？!?\n；;]", value, maxsplit=1)[0]
    chinese = "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", first))
    return chinese[:12] if len(chinese) >= 3 else "新任务"


def _history_keywords(messages: list, limit: int = 5) -> list[str]:
    stop = {"这个", "那个", "我们", "你们", "他们", "可以", "需要", "进行", "相关", "内容", "任务", "问题", "功能", "智能体", "用户", "系统", "一个", "一下", "现在", "已经", "然后", "没有", "不是", "什么", "怎么", "如果", "以及"}
    scores = Counter()
    for position, message in enumerate(messages):
        text = _clean_assistant_text(message.get("text") or "")
        weight = max(1, len(messages) - position)
        for phrase in re.findall(r"[A-Za-z][A-Za-z0-9_.-]*[\u4e00-\u9fff]{2,12}", text):
            scores[phrase] += weight * len(phrase) * 3
        for phrase in re.findall(r"[A-Za-z][A-Za-z0-9_.-]{2,24}|[\u4e00-\u9fff]{3,12}", text):
            if phrase.lower() in stop or phrase in stop:
                continue
            scores[phrase] += weight
        for block in re.findall(r"[\u4e00-\u9fff]{5,20}", text):
            for size in range(4, min(9, len(block) + 1)):
                for index in range(len(block) - size + 1):
                    phrase = block[index:index + size]
                    if not any(word in phrase for word in stop):
                        scores[phrase] += weight * size
    selected = []
    for phrase, _ in scores.most_common(50):
        if any(phrase in existing or existing in phrase for existing in selected):
            continue
        selected.append(phrase)
        if len(selected) >= limit:
            break
    return selected


def _clean_skill_name(value: str) -> str:
    name = re.sub(r"^(?:一个|一条|本次|这个|此)?\s*(?:skill|技能)\s*", "", value or "", flags=re.I).strip()
    name = re.split(r"(?:\s+|[，,。\n；;])(?:内容|步骤|规则|流程|要求)\s*[：:]?", name, maxsplit=1)[0]
    name = re.split(r"[。\n；;]", name, maxsplit=1)[0].strip(" ：:《》\"'“”`*#")
    return name[:48]


def _strip_message_source_prefix(text: str) -> str:
    """Remove UI/chat sender prefixes before command parsing."""
    return re.sub(r"^\s*\[[^\]]{1,32}\]\s*[：:]\s*", "", text or "").strip()


def _looks_like_skill_meta_discussion(text: str) -> bool:
    """Guard against discussions/corrections that merely mention skill creation."""
    normalized = _strip_message_source_prefix(text)
    lowered = normalized.lower()
    negative_markers = (
        "我再说一遍", "不是让你", "不是叫你", "不要", "别", "禁止", "不能",
        "别自己", "不要自己", "不要创建", "别创建",
    )
    routing_markers = ("调用 open code", "调用 opencode", "open code", "opencode")
    meta_markers = ("优化创建 skill 的策略", "优化创建技能的策略", "创建 skill 的策略", "创建技能的策略")
    if any(marker in normalized for marker in negative_markers):
        return True
    if any(marker in lowered for marker in routing_markers):
        return True
    if any(marker in normalized for marker in meta_markers):
        return True
    return False


def _extract_skill_request(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None
    normalized = _strip_message_source_prefix(raw)
    if not normalized or _looks_like_skill_meta_discussion(normalized):
        return None

    # Natural-language skill creation is intentionally conservative: it must be
    # a command at the beginning of the message, include an explicit title
    # delimiter (技能：标题 / skill《标题》), and include explicit body content.
    # This prevents ordinary discussion such as “创建 skill 的策略” from causing
    # persistent skill writes.
    if not SKILL_CREATE_RE.search(normalized):
        return None

    explicit_title = SKILL_TITLE_RE.search(normalized)
    if not explicit_title:
        return None
    name = _clean_skill_name(explicit_title.group(1))
    if not name or len(name) < 2:
        return None

    body_match = re.search(r"(?:^|[\s，,。；;\n])(?:内容|步骤|规则|流程|要求)\s*[：:]\s*(.+)", normalized, re.S)
    if not body_match or not body_match.group(1).strip():
        return None
    content = body_match.group(1).strip()
    if len(content) < 10:
        return None

    description = f"由群聊自然语言请求创建：{normalized.splitlines()[0][:80]}"
    target_name = ""
    target_match = SKILL_TARGET_RE.search(normalized)
    if target_match:
        target_name = target_match.group(1).strip(" ：:《》\"'“”`*#")
    return {"name": name, "description": description, "content": content, "target_name": target_name}


def _resolve_skill_targets(db, room_id: str, mentions: list | None, target_name: str = "") -> list:
    members = [m for m in db.get_room_members(room_id) if is_real_agent(m)]
    room = db.get_room(room_id)
    tenant_id = room.get("tenant_id") if room else None
    if tenant_id is not None:
        members = [member for member in members if member.get("tenant_id") == tenant_id]
    if target_name:
        matched = [m for m in members if m.get("name") == target_name]
        if matched:
            return matched
    if mentions:
        mentioned = [m for m in members if m.get("id") in mentions]
        if mentioned:
            return mentioned
    return members


def _handle_natural_language_skill_create(db, room_id: str, text: str, mentions: list | None = None, thread_id: str | None = None) -> dict | None:
    request = _extract_skill_request(text)
    if not request:
        return None
    targets = _resolve_skill_targets(db, room_id, mentions, request.get("target_name", ""))
    if not targets:
        return {"ok": False, "error": "当前群聊没有可装载技能的真实智能体"}
    created = []
    for agent in targets:
        existing = db.get_agent_skills(agent["id"])
        same = next((s for s in existing if (s.get("name") or "").strip() == request["name"]), None)
        if same:
            skill = db.update_skill(same["id"], {
                "description": request["description"],
                "content": request["content"],
                "file_type": "text",
            })
        else:
            skill = db.create_skill(agent["id"], request["name"], request["description"], request["content"], "text")
        db.add_room_skill(room_id, skill["id"])
        created.append({"agent_id": agent["id"], "agent_name": agent["name"], "skill_id": skill["id"], "skill_name": skill["name"]})
    names = "、".join([f"@{item['agent_name']}" for item in created])
    status_text = f"✅ 已创建/更新技能「{request['name']}」，并装载到 {names}。"
    system_message = db.create_message(room_id, "system", status_text, "markdown", None, [], thread_id=thread_id)
    return {"ok": True, "message": system_message, "created": created}




def default_single_agent_mentions(db, room_id: str, mentions: list | None) -> list:
    mentions = list(mentions or [])
    if mentions:
        return mentions
    real_members = [m for m in db.get_room_members(room_id) if is_real_agent(m)]
    return [real_members[0]["id"]] if len(real_members) == 1 else mentions

def resolve_real_mentions(db, text: str, mentions: list | None = None, room_id: str | None = None, tenant_id: str | None = None) -> list:
    visible = db.list_agents(tenant_id)
    if room_id:
        visible.extend(db.get_room_members(room_id))
    agents = {a["id"]: a for a in visible if is_real_agent(a)}
    resolved = []
    for agent_id in mentions or []:
        if agent_id in agents and agent_id not in resolved:
            resolved.append(agent_id)
    if resolved:
        return resolved
    for match in re.finditer(MENTION_RE, text):
        mention_name = match.group(1).strip().strip("*_`~|")
        mentioned = next((a for a in agents.values() if a["name"] == mention_name), None)
        if mentioned and mentioned["id"] not in resolved:
            resolved.append(mentioned["id"])
    return resolved


def is_low_value_collaboration_ack(text: str) -> bool:
    """Detect status-only coordination messages that should not re-trigger agents."""
    normalized = re.sub(r"^\[[^\]]+\]:\s*", "", text or "").strip()
    if not normalized:
        return False
    status_markers = ("用户确认", "用户授权", "授权后", "等待用户", "当前状态保持不变", "状态同步", "基础自测后", "最终验收")
    pause_markers = ("等待", "授权", "确认", "暂停", "不再继续", "不再重复", "后续", "收到", "再 @")
    if any(marker in normalized for marker in status_markers) and any(marker in normalized for marker in pause_markers):
        return True
    return bool(re.search(r"(?:收到|确认)[，。,.\s]*(?:当前|测试侧|状态)|完成.*基础自测后.*再\s*@", normalized))


def get_db(request: Request):
    return request.app.state.db


def get_ws(request: Request):
    return request.app.state.ws_manager



async def _interrupt_matching_streams(ws_manager, room_id: str, mentions: list, thread_id: str | None = None):
    """Interrupt active streams before a new user turn is persisted."""
    for stream_id, stream_info in list(ws_manager.active_streams.items()):
        if stream_info.get("room_id") != room_id:
            continue
        if (stream_info.get("thread_id") or None) != (thread_id or None):
            continue
        agent_id = stream_info.get("agent_id")
        if agent_id in mentions or not mentions:
            await ws_manager.interrupt_stream(stream_id)


def tenant_id_for_request(request: Request) -> str | None:
    return current_tenant_id(request)


def require_admin_account(request: Request):
    if not is_admin_account(request):
        return JSONResponse({"ok": False, "error": "子账号不能修改系统配置"}, status_code=403)
    return None


def sanitize_model_config_for_tenant(config: dict, tenant_id: str | None) -> dict:
    """Hide administrator/global provider endpoint and key from sub-accounts.

    Tenant-created providers may show their own base_url for editing, but API keys
    are never returned to the browser after creation.
    """
    item = dict(config)
    item["api_key"] = ""
    owner = item.get("tenant_id")
    if tenant_id is not None and owner != tenant_id:
        item.pop("params_json", None)
        item["name"] = item.get("model") or item.get("name") or "默认模型"
        item["base_url"] = ""
        item["readonly"] = True
    return item


def ensure_model_config_write_access(db, model_id: str, request: Request):
    config = db.get_model_config(model_id)
    if not config:
        return None, JSONResponse({"ok": False, "error": "Model not found"}, status_code=404)
    if is_admin_account(request):
        return config, None
    tenant_id = tenant_id_for_request(request)
    if tenant_id is not None and config.get("tenant_id") == tenant_id:
        return config, None
    return None, JSONResponse({"ok": False, "error": "只能修改自己新增的模型配置"}, status_code=403)


def ensure_tenant_room_access(db, room_id: str, tenant_id: str | None) -> bool:
    if tenant_id is None:
        return True
    db.ensure_tenant_columns()
    room = db.get_room(room_id)
    return bool(room and room.get("tenant_id") == tenant_id)


def ensure_tenant_agent_access(db, agent_id: str, tenant_id: str | None) -> bool:
    if tenant_id is None:
        return True
    db.ensure_tenant_columns()
    agent = db.get_agent_by_id(agent_id)
    return bool(agent and agent.get("tenant_id") == tenant_id)


def ensure_tenant_thread_access(db, thread_id: str, tenant_id: str | None) -> dict | None:
    thread = db.get_thread(thread_id)
    if not thread:
        return None
    if not ensure_tenant_room_access(db, thread.get("room_id"), tenant_id):
        return None
    return thread


def ensure_tenant_workflow_access(db, workflow_id: str, tenant_id: str | None) -> dict | None:
    workflow = db.get_workflow(workflow_id)
    if not workflow:
        return None
    if not ensure_tenant_room_access(db, workflow.get("room_id"), tenant_id):
        return None
    return workflow


def ensure_tenant_skill_access(db, skill_id: str, tenant_id: str | None) -> dict | None:
    skill = db.get_skill_by_id(skill_id)
    if not skill:
        return None
    if not ensure_tenant_agent_access(db, skill.get("agent_id"), tenant_id):
        return None
    return skill


def filter_tenant_members(db, members: list, tenant_id: str | None) -> list:
    if tenant_id is None:
        return members
    return [m for m in members if m.get("tenant_id") == tenant_id]

# === Auth middleware (via dependency) ===
async def check_auth(request: Request):
    secret = os.environ.get("SECRET_KEY", "")
    if not secret or secret == "change-me-to-a-random-string":
        return True
    auth = request.headers.get("authorization", "")
    if auth != f"Bearer {secret}":
        return False
    return True


# === Agents ===

@router.get("/agents")
async def list_agents(request: Request):
    db = get_db(request)
    agents = [agent for agent in db.list_agents(tenant_id_for_request(request)) if is_real_agent(agent)]
    return {"ok": True, "result": agents}


@router.post("/agents")
async def create_agent(request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    body = await request.json()
    name = body.get("name")
    if not name:
        return JSONResponse({"ok": False, "error": "name is required"}, status_code=400)
    model_config_id = body.get("model_config_id") or None
    if model_config_id and not db.get_model_config(model_config_id):
        return JSONResponse({"ok": False, "error": "model_config_id is invalid"}, status_code=400)
    agent = db.create_agent(name, body.get("description", ""), model_config_id, tenant_id)
    return {"ok": True, "result": agent}


@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    if not ensure_tenant_agent_access(db, agent_id, tenant_id):
        return JSONResponse({"ok": False, "error": "Agent not found"}, status_code=404)
    body = await request.json()
    if tenant_id is not None:
        for forbidden_key in ["status", "model_config_id", "execution_mode", "self_improve", "self_improve_threshold", "tools_config", "container_id", "sort_order"]:
            body.pop(forbidden_key, None)
    name = body.get("name")
    if not name:
        return JSONResponse({"ok": False, "error": "name is required"}, status_code=400)
    fields = {"name": name, "description": body.get("description", "")}
    for key in ["status", "model_config_id", "execution_mode", "self_improve",
                "self_improve_threshold", "tools_config"]:
        if key in body:
            val = body[key]
            if key == "self_improve":
                val = 1 if val else 0
            if key == "tools_config" and not isinstance(val, str):
                val = json.dumps(val)
            fields[key] = val
    if "container_id" in body:
        fields["container_id"] = str(body.get("container_id") or "").strip() or None
    elif "sort_order" in body:
        fields["container_id"] = str(body["sort_order"])
    db.update_agent(agent_id, fields)
    return {"ok": True}


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, request: Request):
    # Protect system agents from deletion
    if agent_id in ('__system__', 'user', 'system'):
        return JSONResponse({"ok": False, "error": "系统智能体不可删除"}, status_code=403)
    db = get_db(request)
    if not ensure_tenant_agent_access(db, agent_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Agent not found"}, status_code=404)
    db.delete_agent(agent_id)
    return {"ok": True}


# === Rooms ===

@router.get("/rooms")
async def list_rooms(request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    room_type = request.query_params.get("type")
    rooms = db.list_rooms(tenant_id, room_type)
    if not rooms:
        return {"ok": True, "result": []}

    room_ids = [r["id"] for r in rooms]
    members_by_room = db.get_room_members_for_rooms(room_ids)
    last_messages_by_room = db.get_last_messages_for_rooms(room_ids)
    result = []
    for r in rooms:
        room_settings = {}
        try:
            room_settings = json.loads(r.get("settings_json") or "{}")
        except Exception:
            room_settings = {}
        workspace_info = {}
        try:
            workspace_info = get_room_workspace_info(r["id"], room_settings)
        except Exception as e:
            workspace_info = {"workspace_error": str(e)}
        result.append({
            **r,
            "members": members_by_room.get(r["id"], []),
            "last_message": last_messages_by_room.get(r["id"]),
            **workspace_info,
        })
    return {"ok": True, "result": result}


@router.post("/rooms")
async def create_room(request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    body = await request.json()
    name = body.get("name")
    if not name:
        return JSONResponse({"ok": False, "error": "name is required"}, status_code=400)
    room = db.create_room(name, body.get("description", ""), body.get("type", "group"), tenant_id)
    return {"ok": True, "result": room}

@router.post("/collaboration/planning-room")
async def create_collaboration_planning_room(request: Request):
    """Create an isolated room where the default orchestrator plans one task."""
    db = get_db(request)
    db.ensure_system_agents()
    tenant_id = tenant_id_for_request(request)
    orchestrator = _account_orchestrator(db, tenant_id)
    if not is_real_agent(orchestrator):
        return JSONResponse({"ok": False, "error": "Default orchestrator is not configured"}, status_code=400)
    orchestrator_id = orchestrator["id"]
    body = await request.json()
    initial_task = _clean_assistant_text(body.get("task") or "")
    project_id = str(body.get('project_id') or '')
    if project_id:
        if not ensure_tenant_room_access(db, project_id, tenant_id) or not db.get_room(project_id) or not db.get_room_settings(project_id).get('is_project'):
            return JSONResponse({'ok': False, 'error': 'Project not found'}, status_code=404)
    room_name = _compact_task_name(initial_task) if initial_task else "新任务"
    room = db.create_room(room_name, initial_task[:500], "group", tenant_id)
    db.add_member(room["id"], "user", "owner")
    db.add_member(room["id"], orchestrator_id, "coordinator")
    db.update_room_settings(room["id"], {
        "collaboration_mode": "guided" if body.get("mode") == "work" else "manual",
        "is_project": False,
        "is_chat": bool(body.get("is_chat")),
        "execution_mode": "work" if body.get("mode") == "work" else "chat",
        "project_id": project_id or None,
        "planning_orchestrator_id": orchestrator_id,
        "room_guide": f"群聊目标：{initial_task[:500]}" if initial_task else "",
    })
    room["members"] = db.get_room_members(room["id"])
    return {"ok": True, "result": room}




@router.get("/search")
async def search_messages(request: Request, q: str = "", room_id: str = "", limit: int = 50):
    """Full-text search over chat messages (LIKE-based, Chinese friendly)."""
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    q = (q or "").strip()
    if len(q) < 2:
        return {"ok": True, "result": []}
    limit = max(1, min(int(limit or 50), 100))
    esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    ph = db._placeholder()
    like = f"%{esc}%"
    sql = f"""
        SELECT m.id, m.room_id, r.name AS room_name, m.sender_id,
               COALESCE(NULLIF(a.name, ''), CASE m.sender_id WHEN 'user' THEN '用户' ELSE '助手' END) AS sender_name,
               m.text, m.created_at, r.tenant_id AS room_tenant
        FROM messages m
        JOIN rooms r ON r.id = m.room_id
        LEFT JOIN agents a ON a.id = m.sender_id
        WHERE m.text LIKE {ph} ESCAPE '\\' COLLATE NOCASE
    """
    params = [like]
    if room_id:
        sql += f" AND m.room_id = {ph}"
        params.append(room_id)
    if tenant_id is not None:
        sql += f" AND r.tenant_id = {ph}"
        params.append(tenant_id)
    sql += f" ORDER BY m.id DESC LIMIT {limit}"
    rows = db.fetchall(sql, params)

    def snippet(text):
        t = str(text or "")
        low = t.lower()
        pos = low.find(q.lower())
        if pos == -1:
            return t[:160]
        start = max(0, pos - 60)
        end = min(len(t), pos + len(q) + 80)
        return (("…" if start > 0 else "") + t[start:end] + ("…" if end < len(t) else ""))

    result = [{
        "id": r_["id"], "room_id": r_["room_id"], "room_name": r_["room_name"],
        "sender_name": r_["sender_name"], "created_at": r_["created_at"],
        "snippet": snippet(r_["text"]),
    } for r_ in rows]
    return {"ok": True, "result": result}

@router.post("/collaboration/projects")
async def create_project_from_proposal(request: Request):
    """Create a new project room with isolated context and collaboration agents."""
    db = get_db(request)
    db.ensure_system_agents()
    tenant_id = tenant_id_for_request(request)
    body = await request.json()

    project_name = (body.get("project_name") or "").strip()
    summary = (body.get("summary") or "").strip()
    roles = body.get("roles") or []

    if not project_name:
        return JSONResponse({"ok": False, "error": "project_name is required"}, status_code=400)
    if not roles:
        return JSONResponse({"ok": False, "error": "At least one role is required"}, status_code=400)

    if (not isinstance(roles, list) or len(roles) > 30 or
            any(not isinstance(role, dict) or not isinstance(role.get("name"), str) or
                not role["name"].strip() or not isinstance(role.get("responsibility", ""), str)
                for role in roles)):
        return JSONResponse({"ok": False, "error": "Invalid project roles"}, status_code=400)
    orchestrator = _account_orchestrator(db, tenant_id)
    if not is_real_agent(orchestrator):
        return JSONResponse({"ok": False, "error": "Orchestrator agent is not configured"}, status_code=400)

    room = db.create_room(project_name, summary or f"项目：{project_name}", "group", tenant_id)
    room_id = room["id"]

    db.add_member(room_id, "user", "owner")
    db.add_member(room_id, orchestrator["id"], "coordinator")

    created_agents = []
    for role in roles:
        role_name = (role.get("name") or "").strip()
        role_resp = (role.get("responsibility") or "").strip()
        if not role_name:
            continue
        agent = db.create_agent(role_name, role_resp or f"项目角色：{role_name}", None, tenant_id)
        db.add_member(room_id, agent["id"], "member")
        created_agents.append(agent["id"])

    role_lines = []
    for role in roles:
        rname = (role.get("name") or "").strip()
        rresp = (role.get("responsibility") or "").strip()
        if rname:
            role_lines.append(f"- @{rname}：{rresp}")
    roles_text = "\n".join(role_lines)

    settings = {
        "collaboration_mode": "guided",
        "planning_orchestrator_id": orchestrator["id"],
        "is_project": True,
        "project_name": project_name,
        "project_summary": summary[:1000] if summary else "",
    }
    db.update_room_settings(room_id, settings)

    kickoff = (
        f"项目「{project_name}」启动。目标：{summary}\n"
        f"新增协作智能体：\n{roles_text}\n\n"
        f"@{orchestrator['name']} 请按分工协调各智能体，直接开始工作。"
    )
    ws_manager = get_ws(request)
    sys_msg = db.create_message(room_id, "system", kickoff, "markdown", None, [])
    await ws_manager.notify_ui({"type": "new_message", "room_id": room_id, "message": sys_msg})

    from ai_engine import process_message
    async def _trigger():
        try:
            await process_message(db, ws_manager, room_id, "user", kickoff, [orchestrator["id"]], "group")
        except Exception as e:
            print(f"[Project] Trigger error: {e}")
    asyncio.create_task(_trigger())

    room["members"] = db.get_room_members(room_id)
    return {"ok": True, "result": {"room": room, "createdCount": len(created_agents), "sameRoom": False}}

@router.get('/projects/{room_id}/files')
async def list_project_files(room_id: str, request: Request):
    from urllib.parse import quote
    from workspaces import safe_room_workspace_name
    db = get_db(request)
    if not ensure_tenant_room_access(db, room_id, tenant_id_for_request(request)):
        return JSONResponse({'ok': False, 'error': 'Project not found'}, status_code=404)
    room = db.get_room(room_id)
    if not room:
        return JSONResponse({'ok': False, 'error': 'Project not found'}, status_code=404)
    settings = db.get_room_settings(room_id) or {}
    if not settings.get('is_project'):
        return JSONResponse({'ok': False, 'error': 'Project not found'}, status_code=404)
    root = (APP_ROOT / 'data' / 'workspaces').resolve()
    legacy = root / ('room-' + re.sub(r'[^a-zA-Z0-9_.-]', '_', room_id)[:80])
    folder = root / safe_room_workspace_name(room_id)
    if legacy.exists() and not folder.exists(): folder = legacy
    if settings.get('workspace_path'): folder = Path(settings['workspace_path']).expanduser()
    folder = folder.resolve()
    if not folder.is_relative_to(root):
        return JSONResponse({'ok': False, 'error': '首页暂不支持浏览外部绑定目录，请进入项目查看'}, status_code=400)
    files = []
    allowed = {'.docx', '.xlsx', '.xlsm', '.pptx', '.md', '.markdown', '.pdf'}
    if folder.is_dir():
        for current, dirs, names in os.walk(folder, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not d.startswith('.') and not (Path(current) / d).is_symlink())
            for name in sorted(names):
                item = Path(current) / name
                if name.startswith('.') or item.suffix.lower() not in allowed or item.is_symlink(): continue
                resolved = item.resolve()
                if not resolved.is_relative_to(folder) or not resolved.is_file(): continue
                relative = resolved.relative_to(root).as_posix()
                files.append({'name': item.relative_to(folder).as_posix(), 'path': relative, 'url': '/media/workspaces/' + quote(relative, safe='/'), 'size': resolved.stat().st_size})
                if len(files) >= 200:
                    return {'ok': True, 'result': {'files': files, 'truncated': True}}
    return {'ok': True, 'result': {'files': files, 'truncated': False}}


@router.get('/projects/{project_id}/tasks')
async def project_tasks(project_id: str, request: Request):
    db = get_db(request)
    if not ensure_tenant_room_access(db, project_id, tenant_id_for_request(request)):
        return JSONResponse({'ok': False, 'error': 'Project not found'}, status_code=404)
    project = db.get_room(project_id)
    if not project or not db.get_room_settings(project_id).get('is_project'):
        return JSONResponse({'ok': False, 'error': 'Project not found'}, status_code=404)
    tasks = [room for room in db.list_rooms(tenant_id_for_request(request), room_type='group') if db.get_room_settings(room['id']).get('project_id') == project_id]
    # Existing project conversations remain accessible without moving their history.
    if db.get_room_messages(project_id, 1):
        tasks.insert(0, {**project, 'name': '初始任务'})
    return {'ok': True, 'result': tasks}


@router.post('/rooms/{room_id}/project')
async def move_conversation_to_project(room_id: str, request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    body = await request.json()
    project_id = body.get('project_id')
    if not isinstance(project_id, str) or not project_id:
        return JSONResponse({'ok': False, 'error': '请选择已有项目'}, status_code=400)
    if not ensure_tenant_room_access(db, room_id, tenant_id) or not ensure_tenant_room_access(db, project_id, tenant_id):
        return JSONResponse({'ok': False, 'error': '对话或项目不存在'}, status_code=404)
    room, project = db.get_room(room_id), db.get_room(project_id)
    if not room or not project or not db.get_room_settings(project_id).get('is_project'):
        return JSONResponse({'ok': False, 'error': '对话或项目不存在'}, status_code=404)
    if room_id == project_id or db.get_room_settings(room_id).get('is_project'):
        return JSONResponse({'ok': False, 'error': '项目本身不能作为对话移动'}, status_code=400)
    # Only organization changes; message history, members, files and pinned state remain untouched.
    db.update_room_settings(room_id, {'project_id': project_id})
    return {'ok': True, 'result': {'room_id': room_id, 'project_id': project_id}}


@router.post('/projects')
async def create_empty_project(request: Request):
    db = get_db(request)
    body = await request.json()
    name = body.get('name')
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        return JSONResponse({'ok': False, 'error': '项目名称需要为 1 到 100 个字符'}, status_code=400)
    room = db.create_room(name.strip(), '', 'group', tenant_id_for_request(request))
    db.update_room_settings(room['id'], {'is_project': True})
    return {'ok': True, 'result': {**room, 'member_count': 0, 'last_message': None}}


@router.get("/projects")
async def list_projects(request: Request):
    """List all project rooms for the current tenant."""
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    rooms = db.list_rooms(tenant_id, room_type="group")
    projects = []
    for room in rooms:
        settings = db.get_room_settings(room["id"]) or {}
        if not settings.get("is_project"):
            continue
        members = db.get_room_members(room["id"])
        last_msgs = db.get_room_messages(room["id"], limit=1)
        last_msg = last_msgs[0] if last_msgs else None
        projects.append({
            "id": room["id"],
            "name": room.get("name") or settings.get("project_name", ""),
            "summary": settings.get("project_summary", ""),
            "created_at": room.get("created_at", ""),
            "member_count": len([m for m in members if m.get("id") != "user"]),
            "last_message": last_msg,
        })
    projects.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    return {"ok": True, "result": projects}

@router.post("/rooms/{room_id}/share")
async def create_room_share(room_id: str, request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    if not ensure_tenant_room_access(db, room_id, tenant_id):
        return JSONResponse({"ok": False, "error": "Room not found"}, status_code=404)
    room = db.get_room(room_id)
    body = await request.json()
    requested_ids = body.get("message_ids") or []
    allowed_ids = {int(item) for item in requested_ids if str(item).isdigit()}
    messages = db.get_all_room_messages(room_id)
    if allowed_ids:
        messages = [message for message in messages if int(message.get("id") or 0) in allowed_ids]
    messages = messages[-300:]
    safe_messages = [{
        "sender_id": "user" if message.get("sender_id") == "user" else ("system" if message.get("sender_id") == "system" else "assistant"),
        "sender_name": message.get("sender_name") or ("用户" if message.get("sender_id") == "user" else "助手"),
        "text": str(message.get("text") or "")[:100000],
        "created_at": message.get("created_at"),
    } for message in messages]
    if not safe_messages:
        return JSONResponse({"ok": False, "error": "当前没有可分享的聊天内容"}, status_code=400)
    token = secrets.token_urlsafe(32)
    snapshot = {
        "version": 1,
        "title": room.get("name") or "Myna 对话",
        "description": room.get("description") or "",
        "messages": safe_messages,
        "created_at": datetime.now().isoformat(),
    }
    path = _share_file(token)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return {"ok": True, "result": {"token": token, "url": f"/share/{token}"}}


@router.post("/shares/{token}/continue")
async def continue_shared_room(token: str, request: Request):
    try:
        snapshot = json.loads(_share_file(token).read_text("utf-8"))
    except (ValueError, FileNotFoundError, json.JSONDecodeError):
        return JSONResponse({"ok": False, "error": "分享不存在或已失效"}, status_code=404)
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    orchestrator = _account_orchestrator(db, tenant_id)
    if not is_real_agent(orchestrator):
        return JSONResponse({"ok": False, "error": "当前账号未配置马哥"}, status_code=400)
    title = _compact_task_name(snapshot.get("title") or "分享续聊")
    room = db.create_room(f"续聊-{title}"[:30], f"来自分享快照：{snapshot.get('title', '')}"[:500], "group", tenant_id)
    db.add_member(room["id"], "user", "owner")
    db.add_member(room["id"], orchestrator["id"], "coordinator")
    context_lines = []
    for message in snapshot.get("messages", [])[-80:]:
        name = message.get("sender_name") or ("用户" if message.get("sender_id") == "user" else "助手")
        context_lines.append(f"[{name}] {str(message.get('text') or '')[:2000]}")
    context = "以下内容来自用户主动打开的只读分享快照，仅作为当前账号续聊背景：\n\n" + "\n\n".join(context_lines)
    db.create_message(room["id"], "system", f"已载入分享快照「{snapshot.get('title', 'Myna 对话')}」。你可以直接向本账号的马哥继续提问。", "markdown", None, [])
    db.update_room_settings(room["id"], {
        "collaboration_mode": "guided",
        "planning_orchestrator_id": orchestrator["id"],
        "room_guide": f"围绕分享内容继续对话：{snapshot.get('title', '')}"[:500],
        "share_source_token": token,
        "shared_context": context[:60000],
    })
    room["members"] = db.get_room_members(room["id"])
    return {"ok": True, "result": room}


@router.put("/rooms/{room_id}")
async def update_room(room_id: str, request: Request):
    db = get_db(request)
    body = await request.json()
    if not ensure_tenant_room_access(db, room_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Room not found"}, status_code=404)
    room = db.get_room(room_id)
    if not room:
        return JSONResponse({"ok": False, "error": "Room not found"}, status_code=404)
    if "settings_json" in body:
        settings = body["settings_json"]
        if isinstance(settings, str):
            settings = json.loads(settings)
        workspace_path = str(settings.get("workspace_path") or "").strip()
        if workspace_path:
            expanded = os.path.expanduser(workspace_path)
            if not os.path.isabs(expanded):
                return JSONResponse({"ok": False, "error": "workspace_path must be an absolute path"}, status_code=400)
            settings["workspace_path"] = expanded
        else:
            settings["workspace_path"] = ""
        db.update_room_settings(room_id, settings)
    sets = []
    vals = []
    if "name" in body:
        sets.append(f"name = {db._placeholder()}"); vals.append(body["name"])
    if "description" in body:
        sets.append(f"description = {db._placeholder()}"); vals.append(body["description"])
    if sets:
        vals.append(room_id)
        db.execute(f"UPDATE rooms SET {', '.join(sets)} WHERE id = {db._placeholder()}", vals)
        db.commit()
    return {"ok": True}



def _purge_room_storage(db, room_id: str):
    """Remove server-side artifacts belonging to a deleted room."""
    import shutil
    ws_root = (APP_ROOT / "data" / "workspaces")
    for prefix in (f"room-{room_id[:8]}", f"room-{room_id}"):
        p = ws_root / prefix
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
    try:
        rows = db.fetchall(f"SELECT text FROM messages WHERE room_id = {db._placeholder()}", (room_id,))
    except Exception:
        rows = []
    import re as _re
    refs = set()
    for row in rows or []:
        for mch in _re.finditer(r"/uploads/[^\s)\]，。；]+", str(row.get("text") or "")):
            refs.add(mch.group(0).rstrip('.,;'))
    uploads_root = (APP_ROOT / "data" / "uploads").resolve()
    for ref in refs:
        try:
            rel = ref.split("/uploads/", 1)[1]
            cand = (uploads_root / rel).resolve()
            if uploads_root in cand.parents and cand.is_file():
                other = db.fetchone(
                    f"SELECT id FROM messages WHERE room_id != {db._placeholder()} AND text LIKE {db._placeholder()} LIMIT 1",
                    (room_id, f"%{ref}%"),
                )
                if not other:
                    cand.unlink(missing_ok=True)
        except Exception:
            pass

@router.delete("/rooms/{room_id}")
async def delete_room(room_id: str, request: Request):
    db = get_db(request)
    if not ensure_tenant_room_access(db, room_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Room not found"}, status_code=404)
    _purge_room_storage(db, room_id)
    db.delete_room(room_id)
    return {"ok": True}



def _workspace_file_path(raw_path: str):
    from urllib.parse import unquote
    raw = unquote(str(raw_path or '').strip())
    marker = '/data/workspaces/'
    if marker in raw:
        raw = raw.split(marker, 1)[1]
    root = (APP_ROOT / 'data' / 'workspaces').resolve()
    candidate = (root / raw.lstrip('/')).resolve()
    if not raw or not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return candidate


def _authorized_workspace_file(request, raw):
    from workspaces import safe_room_workspace_name
    file_path = _workspace_file_path(raw)
    if not file_path or not is_authenticated(request):
        return None
    db = get_db(request)
    root = (APP_ROOT / 'data' / 'workspaces').resolve()
    for room in db.list_rooms(tenant_id_for_request(request)):
        settings = db.get_room_settings(room['id']) or {}
        legacy = root / ('room-' + re.sub(r'[^a-zA-Z0-9_.-]', '_', room['id'])[:80])
        bases = [root / safe_room_workspace_name(room['id']), legacy]
        if settings.get('workspace_path'):
            bases.append(Path(settings['workspace_path']).expanduser().resolve())
        if any(file_path.is_relative_to(base.resolve()) for base in bases):
            return file_path
    return None


_office_lock = threading.Lock()


def _office_data(data, kind):
    import io
    from fastapi.encoders import jsonable_encoder
    if kind in ('md', 'txt'):
        return {'content': data.decode('utf-8')}
    if kind == 'pdf':
        import fitz
        with fitz.open(stream=data, filetype='pdf') as doc:
            if doc.needs_pass: raise ValueError('Password-protected PDF cannot be edited')
            return {'page_count': doc.page_count}
    if kind == 'docx':
        from docx import Document
        return {'paragraphs': [{'text': p.text} for p in Document(io.BytesIO(data)).paragraphs]}
    if kind == 'xlsx':
        from openpyxl import load_workbook
        book = load_workbook(io.BytesIO(data), read_only=True, data_only=False)
        try:
            sheet = book.worksheets[0]
            if sheet.max_column > 200 or sheet.max_row > 1000:
                raise ValueError('Basic editor supports up to 1000 rows and 200 columns; use Office for larger sheets')
            return {'rows': jsonable_encoder([[c.value if c.value is not None else '' for c in row] for row in sheet.iter_rows()])}
        finally:
            book.close()
    if kind == 'pptx':
        from pptx import Presentation
        deck = Presentation(io.BytesIO(data))
        return {'slides': [{'shapes': [{'text': shape.text} for shape in slide.shapes if shape.has_text_frame]} for slide in deck.slides]}
    raise ValueError('Unsupported document type')


@router.get('/workspace/office')
async def read_workspace_office(request: Request, path: str = '', kind: str = ''):
    import hashlib
    file_path = _authorized_workspace_file(request, path)
    if not file_path:
        return JSONResponse({'ok': False, 'error': 'File not found or access denied'}, status_code=404)
    expected = {'.docx': 'docx', '.xlsx': 'xlsx', '.xlsm': 'xlsx', '.pptx': 'pptx', '.md': 'md', '.markdown': 'md', '.txt': 'txt', '.pdf': 'pdf'}
    if expected.get(file_path.suffix.lower()) != kind:
        return JSONResponse({'ok': False, 'error': 'Unsupported document type'}, status_code=400)
    try:
        if file_path.stat().st_size > 20 * 1024 * 1024:
            raise ValueError('Document exceeds 20 MB editor limit')
        data = file_path.read_bytes()
        result = _office_data(data, kind)
        result['revision'] = hashlib.sha256(data).hexdigest()
        return {'ok': True, 'result': result}
    except Exception as exc:
        return JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)


def _replace_plain_paragraph(paragraph, text, ppt=False):
    if paragraph.text == text:
        return
    runs = paragraph.runs
    if len(runs) > 1:
        raise ValueError('This paragraph has mixed formatting; edit it in Office to preserve formatting')
    if not ppt:
        from docx.oxml.ns import qn
        allowed = {qn('w:pPr'), qn('w:r')}
        if any(child.tag not in allowed for child in paragraph._p):
            raise ValueError('Complex paragraph cannot be safely edited here')
        if runs and any(child.tag not in {qn('w:rPr'), qn('w:t')} for child in runs[0]._r):
            raise ValueError('Paragraph contains non-text objects; edit in Office')
    if runs:
        runs[0].text = text
    elif ppt:
        paragraph.add_run().text = text
    else:
        paragraph.add_run(text)


@router.post('/workspace/office')
@router.post('/workspace/file')
async def write_workspace_office(request: Request):
    import io, hashlib, tempfile
    body = await request.json()
    path = _authorized_workspace_file(request, body.get('path'))
    if not path:
        return JSONResponse({'ok': False, 'error': 'File not found or access denied'}, status_code=404)
    kind = {'.docx': 'docx', '.xlsx': 'xlsx', '.xlsm': 'xlsx', '.pptx': 'pptx', '.md': 'md', '.markdown': 'md', '.txt': 'txt', '.pdf': 'pdf'}.get(path.suffix.lower())
    if not kind or body.get('kind', kind) != kind:
        return JSONResponse({'ok': False, 'error': 'Unsupported document type'}, status_code=400)
    if not body.get('revision'):
        return JSONResponse({'ok': False, 'error': 'Reload document before saving; revision required'}, status_code=409)
    with _office_lock:
        original = path.read_bytes()
        revision = hashlib.sha256(original).hexdigest()
        if revision != body['revision']:
            return JSONResponse({'ok': False, 'error': 'File changed by another editor. Keep your draft and reopen to reconcile changes.'}, status_code=409)
        try:
            current = _office_data(original, kind)
            output = io.BytesIO()
            if kind in ('md', 'txt'):
                if not isinstance(body.get('content'), str):
                    raise ValueError('Text content required')
                output.write(body['content'].encode('utf-8'))
            elif kind == 'pdf':
                import fitz
                annotation = body.get('annotation') or {}
                text = annotation.get('text', '')
                page_number = annotation.get('page')
                if not isinstance(text, str) or not text.strip() or len(text) > 4000:
                    raise ValueError('Enter a text note (up to 4000 characters)')
                if not isinstance(page_number, int) or not 1 <= page_number <= current['page_count']:
                    raise ValueError('Invalid PDF page number')
                with fitz.open(stream=original, filetype='pdf') as doc:
                    if not doc.permissions & fitz.PDF_PERM_ANNOTATE:
                        raise ValueError('This PDF does not permit annotations')
                    page = doc[page_number - 1]
                    point = fitz.Point(page.rect.x0 + 20, page.rect.y0 + 20)
                    page.add_text_annot(point, text.strip())
                    output.write(doc.tobytes())
            elif kind == 'docx':
                from docx import Document
                doc = Document(io.BytesIO(original))
                items = body.get('paragraphs')
                if not isinstance(items, list) or len(items) != len(doc.paragraphs):
                    raise ValueError('Document structure mismatch')
                for paragraph, item in zip(doc.paragraphs, items):
                    if not isinstance(item.get('text'), str): raise ValueError('Text required')
                    _replace_plain_paragraph(paragraph, item['text'])
                doc.save(output)
            elif kind == 'pptx':
                from pptx import Presentation
                deck = Presentation(io.BytesIO(original))
                items = body.get('slides')
                if not isinstance(items, list) or len(items) != len(deck.slides): raise ValueError('Slide structure mismatch')
                for slide, item in zip(deck.slides, items):
                    shapes = [shape for shape in slide.shapes if shape.has_text_frame]
                    values = item.get('shapes', [])
                    if len(values) != len(shapes): raise ValueError('Shape structure mismatch')
                    for shape, value in zip(shapes, values):
                        text = value.get('text')
                        if not isinstance(text, str): raise ValueError('Text required')
                        if shape.text == text: continue
                        parts = text.split('\n')
                        if len(parts) != len(shape.text_frame.paragraphs): raise ValueError('Paragraph structure change requires Office')
                        for paragraph, part in zip(shape.text_frame.paragraphs, parts):
                            _replace_plain_paragraph(paragraph, part, ppt=True)
                deck.save(output)
            else:
                from openpyxl import load_workbook
                from openpyxl.cell.cell import MergedCell
                book = load_workbook(io.BytesIO(original), keep_vba=path.suffix.lower() == '.xlsm')
                try:
                    rows = body.get('rows')
                    old = current['rows']
                    if not isinstance(rows, list) or len(rows) != len(old): raise ValueError('Sheet structure mismatch')
                    for ri, row in enumerate(rows):
                        if not isinstance(row, list) or len(row) != len(old[ri]): raise ValueError('Row structure mismatch')
                        for ci, value in enumerate(row):
                            if value == old[ri][ci]: continue
                            cell = book.worksheets[0].cell(ri + 1, ci + 1)
                            if isinstance(cell, MergedCell): raise ValueError('Only the first cell of a merged region is editable')
                            if isinstance(value, str) and cell.data_type == 'n' and value.strip():
                                try: value = float(value)
                                except ValueError: pass
                            if cell.is_date and value not in ('', None):
                                from datetime import datetime
                                value = datetime.fromisoformat(str(value))
                            cell.value = None if value == '' else value
                    book.save(output)
                finally:
                    book.close()
            data = output.getvalue()
            if hashlib.sha256(path.read_bytes()).hexdigest() != revision:
                return JSONResponse({'ok': False, 'error': 'File changed during save; reload and reconcile'}, status_code=409)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.myna-save-', delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(temporary, path.stat().st_mode)
                os.replace(temporary, path)
            finally:
                if temporary and temporary.exists(): temporary.unlink()
            return {'ok': True, 'result': {'revision': hashlib.sha256(data).hexdigest()}}
        except Exception as exc:
            return JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)


# Room members
@router.post("/rooms/{room_id}/members")
async def add_members(room_id: str, request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    if not ensure_tenant_room_access(db, room_id, tenant_id):
        return JSONResponse({"ok": False, "error": "Room not found"}, status_code=404)
    body = await request.json()
    agent_ids = body.get("agent_ids") or ([body["agent_id"]] if body.get("agent_id") else [])
    if not agent_ids:
        return JSONResponse({"ok": False, "error": "agent_id or agent_ids required"}, status_code=400)
    for aid in agent_ids:
        agent = db.get_agent_by_id(aid)
        if tenant_id is not None and (not agent or agent.get("tenant_id") != tenant_id):
            return JSONResponse({"ok": False, "error": f"Invalid agent: {aid}"}, status_code=400)
        if not is_real_agent(agent):
            return JSONResponse({"ok": False, "error": f"Invalid agent: {aid}"}, status_code=400)
        db.add_member(room_id, aid, body.get("role", "member"))
    return {"ok": True, "added": len(agent_ids)}


@router.delete("/rooms/{room_id}/members/{agent_id}")
async def remove_member(room_id: str, agent_id: str, request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    if not ensure_tenant_room_access(db, room_id, tenant_id) or not ensure_tenant_agent_access(db, agent_id, tenant_id):
        return JSONResponse({"ok": False, "error": "Room or agent not found"}, status_code=404)
    db.remove_member(room_id, agent_id)
    return {"ok": True}


# Room messages
@router.get("/rooms/{room_id}/messages")
async def get_room_messages(room_id: str, request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    if not ensure_tenant_room_access(db, room_id, tenant_id):
        return JSONResponse({"ok": False, "error": "Room not found"}, status_code=404)
    limit = int(request.query_params.get("limit", "50"))
    before_id = request.query_params.get("before_id")
    q = request.query_params.get("q")
    order = request.query_params.get("order", "desc")
    if q:
        messages = db.get_room_history(
            room_id,
            limit,
            int(before_id) if before_id else None,
            order=order,
            q=q,
        )
    else:
        messages = db.get_room_messages(room_id, limit, int(before_id) if before_id else None)
    return {"ok": True, "result": messages}


def _assistant_pref_key(request: Request) -> str:
    return 'assistant_name:' + str(tenant_id_for_request(request) or 'admin')


@router.get('/personal-assistant/preferences')
async def get_personal_assistant_preferences(request: Request):
    name = get_db(request).get_hub_setting(_assistant_pref_key(request), '') or ''
    return {'ok': True, 'result': {'name': name}}


@router.put('/personal-assistant/preferences')
async def set_personal_assistant_preferences(request: Request):
    body = await request.json()
    name = body.get('name')
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 30:
        return JSONResponse({'ok': False, 'error': '名称需要为 1 到 30 个字符'}, status_code=400)
    get_db(request).set_hub_setting(_assistant_pref_key(request), name.strip())
    return {'ok': True, 'result': {'name': name.strip()}}


@router.get("/personal-assistant/topics")
async def get_personal_assistant_topics(request: Request):
    """Return keywords derived only from the current account's recent chats."""
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    if tenant_id is None:
        ph = db._placeholder()
        rooms = db.fetchall("SELECT * FROM rooms WHERE tenant_id IS NULL ORDER BY created_at DESC LIMIT 30")
    else:
        rooms = db.list_rooms(tenant_id)[:30]
    messages = []
    for room in rooms:
        messages.extend(db.get_room_messages(room["id"], 30))
    messages.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    topics = _history_keywords(messages[:300])
    return {"ok": True, "result": {"topics": topics, "message_count": min(len(messages), 300)}}


@router.delete("/rooms/{room_id}/messages")
async def clear_room_messages(room_id: str, request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    if not ensure_tenant_room_access(db, room_id, tenant_id):
        return JSONResponse({"ok": False, "error": "Room not found"}, status_code=404)
    db.clear_room_messages(room_id)
    return {"ok": True}


# Message edit/delete
@router.patch("/messages/{message_id}")
async def update_message(message_id: int, request: Request):
    db = get_db(request)
    message = db.get_message_by_id(message_id)
    if not message:
        return JSONResponse({"ok": False, "error": "Message not found"}, status_code=404)
    if not ensure_tenant_room_access(db, message.get("room_id"), tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Message not found"}, status_code=404)
    body = await request.json()
    text = body.get("text")
    if not text:
        return JSONResponse({"ok": False, "error": "text is required"}, status_code=400)
    db.update_message(message_id, text)
    return {"ok": True}


@router.delete("/messages/{message_id}")
async def delete_message(message_id: int, request: Request):
    db = get_db(request)
    message = db.get_message_by_id(message_id)
    if not message:
        return JSONResponse({"ok": False, "error": "Message not found"}, status_code=404)
    if not ensure_tenant_room_access(db, message.get("room_id"), tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Message not found"}, status_code=404)
    db.delete_message(message_id)
    return {"ok": True}


# Send message (triggers AI)
@router.post("/rooms/{room_id}/send")
async def send_message(room_id: str, request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    if not ensure_tenant_room_access(db, room_id, tenant_id):
        return JSONResponse({"ok": False, "error": "Room not found"}, status_code=404)
    ws_manager = get_ws(request)
    body = await request.json()
    text = body.get("text")
    if not text:
        return JSONResponse({"ok": False, "error": "text is required"}, status_code=400)

    text = _clean_assistant_text(text)
    if not text:
        return JSONResponse({"ok": False, "error": "text is required"}, status_code=400)
    db.ensure_system_agents()

    # Parse mentions
    mentions = resolve_real_mentions(db, text, body.get("mentions") or [], room_id, tenant_id)

    # Handle /retry: delete last AI message and re-trigger
    if text.strip() == '/retry':
        recent = db.get_room_messages(room_id, 10)
        last_ai = None
        for m in reversed(recent):
            if m["sender_id"] not in ("user", "system"):
                last_ai = m
                break
        if last_ai:
            db.delete_message(last_ai["id"])
            await ws_manager.notify_ui({"type": "message_deleted", "room_id": room_id, "message_id": last_ai["id"]})
            # Re-trigger with the last user message
            last_user = None
            for m in reversed(recent):
                if m["sender_id"] == "user" and m["id"] != last_ai["id"]:
                    last_user = m
                    break
            if last_user:
                from ai_engine import process_message
                room = db.get_room(room_id)
                room_type = room["type"] if room else "group"
                target_agents = mentions if mentions else [last_ai["sender_id"]]
                async def _retry():
                    try:
                        await process_message(db, ws_manager, room_id, "user", last_user["text"], target_agents, room_type)
                    except Exception as e:
                        print(f"[AI] retry error: {e}")
                asyncio.create_task(_retry())
        return {"ok": True, "result": {"action": "retry"}}

    if text.strip() == "/summary":
        text = (
            "请对本群聊做一次任务进展总结，严格按以下 Markdown 结构输出（某节无内容则写“无”）：\n\n"
            "## 任务目标\n## 已完成（逐条附产物路径或链接）\n## 进行中\n## 待办（按优先级排序）\n"
            "## 阻塞问题\n## 下一步行动\n\n"
            "要求：只依据本群聊天记录与共享工作空间的真实文件；禁止编造未发生的进展；全文不超过 400 字。"
        )

    room = db.get_room(room_id)
    room_type = room["type"] if room else "group"
    room_settings = db.get_room_settings(room_id) if room_type == "group" else {}
    if room_settings.get("collaboration_mode") == "planning":
        orchestrator_id = room_settings.get("planning_orchestrator_id")
        if orchestrator_id:
            mentions = [orchestrator_id]
        recent = db.get_room_messages(room_id, 1)
        if not recent:
            title = _compact_task_name(text)
            db.execute(
                f"UPDATE rooms SET name = {db._placeholder()}, description = {db._placeholder()} WHERE id = {db._placeholder()}",
                (title, text[:500], room_id),
            )
            db.update_room_settings(room_id, {"room_guide": f"群聊目标：{text[:500]}"})
            db.commit()
    if room_type == "group":
        mentions = default_single_agent_mentions(db, room_id, mentions)

    await _interrupt_matching_streams(ws_manager, room_id, mentions)

    message = db.create_message(room_id, "user", text, "markdown", None, mentions)

    skill_result = _handle_natural_language_skill_create(db, room_id, text, mentions)
    if skill_result:
        if skill_result.get("message"):
            await ws_manager.notify_ui({"type": "new_message", "room_id": room_id, "message": skill_result["message"]})
        if not skill_result.get("ok"):
            error_message = db.create_message(room_id, "system", f"⚠️ 技能创建失败：{skill_result.get('error', '未知错误')}")
            await ws_manager.notify_ui({"type": "new_message", "room_id": room_id, "message": error_message})
        return {"ok": True, "result": message, "skill_result": skill_result}

    if is_low_value_collaboration_ack(text):
        return {"ok": True, "result": message, "skipped_ai": "low_value_collaboration_ack"}

    # TRAE experience account message limit
    if tenant_id == "traetest":
        ip = _get_client_ip(request)
        allowed, limit_msg = _check_traetest_message_limit(db, ip)
        if not allowed:
            limit_sys_msg = db.create_message(room_id, "system", f"⚠️ {limit_msg}")
            await ws_manager.notify_ui({"type": "new_message", "room_id": room_id, "message": limit_sys_msg})
            return {"ok": True, "result": message, "limit_reached": True}

    # Trigger AI asynchronously
    from ai_engine import process_message
    ai_text = text
    credential_query = bool(re.search(r"(?:账号|密码|凭据|credential).*(?:查询|查看|列出|有哪些)|(?:查询|查看|列出).*(?:账号|密码|凭据|credential)", text, re.I))
    if credential_query:
        if not is_admin_account(request):
            denial = db.create_message(room_id, "system", "仅主账号可以查询凭据目录。凭据明文不会向任何账号显示。")
            await ws_manager.notify_ui({"type": "new_message", "room_id": room_id, "message": denial})
            return {"ok": True, "result": message, "credential_access": "denied"}
        store = getattr(request.app.state, "credential_store", None)
        credentials = store.list_all() if store else []
        safe_lines = [f"- {item.get('name', '未命名')} ({item.get('type', 'unknown')})" for item in credentials]
        ai_text += "\n\n[主账号授权的只读凭据目录；只能说明名称和类型，禁止输出或索取明文]\n" + ("\n".join(safe_lines) if safe_lines else "暂无配置凭据")
    async def _run_ai():
        try:
            await process_message(db, ws_manager, room_id, "user", ai_text, mentions, room_type)
        except Exception as e:
            import traceback
            print(f"[AI] process_message error: {e}")
            traceback.print_exc()
    asyncio.create_task(_run_ai())

    return {"ok": True, "result": message}


@router.post("/conversations/batch-delete")
async def batch_delete_conversations(request: Request):
    db = get_db(request)
    body = await request.json()
    items = body.get("items") or []
    delete_dm_agents = bool(body.get("delete_dm_agents"))
    if not isinstance(items, list):
        return JSONResponse({"ok": False, "error": "items must be a list"}, status_code=400)

    orchestrator_ids = {
        db.get_hub_setting("orchestrator_agent_id"),
        db.get_hub_setting("default_orchestrator_agent_id"),
    }
    protected_agent_ids = {"__system__", "user", "system", None, ""} | orchestrator_ids
    deleted_rooms = []
    deleted_agents = []
    errors = []

    for item in items:
        if isinstance(item, str):
            room_id = item.strip()
            item_type = "group"
        elif isinstance(item, dict):
            room_id = str(item.get("id") or "").strip()
            item_type = str(item.get("type") or item.get("conversationType") or "group")
        else:
            continue
        if not room_id:
            continue
        room = db.get_room(room_id)
        if not room:
            continue
        agent_ids = []
        if delete_dm_agents and (item_type == "dm" or room.get("type") == "dm"):
            members = db.get_room_members(room_id)
            agent_ids = [m.get("id") for m in members if m.get("id") not in protected_agent_ids]
        try:
            db.delete_room(room_id)
            deleted_rooms.append(room_id)
            for agent_id in agent_ids:
                try:
                    db.delete_agent(agent_id)
                    deleted_agents.append(agent_id)
                except Exception as exc:
                    errors.append({"id": agent_id, "error": str(exc)})
        except Exception as exc:
            errors.append({"id": room_id, "error": str(exc)})

    return {"ok": not errors, "deleted_rooms": deleted_rooms, "deleted_agents": deleted_agents, "errors": errors}


# === DMs ===

@router.post("/dm/{agent_id}")
async def create_dm(agent_id: str, request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    if not ensure_tenant_agent_access(db, agent_id, tenant_id):
        return JSONResponse({"ok": False, "error": "Agent not found"}, status_code=404)
    agent = db.get_agent_by_id(agent_id)
    if not agent:
        return JSONResponse({"ok": False, "error": "Agent not found"}, status_code=404)
    db.ensure_system_agents()
    dm_room = db.get_dm_room("user", agent_id)
    if dm_room and tenant_id is not None and dm_room.get("tenant_id") != tenant_id:
        dm_room = None
    if not dm_room:
        dm_room = db.create_room(f"DM: {agent['name']}", "", "dm", tenant_id)
        db.add_member(dm_room["id"], "user", "member")
        db.add_member(dm_room["id"], agent_id, "member")
    return {"ok": True, "result": {"room_id": dm_room["id"], "agent": agent}}


@router.get("/dms")
async def list_dms(request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    return {"ok": True, "result": db.list_dm_rooms_with_details(tenant_id)}


# === Model Configs ===

@router.get("/models")
async def list_models(request: Request):
    db = get_db(request)
    configs = db.list_model_configs()
    if is_admin_account(request):
        # 主账号允许查看/维护完整模型配置（包括 endpoint 和 api_key）。
        # 注意：不要在日志中打印该返回值。
        safe = configs
    else:
        # 子账号可新增/维护自己的模型；管理员已有模型只可使用，隐藏原始 endpoint/key。
        tenant_id = tenant_id_for_request(request)
        safe = [sanitize_model_config_for_tenant(c, tenant_id) for c in configs]
    return {"ok": True, "result": safe}


@router.post("/models")
async def create_model(request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    body = await request.json()
    for key in ["name", "provider", "base_url", "api_key", "model"]:
        if not body.get(key):
            return JSONResponse({"error": f"{key} required"}, status_code=400)
    body["tenant_id"] = tenant_id
    config = db.create_model_config(body)
    if not is_admin_account(request):
        config = sanitize_model_config_for_tenant(config, tenant_id)
    return {"ok": True, "result": config}


@router.post("/models/batch-delete")
async def batch_delete_models(request: Request):
    db = get_db(request)
    body = await request.json()
    model_ids = body.get("model_ids") or body.get("ids") or []
    if not isinstance(model_ids, list) or not model_ids:
        return JSONResponse({"ok": False, "error": "model_ids required"}, status_code=400)
    if not is_admin_account(request):
        allowed = []
        tenant_id = tenant_id_for_request(request)
        for model_id in model_ids:
            config = db.get_model_config(model_id)
            if config and config.get("tenant_id") == tenant_id:
                allowed.append(model_id)
        model_ids = allowed
        if not model_ids:
            return JSONResponse({"ok": False, "error": "只能删除自己新增的模型配置"}, status_code=403)
    deleted = db.delete_model_configs_batch(model_ids)
    return {"ok": True, "deleted": deleted}


@router.put("/models/{model_id}")
async def update_model(model_id: str, request: Request):
    db = get_db(request)
    _, blocked = ensure_model_config_write_access(db, model_id, request)
    if blocked:
        return blocked
    body = await request.json()
    db.update_model_config(model_id, body)
    return {"ok": True}


@router.delete("/models/{model_id}")
async def delete_model(model_id: str, request: Request):
    db = get_db(request)
    _, blocked = ensure_model_config_write_access(db, model_id, request)
    if blocked:
        return blocked
    db.delete_model_config(model_id)
    return {"ok": True}


# Model metadata (litellm)
_model_metadata_cache = None
_model_metadata_time = 0


@router.post("/config/models")
async def fetch_provider_models(request: Request):
    """Fetch available models from a provider's /models endpoint."""
    import httpx
    body = await request.json()
    base_url = body.get("base_url", "").rstrip("/")
    api_key_val = body.get("api_key", "")

    # Existing stored keys may be used only by admin or the tenant that created that config.
    if not api_key_val and body.get("model_config_id"):
        db = get_db(request)
        config, blocked = ensure_model_config_write_access(db, body["model_config_id"], request)
        if blocked:
            return blocked
        if config:
            api_key_val = config.get("api_key", "")
            if not base_url:
                base_url = config.get("base_url", "").rstrip("/")

    if not base_url or not api_key_val:
        return JSONResponse({"ok": False, "error": "需要 base_url 和 api_key"}, status_code=400)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                base_url + "/models",
                headers={"Authorization": f"Bearer {api_key_val}"}
            )
            if resp.status_code != 200:
                return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            data = resp.json()
            # OpenAI format: { data: [{id: "model-name", ...}, ...] }
            models_list = data.get("data", [])
            # Normalize to [{id: "..."}]
            result = [{"id": m["id"]} for m in models_list if m.get("id")]
            # Sort alphabetically
            result.sort(key=lambda x: x["id"])
            return {"ok": True, "result": result}
    except httpx.TimeoutException:
        return {"ok": False, "error": "连接超时（20秒）"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/models/test")
async def test_model_connection(request: Request):
    """Test a model connection by sending a simple prompt."""
    import httpx
    body = await request.json()
    base_url = body.get("base_url", "").rstrip("/")
    api_key_val = body.get("api_key", "")
    model = body.get("model", "gpt-4o-mini")
    api_mode = body.get("api_mode", "chat_completions")

    # Existing stored keys may be used only by admin or the tenant that created that config.
    if not api_key_val and body.get("model_config_id"):
        db = get_db(request)
        config, blocked = ensure_model_config_write_access(db, body["model_config_id"], request)
        if blocked:
            return blocked
        if config:
            api_key_val = config["api_key"]
            if not base_url:
                base_url = config["base_url"].rstrip("/")

    if not base_url or not api_key_val:
        return JSONResponse({"ok": False, "error": "需要 base_url 和 api_key"}, status_code=400)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if api_mode == "anthropic_messages":
                # Anthropic Messages API format
                url = base_url + "/messages"
                resp = await client.post(url, json={
                    "model": model,
                    "max_tokens": 50,
                    "messages": [{"role": "user", "content": "Say hi in 5 words"}]
                }, headers={
                    "x-api-key": api_key_val,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                })
            elif api_mode == "responses":
                # OpenAI Responses API format
                url = base_url + "/responses"
                resp = await client.post(url, json={
                    "model": model,
                    "input": "Say hi in 5 words",
                }, headers={
                    "Authorization": f"Bearer {api_key_val}",
                    "Content-Type": "application/json",
                })
            else:
                # Chat Completions (default)
                url = base_url + "/chat/completions"
                resp = await client.post(url, json={
                    "model": model,
                    "max_tokens": 50,
                    "messages": [{"role": "user", "content": "Say hi in 5 words"}]
                }, headers={
                    "Authorization": f"Bearer {api_key_val}",
                    "Content-Type": "application/json",
                })

            if resp.status_code != 200:
                error_text = resp.text[:200]
                return {"ok": False, "error": f"HTTP {resp.status_code}: {error_text}"}

            data = resp.json()
            # Extract reply based on format
            reply = ""
            if api_mode == "anthropic_messages":
                reply = data.get("content", [{}])[0].get("text", "")
            elif api_mode == "responses":
                reply = data.get("output_text", "") or str(data.get("output", ""))[:100]
            else:
                reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            return {"ok": True, "result": {"reply": reply, "model": model, "api_mode": api_mode}}

    except httpx.TimeoutException:
        return {"ok": False, "error": "连接超时（30秒）"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.get("/models/metadata")
async def get_model_metadata(request: Request):
    import time
    import httpx
    global _model_metadata_cache, _model_metadata_time

    if _model_metadata_cache and (time.time() - _model_metadata_time < 86400):
        pass
    else:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get("https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json")
                if resp.status_code == 200:
                    data = resp.json()
                    simplified = {}
                    for key, val in data.items():
                        if key == "sample_spec":
                            continue
                        simplified[key] = {
                            "max_input_tokens": val.get("max_input_tokens"),
                            "max_output_tokens": val.get("max_output_tokens"),
                            "provider": val.get("litellm_provider"),
                            "supports_vision": bool(val.get("supports_vision")),
                            "supports_function_calling": bool(val.get("supports_function_calling")),
                        }
                    _model_metadata_cache = simplified
                    _model_metadata_time = time.time()
        except Exception:
            pass

    metadata = _model_metadata_cache or {}
    q = request.query_params.get("q")
    id_param = request.query_params.get("id")

    if id_param:
        exact = metadata.get(id_param)
        if exact:
            return {"ok": True, "result": {id_param: exact}}
        matches = {k: v for k, v in metadata.items() if id_param in k}
        return {"ok": True, "result": dict(list(matches.items())[:20])}
    if q:
        query = q.lower()
        matches = {k: v for k, v in metadata.items() if query in k.lower()}
        return {"ok": True, "result": dict(list(matches.items())[:50])}
    return {"ok": True, "total": len(metadata)}


# === Threads ===

@router.get("/rooms/{room_id}/threads")
async def get_threads(room_id: str, request: Request):
    db = get_db(request)
    if not ensure_tenant_room_access(db, room_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Room not found"}, status_code=404)
    threads = db.get_threads(room_id)
    return {"ok": True, "result": threads}


@router.post("/rooms/{room_id}/threads")
async def create_thread(room_id: str, request: Request):
    db = get_db(request)
    if not ensure_tenant_room_access(db, room_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Room not found"}, status_code=404)
    body = await request.json()
    title = body.get("title")
    if not title:
        return JSONResponse({"ok": False, "error": "title is required"}, status_code=400)
    thread = db.create_thread(room_id, title)
    return {"ok": True, "result": thread}


@router.patch("/threads/{thread_id}")
@router.put("/threads/{thread_id}")
async def update_thread(thread_id: str, request: Request):
    db = get_db(request)
    if not ensure_tenant_thread_access(db, thread_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Thread not found"}, status_code=404)
    body = await request.json()
    db.update_thread(thread_id, body)
    return {"ok": True}


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str, request: Request):
    db = get_db(request)
    if not ensure_tenant_thread_access(db, thread_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Thread not found"}, status_code=404)
    db.delete_thread(thread_id)
    return {"ok": True}


# === Approval ===

@router.post("/approvals/{approval_id}")
async def respond_approval(approval_id: str, request: Request):
    """User responds to an approval request (approve/deny)."""
    from ai_engine import resolve_approval
    body = await request.json()
    decision = body.get("decision", "deny")  # command: once/session/always/deny; skill: approve/deny
    if decision not in ("once", "session", "always", "approve", "deny"):
        decision = "deny"
    resolve_approval(approval_id, decision)
    return {"ok": True, "decision": decision}


@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str, request: Request):
    db = get_db(request)
    if not ensure_tenant_thread_access(db, thread_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Thread not found"}, status_code=404)
    limit = int(request.query_params.get("limit", "30"))
    q = request.query_params.get("q")
    before_id = request.query_params.get("before_id")
    order = request.query_params.get("order", "desc")
    if q:
        thread = db.get_thread(thread_id)
        if not thread:
            return JSONResponse({"ok": False, "error": "Thread not found"}, status_code=404)
        messages = db.get_room_history(
            thread["room_id"],
            limit,
            int(before_id) if before_id else None,
            order=order,
            q=q,
            thread_id=thread_id,
        )
    else:
        messages = db.get_thread_messages(thread_id, limit, int(before_id) if before_id else None)
    return {"ok": True, "result": messages}


@router.post("/threads/{thread_id}/send")
async def send_thread_message(thread_id: str, request: Request):
    db = get_db(request)
    ws_manager = get_ws(request)
    body = await request.json()
    text = body.get("text")
    if not text:
        return JSONResponse({"ok": False, "error": "text is required"}, status_code=400)

    thread = ensure_tenant_thread_access(db, thread_id, tenant_id_for_request(request))
    if not thread:
        return JSONResponse({"ok": False, "error": "Thread not found"}, status_code=404)

    db.ensure_system_agents()

    # Parse mentions
    mentions = resolve_real_mentions(db, text, body.get("mentions") or [])

    # Handle /retry in thread
    if text.strip() == '/retry':
        recent = db.get_thread_messages(thread_id, 10)
        last_ai = None
        for m in reversed(recent):
            if m["sender_id"] not in ("user", "system"):
                last_ai = m
                break
        if last_ai:
            db.delete_message(last_ai["id"])
            await ws_manager.notify_ui({"type": "message_deleted", "room_id": thread["room_id"], "message_id": last_ai["id"], "thread_id": thread_id})
            last_user = None
            for m in reversed(recent):
                if m["sender_id"] == "user" and m["id"] != last_ai["id"]:
                    last_user = m
                    break
            if last_user:
                from ai_engine import process_message
                room = db.get_room(thread["room_id"])
                room_type = room["type"] if room else "group"
                target_agents = mentions if mentions else [last_ai["sender_id"]]
                async def _retry_thread():
                    try:
                        await process_message(db, ws_manager, thread["room_id"], "user", last_user["text"], target_agents, room_type, thread_id=thread_id)
                    except Exception as e:
                        print(f"[AI] retry error: {e}")
                asyncio.create_task(_retry_thread())
        return {"ok": True, "result": {"action": "retry"}}

    room = db.get_room(thread["room_id"])
    room_type = room["type"] if room else "group"
    if room_type == "group":
        mentions = default_single_agent_mentions(db, thread["room_id"], mentions)

    await _interrupt_matching_streams(ws_manager, thread["room_id"], mentions, thread_id)

    message = db.create_message(thread["room_id"], "user", text, "markdown", None, mentions, thread_id=thread_id)

    skill_result = _handle_natural_language_skill_create(db, thread["room_id"], text, mentions, thread_id=thread_id)
    if skill_result:
        if skill_result.get("message"):
            await ws_manager.notify_ui({"type": "new_message", "room_id": thread["room_id"], "message": skill_result["message"], "thread_id": thread_id})
        if not skill_result.get("ok"):
            error_message = db.create_message(thread["room_id"], "system", f"⚠️ 技能创建失败：{skill_result.get('error', '未知错误')}", thread_id=thread_id)
            await ws_manager.notify_ui({"type": "new_message", "room_id": thread["room_id"], "message": error_message, "thread_id": thread_id})
        return {"ok": True, "result": message, "skill_result": skill_result}

    # TRAE experience account message limit
    if tenant_id_for_request(request) == "traetest":
        ip = _get_client_ip(request)
        allowed, limit_msg = _check_traetest_message_limit(db, ip)
        if not allowed:
            limit_sys_msg = db.create_message(thread["room_id"], "system", f"⚠️ {limit_msg}", thread_id=thread_id)
            await ws_manager.notify_ui({"type": "new_message", "room_id": thread["room_id"], "message": limit_sys_msg, "thread_id": thread_id})
            return {"ok": True, "result": message, "limit_reached": True}

    # Trigger AI
    from ai_engine import process_message
    asyncio.create_task(process_message(db, ws_manager, thread["room_id"], "user", text, mentions, room_type, thread_id=thread_id))

    return {"ok": True, "result": message}


# === Workflows ===

@router.get("/rooms/{room_id}/workflows")
async def get_workflows(room_id: str, request: Request):
    db = get_db(request)
    if not ensure_tenant_room_access(db, room_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Room not found"}, status_code=404)
    workflows = db.get_workflows(room_id)
    return {"ok": True, "result": workflows}


@router.post("/rooms/{room_id}/workflows")
async def create_workflow(room_id: str, request: Request):
    db = get_db(request)
    if not ensure_tenant_room_access(db, room_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Room not found"}, status_code=404)
    body = await request.json()
    name = body.get("name")
    steps_json = body.get("steps_json")
    if not name or not steps_json:
        return JSONResponse({"ok": False, "error": "name and steps_json required"}, status_code=400)
    if not isinstance(steps_json, str):
        steps_json = json.dumps(steps_json)
    trigger_config = body.get("trigger_config", "{}")
    if not isinstance(trigger_config, str):
        trigger_config = json.dumps(trigger_config)
    workflow = db.create_workflow(room_id, name, body.get("description", ""),
                                  steps_json, body.get("trigger_type", "manual"), trigger_config)
    # Reload scheduler
    scheduler = request.app.state.workflow_scheduler
    if scheduler:
        scheduler.reload()
    return {"ok": True, "result": workflow}


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str, request: Request):
    db = get_db(request)
    workflow = ensure_tenant_workflow_access(db, workflow_id, tenant_id_for_request(request))
    if not workflow:
        return JSONResponse({"ok": False, "error": "Workflow not found"}, status_code=404)
    return {"ok": True, "result": workflow}


@router.put("/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, request: Request):
    db = get_db(request)
    if not ensure_tenant_workflow_access(db, workflow_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Workflow not found"}, status_code=404)
    body = await request.json()
    db.update_workflow(workflow_id, body)
    scheduler = request.app.state.workflow_scheduler
    if scheduler:
        scheduler.reload()
    return {"ok": True}


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, request: Request):
    db = get_db(request)
    if not ensure_tenant_workflow_access(db, workflow_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Workflow not found"}, status_code=404)
    db.delete_workflow(workflow_id)
    scheduler = request.app.state.workflow_scheduler
    if scheduler:
        scheduler.reload()
    return {"ok": True}


@router.get("/workflows/{workflow_id}/runs")
async def get_workflow_runs(workflow_id: str, request: Request):
    db = get_db(request)
    runs = db.get_workflow_runs(workflow_id)
    return {"ok": True, "result": runs}


@router.post("/workflows/{workflow_id}/run")
@router.post("/workflows/{workflow_id}/trigger")
async def run_workflow(workflow_id: str, request: Request):
    db = get_db(request)
    workflow = ensure_tenant_workflow_access(db, workflow_id, tenant_id_for_request(request))
    if not workflow:
        return JSONResponse({"ok": False, "error": "Workflow not found"}, status_code=404)
    runner = request.app.state.workflow_runner
    if not runner:
        return JSONResponse({"ok": False, "error": "WorkflowRunner not initialized"}, status_code=500)
    try:
        result = await runner.start(workflow_id, workflow["room_id"])
        return {"ok": True, "result": result}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.post("/workflow-runs/{run_id}/cancel")
async def cancel_workflow_run(run_id: str, request: Request):
    runner = request.app.state.workflow_runner
    if not runner:
        return JSONResponse({"ok": False, "error": "WorkflowRunner not initialized"}, status_code=500)
    runner.cancel(run_id)
    return {"ok": True}


# === Agent Skills ===

@router.get("/agents/{agent_id}/skills")
async def get_agent_skills(agent_id: str, request: Request):
    db = get_db(request)
    if not ensure_tenant_agent_access(db, agent_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Agent not found"}, status_code=404)
    skills = db.get_agent_skills(agent_id)
    return {"ok": True, "result": skills}


@router.get("/skills")
async def get_all_skills(request: Request):
    db = get_db(request)
    skills = db.get_all_skills(tenant_id_for_request(request))
    return {"ok": True, "result": skills}


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str, request: Request):
    db = get_db(request)
    skill = ensure_tenant_skill_access(db, skill_id, tenant_id_for_request(request))
    if not skill:
        return JSONResponse({"ok": False, "error": "Skill not found"}, status_code=404)
    return {"ok": True, "result": skill}


@router.post("/agents/{agent_id}/skills")
async def create_skill(agent_id: str, request: Request):
    db = get_db(request)
    if not ensure_tenant_agent_access(db, agent_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Agent not found"}, status_code=404)
    body = await request.json()
    name = body.get("name")
    if not name:
        return JSONResponse({"ok": False, "error": "name is required"}, status_code=400)
    skill = db.create_skill(agent_id, name, body.get("description", ""),
                            body.get("content", ""), body.get("file_type", "text"))
    return {"ok": True, "result": skill}


@router.put("/skills/{skill_id}")
async def update_skill(skill_id: str, request: Request):
    db = get_db(request)
    if not ensure_tenant_skill_access(db, skill_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Skill not found"}, status_code=404)
    body = await request.json()
    skill = db.update_skill(skill_id, body)
    return {"ok": True, "result": skill}


@router.delete("/skills/{skill_id}")
async def delete_skill(skill_id: str, request: Request):
    db = get_db(request)
    if not ensure_tenant_skill_access(db, skill_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Skill not found"}, status_code=404)
    db.delete_skill(skill_id)
    return {"ok": True}


# === Engine Status ===

@router.get("/engine/status")
async def engine_status(request: Request):
    from ai_engine import get_engine_status
    return {"ok": True, "result": get_engine_status()}


@router.post("/skills/{skill_id}/copy")
async def copy_skill(skill_id: str, request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    if not ensure_tenant_skill_access(db, skill_id, tenant_id):
        return JSONResponse({"ok": False, "error": "Source skill not found"}, status_code=404)
    body = await request.json()
    target = body.get("target_agent_id")
    if not target:
        return JSONResponse({"ok": False, "error": "target_agent_id required"}, status_code=400)
    if not ensure_tenant_agent_access(db, target, tenant_id):
        return JSONResponse({"ok": False, "error": "Target agent not found"}, status_code=404)
    skill = db.copy_skill_to_agent(skill_id, target)
    if not skill:
        return JSONResponse({"ok": False, "error": "Source skill not found"}, status_code=404)
    return {"ok": True, "result": skill}


# === Room Skills (isolation per room) ===

@router.get("/rooms/{room_id}/skills")
async def get_room_skills(room_id: str, request: Request):
    db = get_db(request)
    if not ensure_tenant_room_access(db, room_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Room not found"}, status_code=404)
    skills = db.get_room_skills_full(room_id)
    return {"ok": True, "result": skills}


@router.put("/rooms/{room_id}/skills")
async def set_room_skills(room_id: str, request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    if not ensure_tenant_room_access(db, room_id, tenant_id):
        return JSONResponse({"ok": False, "error": "Room not found"}, status_code=404)
    body = await request.json()
    skill_ids = body.get("skill_ids", [])
    for sid in skill_ids:
        if not ensure_tenant_skill_access(db, sid, tenant_id):
            return JSONResponse({"ok": False, "error": f"Skill not found: {sid}"}, status_code=404)
    db.set_room_skills(room_id, skill_ids)
    skills = db.get_room_skills_full(room_id)
    return {"ok": True, "result": skills}


@router.post("/rooms/{room_id}/skills/{skill_id}")
async def add_room_skill(room_id: str, skill_id: str, request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    if not ensure_tenant_room_access(db, room_id, tenant_id) or not ensure_tenant_skill_access(db, skill_id, tenant_id):
        return JSONResponse({"ok": False, "error": "Room or skill not found"}, status_code=404)
    db.add_room_skill(room_id, skill_id)
    skills = db.get_room_skills_full(room_id)
    return {"ok": True, "result": skills}


@router.delete("/rooms/{room_id}/skills/{skill_id}")
async def remove_room_skill(room_id: str, skill_id: str, request: Request):
    db = get_db(request)
    tenant_id = tenant_id_for_request(request)
    if not ensure_tenant_room_access(db, room_id, tenant_id) or not ensure_tenant_skill_access(db, skill_id, tenant_id):
        return JSONResponse({"ok": False, "error": "Room or skill not found"}, status_code=404)
    db.remove_room_skill(room_id, skill_id)
    skills = db.get_room_skills_full(room_id)
    return {"ok": True, "result": skills}


# === Observability ===

@router.get("/observability/summary")
async def get_observability_summary(request: Request):
    db = get_db(request)
    room_id = request.query_params.get("room_id")
    tenant_id = tenant_id_for_request(request)
    if room_id and not ensure_tenant_room_access(db, room_id, tenant_id):
        return JSONResponse({"ok": False, "error": "Room not found"}, status_code=404)
    if tenant_id is not None and not room_id:
        return JSONResponse({"ok": False, "error": "子账号不能查看全局观测数据"}, status_code=403)
    limit = int(request.query_params.get("limit", "100"))
    return {"ok": True, "result": db.get_observability_summary(room_id, limit)}


# === Hub Settings ===

LOG_FILE = "/tmp/myna.log"
LOG_FILE_ABSPATH = os.path.abspath(LOG_FILE)
LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
SECRET_PATTERNS = [
    (re.compile(r"(authorization\s*[:=]\s*bearer\s+)[^\s\"'<>]+", re.I), r"\1[REDACTED]"),
    (re.compile(r"(bearer\s+)[A-Za-z0-9._\-+/=]{12,}", re.I), r"\1[REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), "sk-[REDACTED]"),
    (re.compile(r"((?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|secret)\s*[:=]\s*)[^\s,;\"'{}<>]+", re.I), r"\1[REDACTED]"),
    (re.compile(r"(\"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|secret)\"\s*:\s*\")[^\"]+", re.I), r"\1[REDACTED]"),
]


def _setting_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _setting_int(value, default: int, lower: int, upper: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(lower, min(parsed, upper))


def _logging_settings_payload(db) -> dict:
    enabled = _setting_bool(db.get_hub_setting("debug_logging_enabled", "0"))
    level = str(db.get_hub_setting("debug_logging_level", "INFO") or "INFO").upper()
    if level not in LOG_LEVELS:
        level = "INFO"
    retention_days = _setting_int(db.get_hub_setting("debug_logging_retention_days", "7"), 7, 1, 365)
    settings = {
        "enabled": enabled,
        "level": level,
        "retention_days": retention_days,
        "log_path": LOG_FILE,
        "max_lines": 1000,
    }
    return {"ok": True, **settings, "settings": settings, "result": settings}


def _redact_log_line(line: str) -> str:
    redacted = line.rstrip("\n\r")
    for pattern, repl in SECRET_PATTERNS:
        redacted = pattern.sub(repl, redacted)
    return redacted


def _is_allowed_log_file() -> bool:
    return LOG_FILE_ABSPATH == "/tmp/myna.log" and not os.path.islink(LOG_FILE)


@router.get("/logging/settings")
async def get_logging_settings(request: Request):
    db = get_db(request)
    return _logging_settings_payload(db)


async def _update_logging_settings(request: Request):
    db = get_db(request)
    body = await request.json()
    if "enabled" in body:
        db.set_hub_setting("debug_logging_enabled", "1" if bool(body.get("enabled")) else "0")
    if "level" in body:
        level = str(body.get("level") or "").upper()
        if level not in LOG_LEVELS:
            return JSONResponse({"ok": False, "error": "日志级别无效"}, status_code=400)
        db.set_hub_setting("debug_logging_level", level)
    if "retention_days" in body:
        retention_days = _setting_int(body.get("retention_days"), 7, 1, 365)
        db.set_hub_setting("debug_logging_retention_days", str(retention_days))
    return _logging_settings_payload(db)


@router.put("/logging/settings")
async def update_logging_settings(request: Request):
    blocked = require_admin_account(request)
    if blocked:
        return blocked
    return await _update_logging_settings(request)


@router.post("/logging/settings")
async def post_logging_settings(request: Request):
    blocked = require_admin_account(request)
    if blocked:
        return blocked
    return await _update_logging_settings(request)


@router.get("/logging/recent")
async def get_recent_logs(request: Request):
    try:
        lines = int(request.query_params.get("lines", "200"))
    except ValueError:
        lines = 200
    requested_lines = lines
    lines = max(1, min(lines, 1000))
    if not _is_allowed_log_file():
        return JSONResponse({"ok": False, "error": "日志路径不受允许"}, status_code=400)
    if not os.path.exists(LOG_FILE):
        return {"ok": True, "lines": [], "result": [], "path": LOG_FILE, "line_count": 0, "requested_lines": requested_lines}
    if not os.path.isfile(LOG_FILE):
        return JSONResponse({"ok": False, "error": "日志路径不可读取"}, status_code=400)
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            recent = f.readlines()[-lines:]
        redacted = [_redact_log_line(line) for line in recent]
        return {"ok": True, "lines": redacted, "result": redacted, "path": LOG_FILE, "line_count": len(redacted), "requested_lines": requested_lines}
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"读取日志失败：{e}"}, status_code=500)


@router.delete("/logging/recent")
async def clear_recent_logs(request: Request):
    blocked = require_admin_account(request)
    if blocked:
        return blocked
    if not _is_allowed_log_file():
        return JSONResponse({"ok": False, "error": "日志路径不受允许"}, status_code=400)
    if not os.path.exists(LOG_FILE):
        return {"ok": True, "cleared": False, "path": LOG_FILE}
    if not os.path.isfile(LOG_FILE):
        return JSONResponse({"ok": False, "error": "日志路径不可清空"}, status_code=400)
    try:
        with open(LOG_FILE, "w", encoding="utf-8"):
            pass
        return {"ok": True, "cleared": True, "path": LOG_FILE}
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"清空日志失败：{e}"}, status_code=500)



@router.get("/pinned-conversations")
async def get_pinned_conversations(request: Request):
    db = get_db(request)
    raw = db.get_hub_setting("pinned_conversations", "{}")
    try:
        pins = json.loads(raw or "{}")
    except Exception:
        pins = {}
    if not isinstance(pins, dict):
        pins = {}
    return {"ok": True, "result": pins}


@router.put("/pinned-conversations")
async def update_pinned_conversations(request: Request):
    body = await request.json()
    pins = body.get("pins", {})
    if not isinstance(pins, dict):
        return JSONResponse({"ok": False, "error": "Invalid pins"}, status_code=400)
    clean = {}
    for key, value in pins.items():
        if not isinstance(key, str) or not key:
            continue
        try:
            clean[key] = int(value)
        except Exception:
            clean[key] = 1
    db = get_db(request)
    db.set_hub_setting("pinned_conversations", json.dumps(clean, ensure_ascii=False))
    return {"ok": True, "result": clean}

@router.get("/settings")
async def get_settings(request: Request):
    blocked = require_admin_account(request)
    if blocked:
        return blocked
    db = get_db(request)
    settings = db.get_all_hub_settings()
    # Never expose password hash to frontend
    settings.pop("auth_password", None)
    # Defaults
    defaults = {
        "agent_max_rounds": "50",
        "agent_concurrency": "10",
        "context_messages_limit": "20",
        "self_improve_enabled": "1",
        "self_improve_threshold": "2",
        "self_improve_path": "per_agent",
        # Optional OpenAI-compatible vision fallback used to describe uploaded
        # images for agents whose primary chat model is text-only. Values may
        # also be supplied through MYNA_VISION_* environment variables.
        "vision_model_config_id": "",
        "vision_base_url": "",
        "vision_api_key": "",
        "vision_model": "",
        "vision_params_json": "",
    }
    for k, v in defaults.items():
        if k not in settings:
            settings[k] = v
    return {"ok": True, "result": settings}


@router.put("/settings")
async def update_settings(request: Request):
    blocked = require_admin_account(request)
    if blocked:
        return blocked
    db = get_db(request)
    body = await request.json()
    for key, value in body.items():
        db.set_hub_setting(key, str(value))
    return {"ok": True}


# === Media file serving ===

from fastapi.responses import FileResponse

@router.get("/media/{path:path}")
async def serve_media(path: str, download: str | None = None):
    """Serve media files generated by agents (screenshots, etc.)."""
    import os
    import mimetypes
    # Try multiple locations for the file
    candidates = [
        str(PROFILES_ROOT / path),          # Hermes profiles
        f"/{path}",                         # Absolute path (e.g. /app/backend/project/...)
    ]
    full_path = None
    # Unauthenticated route: only serve deliverables from known data roots, never secrets/databases.
    data_root = (PROFILES_ROOT.parent.parent).resolve()
    allowed_roots = [(data_root / "workspaces").resolve(), (data_root / "uploads").resolve(), PROFILES_ROOT.resolve()]
    backend_root = (APP_ROOT / "backend").resolve()
    safe_exts = {'.zip', '.tar', '.gz', '.7z', '.rar', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.pdf',
                 '.csv', '.md', '.txt', '.json', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.mp4', '.webm',
                 '.mp3', '.wav', '.html', '.htm'}
    blocked_exts = {'.sqlite', '.sqlite3', '.db', '.key', '.pem', '.env', '.yaml', '.yml', '.toml', '.ini', '.cfg'}
    for candidate in candidates:
        try:
            resolved = Path(candidate).resolve()
        except Exception:
            continue
        if not resolved.is_file():
            continue
        if any(part.startswith('.') for part in resolved.parts[1:]) or resolved.suffix.lower() in blocked_exts:
            continue
        in_data = any(resolved == root or root in resolved.parents for root in allowed_roots)
        if resolved.is_relative_to(PROFILES_ROOT.resolve()) and resolved.suffix.lower() not in safe_exts:
            in_data = False
        in_backend = backend_root in resolved.parents and resolved.suffix.lower() in safe_exts
        if in_data or in_backend:
            full_path = str(resolved)
            break
    if not full_path:
        return JSONResponse({"ok": False, "error": "File not found"}, status_code=404)

    filename = os.path.basename(full_path)
    mime, _ = mimetypes.guess_type(full_path)
    mime = mime or "application/octet-stream"

    # Images and videos: inline display; everything else: force download
    is_viewable = mime.startswith("image/") or mime.startswith("video/") or mime == "application/pdf"
    if download or not is_viewable:
        # FileResponse safely encodes non-ASCII names in Content-Disposition.
        return FileResponse(full_path, filename=filename, media_type=mime)
    return FileResponse(full_path, media_type=mime)


# === System version & update ===

import subprocess

def _detect_version():
    """Detect version: env var > packaged VERSION file > git tag > fallback."""
    env_ver = os.environ.get("MYNA_VERSION")
    if env_ver:
        return env_ver
    try:
        version_file = APP_ROOT / "VERSION"
        if version_file.exists():
            version = version_file.read_text(encoding="utf-8").strip()
            if version:
                return version
    except Exception:
        pass
    # Try git tag (works when running from source)
    try:
        import subprocess
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().lstrip("v")
    except Exception:
        pass
    return "0.5.0"

MYNA_VERSION = _detect_version()

@router.get("/system/version")
async def get_system_version():
    """Return current version and detect if running in Docker."""
    in_docker = os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")
    return {"ok": True, "version": MYNA_VERSION, "docker": in_docker}


# Cache for update check (avoid hammering GitHub API)
_update_cache = {"latest": None, "checked_at": 0}


def _version_key(version: str) -> tuple:
    """Return a comparable semantic-ish version key for tags like v0.7.6.

    Avoid external dependencies and keep behavior consistent in Docker images.
    Non-numeric suffixes are ignored for ordering.
    """
    import re
    nums = re.findall(r"\d+", (version or "").lstrip("vV"))
    return tuple(int(n) for n in nums[:4]) or (0,)


@router.get("/system/check-update")
async def check_for_update(request: Request = None):
    if request is not None:
        blocked = require_admin_account(request)
        if blocked:
            return blocked
    """Check GitHub tags for latest version. Server-side with caching (60s)."""
    import time, httpx
    now = time.time()
    # Return cached result if checked within 60s
    if _update_cache["latest"] and (now - _update_cache["checked_at"]) < 60:
        remote = _update_cache["latest"]
    else:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://api.github.com/repos/uskyu/myna/tags?per_page=100")
                if resp.status_code == 200:
                    tags = resp.json()
                    tag_names = [t.get("name", "") for t in tags if t.get("name")]
                    semver_tags = [t for t in tag_names if _version_key(t) != (0,)]
                    remote = max(semver_tags, key=_version_key).lstrip("v") if semver_tags else ""
                    _update_cache["latest"] = remote
                    _update_cache["checked_at"] = now
                else:
                    return JSONResponse({"ok": False, "error": f"GitHub API returned {resp.status_code}"}, status_code=502)
        except Exception as e:
            return JSONResponse({"ok": False, "error": f"请求超时或网络错误: {type(e).__name__}"}, status_code=502)

    in_docker = os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")
    current = MYNA_VERSION.lstrip("v")
    available = bool(remote and _version_key(remote) > _version_key(current))
    return {
        "ok": True,
        "current": current,
        "latest": remote,
        "available": available,
        "docker": in_docker,
    }


@router.post("/system/update")
async def do_system_update(request: Request):
    blocked = require_admin_account(request)
    if blocked:
        return blocked
    """Trigger container update via an external updater.

    A running web app should not pull/recreate its own container. Mature Docker
    apps delegate self-updates to a supervisor/updater process (Watchtower,
    Portainer agent, systemd unit, etc.). Myna's button therefore asks
    Watchtower to perform the update and only streams the requested state.
    """
    import os
    import time
    import httpx

    if not (os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")):
        return JSONResponse({"ok": False, "error": "Not running in Docker mode"}, status_code=400)

    ws_manager = get_ws(request)
    update_url = os.environ.get("WATCHTOWER_UPDATE_URL", "").strip()
    token = os.environ.get("WATCHTOWER_HTTP_API_TOKEN", "").strip()

    if not (update_url and token) and not os.path.exists("/var/run/docker.sock"):
        return JSONResponse({"ok": False, "error": "Watchtower API not configured and Docker socket not mounted"}, status_code=400)

    async def _trigger_external_updater():
        try:
            await ws_manager.notify_ui({
                "type": "update_progress",
                "stage": "requesting_updater",
                "message": "正在通知独立更新器...",
                "percent": 5,
            })

            # Preferred path: Watchtower HTTP API in the same compose network.
            if update_url and token:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(update_url, headers={"Authorization": f"Bearer {token}"})
                if 200 <= resp.status_code < 300:
                    await ws_manager.notify_ui({
                        "type": "update_progress",
                        "stage": "updater_started",
                        "message": "更新器已接管，正在拉取镜像并重启容器...",
                        "percent": 20,
                    })
                    return
                await ws_manager.notify_ui({
                    "type": "update_progress",
                    "stage": "error",
                    "message": f"Watchtower API 调用失败: HTTP {resp.status_code} {resp.text[:120]}",
                    "percent": 0,
                })
                return

            # Compatibility path for older deployments: start a one-shot
            # Watchtower helper container. It is still an external updater; Myna
            # does not attempt to replace its own process.
            updater_name = f"myna-updater-{int(time.time())}"
            cmd = [
                "docker", "run", "-d", "--rm",
                "--name", updater_name,
                "-v", "/var/run/docker.sock:/var/run/docker.sock",
                "containrrr/watchtower:latest",
                "--run-once",
                "--cleanup",
                "--label-enable",
                "myna-app",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode != 0:
                await ws_manager.notify_ui({
                    "type": "update_progress",
                    "stage": "error",
                    "message": f"启动更新器失败: {(proc.stderr or proc.stdout)[:160]}",
                    "percent": 0,
                })
                return

            await ws_manager.notify_ui({
                "type": "update_progress",
                "stage": "updater_started",
                "message": "一次性 Watchtower 更新器已启动，正在拉取镜像并重启容器...",
                "percent": 20,
            })
        except Exception as e:
            await ws_manager.notify_ui({
                "type": "update_progress",
                "stage": "error",
                "message": f"触发更新失败: {type(e).__name__}: {str(e)[:120]}",
                "percent": 0,
            })

    asyncio.create_task(_trigger_external_updater())
    return {"ok": True, "message": "Update handed off to external updater."}


def _parse_size(s: str) -> int:
    """Parse size string like '12.5MB' to bytes."""
    import re
    s = s.strip().upper()
    m = re.match(r'^([\d.]+)\s*([KMGT]?)B?$', s)
    if not m:
        return 0
    val = float(m.group(1))
    unit = m.group(2)
    multipliers = {'': 1, 'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}
    return int(val * multipliers.get(unit, 1))


# === Token Usage Stats (requires auth) ===

@router.get("/token-usage/summary")
async def token_usage_summary(request: Request):
    """Get daily total token usage summary (last N days). Requires auth."""
    if not is_authenticated(request):
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    db = get_db(request)
    days = int(request.query_params.get("days", "30"))
    tenant_id = tenant_id_for_request(request)
    summary = db.get_token_daily_summary(days) if tenant_id is None else db.get_token_daily_by_room(days, tenant_id).get("daily", [])
    totals = db.get_token_daily_totals(tenant_id)
    return {"ok": True, "result": {"daily": summary, "totals": totals}}


@router.get("/token-usage/by-agent")
async def token_usage_by_agent(request: Request):
    """Get per-agent daily token usage breakdown. Requires auth."""
    if not is_authenticated(request):
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    db = get_db(request)
    days = int(request.query_params.get("days", "30"))
    daily = db.get_token_daily_by_agent(days, tenant_id_for_request(request))
    return {"ok": True, "result": daily}


@router.get("/token-usage/by-room")
async def token_usage_by_room(request: Request):
    """Get per-room token usage totals and daily trend. Requires auth."""
    if not is_authenticated(request):
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    db = get_db(request)
    try:
        days = int(request.query_params.get("days", "30"))
    except (TypeError, ValueError):
        days = 30
    usage = db.get_token_daily_by_room(days, tenant_id_for_request(request))
    return {"ok": True, "result": usage}


@router.get("/token-usage/agent/{agent_id}")
async def token_usage_single_agent(agent_id: str, request: Request):
    """Get token usage history for a specific agent. Requires auth."""
    if not is_authenticated(request):
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    db = get_db(request)
    days = int(request.query_params.get("days", "30"))
    if not ensure_tenant_agent_access(db, agent_id, tenant_id_for_request(request)):
        return JSONResponse({"ok": False, "error": "Agent not found"}, status_code=404)
    usage = db.get_token_daily_for_agent(agent_id, days)
    agent = db.get_agent_by_id(agent_id)
    return {"ok": True, "result": {"agent": agent, "usage": usage}}


# === Data Directory Management (requires auth) ===

@router.get("/data-dir")
async def get_data_dir(request: Request):
    """Get current data directory information. Requires auth."""
    if not is_authenticated(request):
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    blocked = require_admin_account(request)
    if blocked:
        return blocked
    from paths import get_data_dir_info, _migration_pending
    info = get_data_dir_info()
    if _migration_pending:
        info["migration_pending"] = _migration_pending
    return {"ok": True, "result": info}


@router.post("/data-dir/migrate")
async def migrate_data_dir(request: Request):
    """Migrate data to a new directory. Requires auth. App must restart after."""
    if not is_authenticated(request):
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    blocked = require_admin_account(request)
    if blocked:
        return blocked
    body = await request.json()
    new_dir = body.get("new_dir", "").strip()
    if not new_dir:
        return JSONResponse({"ok": False, "error": "请提供新目录路径"}, status_code=400)
    from paths import migrate_data_dir as do_migrate
    result = do_migrate(new_dir)
    return result
