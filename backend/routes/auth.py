"""
Authentication routes - login, change password, session validation.
Default password: admin123
Password stored in hub_settings table (key: 'auth_password', bcrypt hash).
Session token stored in cookie + localStorage on frontend.
"""
import os
import hashlib
import secrets
import time
import threading
import json
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

router = APIRouter()

# In-memory session cache (token -> session metadata), mirrored to DB so
# development restarts do not force users to log in again.
_sessions: dict[str, dict] = {}
SESSION_TTL = 7 * 24 * 3600  # 7 days
SESSION_SETTING_KEY = "auth_sessions"
_auth_lock = threading.Lock()

# TRAE experience account daily login limit
TRAE_LOGIN_LIMIT = 10
TRAE_LOGIN_TRACKER_KEY = "traetest_login_tracker"
TRAE_DEMO_GITHUB_URL = "https://github.com/uskyu/Myna"
TRAE_LIMIT_TIP = (
    "为了控制公共 Demo 的 token 消耗，体验账号每天仅开放 10 个体验名额，"
    "每位体验用户建议只体验 1-2 个问题。深度体验欢迎点击 GitHub 链接自行部署："
    f"{TRAE_DEMO_GITHUB_URL} ，有问题可联系作者一起调整。"
)


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "0.0.0.0"


def _check_traetest_login_limit(db, ip: str) -> tuple[bool, str]:
    raw = db.get_hub_setting(TRAE_LOGIN_TRACKER_KEY) or "{}"
    try:
        tracker = json.loads(raw)
    except Exception:
        tracker = {}
    today = time.strftime("%Y-%m-%d")
    if tracker.get("date") != today or not isinstance(tracker.get("ips"), list):
        tracker = {"date": today, "ips": []}
    if ip in tracker["ips"]:
        return True, ""
    if len(tracker["ips"]) >= TRAE_LOGIN_LIMIT:
        return False, TRAE_LIMIT_TIP
    tracker["ips"].append(ip)
    db.set_hub_setting(TRAE_LOGIN_TRACKER_KEY, json.dumps(tracker))
    return True, ""


DEFAULT_PASSWORD = "admin123"
ADMIN_ACCOUNT = {"id": "admin", "username": "admin", "role": "admin", "tenant_id": None}
SUB_ACCOUNTS = {
    "xj": {"id": "xj", "username": "xj", "password": "xj234", "role": "tenant", "tenant_id": "xj"},
    # TRAE 初赛体验账号：仅使用子账号，数据按 tenant_id 与其他账号隔离。
    "traetest": {"id": "traetest", "username": "traetest", "password": "trae123", "role": "tenant", "tenant_id": "traetest"},
    "PP": {"id": "PP", "username": "PP", "password": "PP123", "role": "tenant", "tenant_id": "PP"},
    "test": {"id": "test", "username": "test", "password": "test123", "role": "tenant", "tenant_id": "test"},
    "qiuqiu": {"id": "qiuqiu", "username": "qiuqiu", "password": "qq123", "role": "tenant", "tenant_id": "qiuqiu"},
    "wj": {"id": "wj", "username": "wj", "password": "wj888", "role": "tenant", "tenant_id": "wj"},
    "lfc": {"id": "lfc", "username": "lfc", "password": "lfc888", "role": "tenant", "tenant_id": "lfc"},
    "Ivy": {"id": "Ivy", "username": "Ivy", "password": "Ivy627", "role": "tenant", "tenant_id": "Ivy"},
}


