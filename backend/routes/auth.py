"""
Authentication routes - login, change password, session validation.
Default password: hermeshub
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

# In-memory session cache (token -> expiry timestamp), mirrored to DB so
# development restarts do not force users to log in again.
_sessions: dict[str, float] = {}
SESSION_TTL = 7 * 24 * 3600  # 7 days
SESSION_SETTING_KEY = "auth_sessions"
_auth_lock = threading.Lock()

DEFAULT_PASSWORD = "admin123"


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


def _load_sessions(db) -> dict[str, float]:
    """Load persisted sessions from hub_settings and drop expired entries.

    Uses the existing db adapter methods only, so this stays compatible with
    both SQLite and MySQL without database-specific SQL.
    """
    raw = db.get_hub_setting(SESSION_SETTING_KEY, "{}")
    try:
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}

    now = time.time()
    sessions = {}
    for token, expiry in data.items():
        try:
            expiry = float(expiry)
        except (TypeError, ValueError):
            continue
        if expiry > now:
            sessions[token] = expiry
    return sessions


def _save_sessions(db, sessions: dict[str, float]):
    """Persist sessions through hub_settings adapter (SQLite/MySQL compatible)."""
    db.set_hub_setting(SESSION_SETTING_KEY, json.dumps(sessions))


def _create_session(db) -> str:
    """Create a new session token and persist it."""
    _sessions.update(_load_sessions(db))
    token = secrets.token_hex(32)
    _sessions[token] = time.time() + SESSION_TTL
    _save_sessions(db, _sessions)
    return token


def _validate_session(token: str, db=None) -> bool:
    """Check if session token is valid. Falls back to DB on restart."""
    if not token:
        return False
    if db is not None and token not in _sessions:
        _sessions.update(_load_sessions(db))
    expiry = _sessions.get(token)
    if not expiry:
        return False
    if time.time() > expiry:
        del _sessions[token]
        if db is not None:
            _save_sessions(db, _sessions)
        return False
    return True


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
    password = body.get("password", "")

    with _auth_lock:
        stored_hash = get_password_hash(db)
        if not _verify_password(password, stored_hash):
            return JSONResponse({"ok": False, "error": "密码错误"}, status_code=401)

        token = _create_session(db)
    return {"ok": True, "token": token}


@router.post("/change-password")
async def change_password(request: Request):
    """Change password (requires current password)."""
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

    # Create new session for current user
    token = _create_session(db)
    return {"ok": True, "token": token, "message": "密码已修改"}


@router.get("/check")
async def check_auth(request: Request):
    """Check if current session is valid."""
    if is_authenticated(request):
        return {"ok": True, "authenticated": True}
    return JSONResponse({"ok": True, "authenticated": False}, status_code=200)