def _hash_password(password: str) -> str:
    """Simple SHA-256 hash with salt."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_password(password: str, stored: str) -> bool:
    """Verify password against stored hash."""
    if ":" not in stored:
        # Legacy plain text comparison (shouldn't happen)
        return password == stored
    salt, h = stored.split(":", 1)
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest() == h


def _normalize_account(account: dict | None) -> dict:
    data = dict(ADMIN_ACCOUNT)
    if account:
        data.update({k: v for k, v in account.items() if k in {"id", "username", "role", "tenant_id"}})
    return data


def _session_from_legacy_expiry(expiry) -> dict | None:
    try:
        expiry = float(expiry)
    except (TypeError, ValueError):
        return None
    return {"expiry": expiry, "account": dict(ADMIN_ACCOUNT)}


def _load_sessions(db) -> dict[str, dict]:
    """Load persisted sessions from hub_settings and drop expired entries."""
    raw = db.get_hub_setting(SESSION_SETTING_KEY, "{}")
    try:
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}

    now = time.time()
    sessions = {}
    for token, value in data.items():
        session = value if isinstance(value, dict) else _session_from_legacy_expiry(value)
        if not session:
            continue
        try:
            expiry = float(session.get("expiry", 0))
        except (TypeError, ValueError):
            continue
        if expiry > now:
            sessions[token] = {"expiry": expiry, "account": _normalize_account(session.get("account"))}
    return sessions


def _save_sessions(db, sessions: dict[str, dict]):
    """Persist sessions through hub_settings adapter (SQLite/MySQL compatible)."""
    db.set_hub_setting(SESSION_SETTING_KEY, json.dumps(sessions))


def _create_session(db, account: dict | None = None) -> str:
    """Create a new session token and persist it."""
    _sessions.update(_load_sessions(db))
    token = secrets.token_hex(32)
    _sessions[token] = {"expiry": time.time() + SESSION_TTL, "account": _normalize_account(account)}
    _save_sessions(db, _sessions)
    return token


def _get_session(token: str, db=None) -> dict | None:
    if not token:
        return None
    if db is not None and token not in _sessions:
        _sessions.update(_load_sessions(db))
    session = _sessions.get(token)
    if not session or not isinstance(session, dict):
        return None
    try:
        expiry = float(session.get("expiry", 0))
    except (TypeError, ValueError):
        expiry = 0
    if time.time() > expiry:
        _sessions.pop(token, None)
        if db is not None:
            _save_sessions(db, _sessions)
        return None
    return session


def _validate_session(token: str, db=None) -> bool:
    """Check if session token is valid. Falls back to DB on restart."""
    return _get_session(token, db) is not None


def get_account_for_token(token: str, db=None) -> dict | None:
    """Resolve a validated session token to its account metadata."""
    session = _get_session(token, db)
    return _normalize_account(session.get("account")) if session else None


def get_current_account(request: Request) -> dict:
    """Return current account metadata for tenant-aware routes."""
    db = getattr(request.app.state, "db", None)
    auth_header = request.headers.get("authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else request.query_params.get("auth_token", "")
    session = _get_session(token, db)
    if not session:
        return {"id": None, "username": None, "role": "anonymous", "tenant_id": None}
    return _normalize_account(session.get("account"))


def current_tenant_id(request: Request) -> str | None:
    return get_current_account(request).get("tenant_id")


def is_admin_account(request: Request) -> bool:
    return get_current_account(request).get("role") == "admin"


def get_password_hash(db) -> str:
    """Get stored password hash, or set default if not exists."""
    stored = db.get_hub_setting("auth_password")
    if not stored:
        # First run: set default password
        hashed = _hash_password(DEFAULT_PASSWORD)
        db.set_hub_setting("auth_password", hashed)
        return hashed
    return stored


def ensure_password_initialized(db):
    """Call once at startup to ensure password hash exists in DB.
    Prevents race condition where concurrent login requests both see
    no stored hash and write different salted hashes."""
    get_password_hash(db)


def is_authenticated(request: Request) -> bool:
    """Check if request has valid auth session."""
    db = getattr(request.app.state, "db", None)
    # Check Authorization header (Bearer token)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if _validate_session(token, db):
            return True
    # Check query param (for WebSocket)
    token = request.query_params.get("auth_token", "")
    if _validate_session(token, db):
        return True
    return False


@router.post("/login")
async def login(request: Request):
    """Login with password, returns session token."""
    db = request.app.state.db
    body = await request.json()
    username = (body.get("username") or "admin").strip() or "admin"
    password = body.get("password", "")

    with _auth_lock:
        sub_account = SUB_ACCOUNTS.get(username)
        if sub_account:
            if password != sub_account["password"]:
                return JSONResponse({"ok": False, "error": "密码错误"}, status_code=401)
            # TRAE experience account daily login limit
            if sub_account["id"] == "traetest":
                ip = _get_client_ip(request)
                allowed, msg = _check_traetest_login_limit(db, ip)
                if not allowed:
                    return JSONResponse({"ok": False, "error": msg}, status_code=403)
            account = {k: v for k, v in sub_account.items() if k != "password"}
            token = _create_session(db, account)
            return {"ok": True, "token": token, "account": account}

        stored_hash = get_password_hash(db)
        if not _verify_password(password, stored_hash):
            return JSONResponse({"ok": False, "error": "密码错误"}, status_code=401)

        token = _create_session(db, ADMIN_ACCOUNT)
    return {"ok": True, "token": token, "account": ADMIN_ACCOUNT}


@router.post("/change-password")
async def change_password(request: Request):
    """Change password (requires current password)."""
    if not is_admin_account(request):
        return JSONResponse({"ok": False, "error": "子账号不能修改主账号密码"}, status_code=403)
    db = request.app.state.db
    body = await request.json()
    current = body.get("current_password", "")
    new_pwd = body.get("new_password", "")

    if not new_pwd or len(new_pwd) < 4:
        return JSONResponse({"ok": False, "error": "新密码至少4位"}, status_code=400)

    stored_hash = get_password_hash(db)
    if not _verify_password(current, stored_hash):
        return JSONResponse({"ok": False, "error": "当前密码错误"}, status_code=401)

    new_hash = _hash_password(new_pwd)
    db.set_hub_setting("auth_password", new_hash)

    # Invalidate all sessions, including persisted sessions
    _sessions.clear()
    _save_sessions(db, _sessions)

    # Create new session for admin user
    token = _create_session(db, ADMIN_ACCOUNT)
    return {"ok": True, "token": token, "account": ADMIN_ACCOUNT, "message": "密码已修改"}


@router.get("/check")
async def check_auth(request: Request):
    """Check if current session is valid."""
    if is_authenticated(request):
        return {"ok": True, "authenticated": True, "account": get_current_account(request)}
    return JSONResponse({"ok": True, "authenticated": False}, status_code=200)
