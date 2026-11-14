"""
Myna - Python Backend
Multi-agent collaboration platform powered by Hermes Agent.
"""
import os
import sys
import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import uvicorn
import mimetypes
from urllib.parse import unquote

# Add hermes-agent to path for direct import
HERMES_AGENT_PATH = Path("/root/hermes")
if HERMES_AGENT_PATH.exists():
    sys.path.insert(0, str(HERMES_AGENT_PATH))

from db import get_database
from ws_manager import WSManager
from routes.admin import router as admin_router, MYNA_VERSION
from routes.gateway import router as gateway_router
from routes.upload import router as upload_router
from routes.auth import router as auth_router, is_authenticated, ensure_password_initialized
from workflow_engine import WorkflowRunner, WorkflowScheduler
from credentials import CredentialStore
from paths import APP_ROOT, DB_ROOT, UPLOADS_DIR, ensure_runtime_dirs

# Globals
db = None
ws_manager: WSManager = None
workflow_runner: WorkflowRunner = None
workflow_scheduler: WorkflowScheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, ws_manager, workflow_runner, workflow_scheduler
    
    # Startup
    ensure_runtime_dirs()
    
    db = get_database(str(DB_ROOT / "myna.sqlite"))
    # Initialize password hash at startup to prevent race condition
    ensure_password_initialized(db)
    ws_manager = WSManager()
    workflow_runner = WorkflowRunner(db, ws_manager)
    workflow_scheduler = WorkflowScheduler(db, workflow_runner)
    workflow_scheduler.start()

    # Credential storage remains available to the main assistant's guarded,
    # read-only lookup. There is no separate System Agent runtime.
    # Use a stable secret for encryption (derived from DB path + machine id)
    encryption_secret = os.environ.get("MYNA_ENCRYPTION_KEY", "")
    if not encryption_secret:
        import warnings
        IS_DOCKER = os.path.exists("/.dockerenv")
        if IS_DOCKER:
            print("⚠️  WARNING: MYNA_ENCRYPTION_KEY not set! Running with auto-generated key.")
            print("⚠️  Credential encryption will NOT survive container recreation.")
            print("⚠️  Set MYNA_ENCRYPTION_KEY in docker-compose.yml environment for production use.")
        # Auto-generate a stable key from DB path + machine id so credentials
        # survive restarts (but NOT container recreation in Docker).
        try:
            with open("/etc/machine-id") as f:
                machine_id = f.read().strip()
        except (FileNotFoundError, PermissionError):
            machine_id = str(Path(__file__).resolve())
        import hashlib
        encryption_secret = hashlib.sha256(f"myna-{machine_id}-{DB_ROOT}".encode()).hexdigest()
    credential_store = CredentialStore(db, encryption_secret)
    
    # Store in app state
    app.state.db = db
    app.state.ws_manager = ws_manager
    app.state.workflow_runner = workflow_runner
    app.state.workflow_scheduler = workflow_scheduler
    app.state.credential_store = credential_store
    
    port = int(os.environ.get("PORT", "3456"))
    print(f"""
╔══════════════════════════════════════════╗
║           Myna v{MYNA_VERSION}                   ║
╠══════════════════════════════════════════╣
║  Web UI:    http://localhost:{port}        ║
║  Gateway:   http://localhost:{port}/bot*   ║
║  WebSocket: ws://localhost:{port}/ws       ║
║  Admin API: http://localhost:{port}/admin  ║
║  Engine:    Hermes Agent (direct)        ║
╚══════════════════════════════════════════╝
    """)

    # Start stream cleanup task
    async def _stream_cleanup_loop():
        while True:
            await asyncio.sleep(60)  # Check every minute
            try:
                await ws_manager.cleanup_stale_streams()
            except Exception as e:
                print(f"[WS] Stream cleanup error: {e}")

    cleanup_task = asyncio.create_task(_stream_cleanup_loop())
    
    # Start update check task (Docker mode only)
    async def _update_check_loop():
        from routes.admin import check_for_update
        IS_DOCKER = os.path.exists("/.dockerenv")
        if not IS_DOCKER:
            return
        
        while True:
            await asyncio.sleep(600)  # Check every 10 minutes
            try:
                result = await check_for_update()
                if isinstance(result, dict) and result.get("available"):
                    await ws_manager.notify_ui({
                        "type": "update_available",
                        "local_version": result.get("current"),
                        "remote_version": result.get("latest")
                    })
            except Exception as e:
                print(f"[UPDATE] Check error: {e}")
    
    update_check_task = asyncio.create_task(_update_check_loop())

    yield
    
    # Shutdown
    cleanup_task.cancel()
    update_check_task.cancel()
    workflow_scheduler.stop()
    db.close()


app = FastAPI(title="Myna", version=MYNA_VERSION, lifespan=lifespan)

# CORS — configurable via MYNA_CORS_ORIGINS env var (comma-separated)
_cors_origins_str = os.environ.get("MYNA_CORS_ORIGINS", "")
if _cors_origins_str:
    _cors_origins = [o.strip() for o in _cors_origins_str.split(",") if o.strip()]
else:
    _cors_origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth_router, prefix="/auth")
app.include_router(admin_router, prefix="/admin")
app.include_router(gateway_router)
app.include_router(upload_router)


# Auth middleware - protect all routes except /auth/*, /health, static files, /ws
# Using pure ASGI middleware instead of BaseHTTPMiddleware to avoid response truncation bugs
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse as StarletteJSONResponse


class AuthMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] not in ("http",):
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        # Skip auth for: login/check endpoints, health, static assets, websocket upgrade, media files, uploads
        if (path.startswith("/auth/") or
            path == "/health" or
            path.startswith("/assets/") or
            path.startswith("/admin/media/") or
            path.startswith("/share/") or
            path == "/admin/system/version" or
            path == "/api/system/version" or
            path.startswith("/uploads/") or
            path.endswith(".js") or path.endswith(".css") or
            path.endswith(".ico") or path.endswith(".png") or
            path.endswith(".svg") or path.endswith(".woff") or path.endswith(".woff2") or
            path == "/" or path == "/index.html"):
            await self.app(scope, receive, send)
            return
        # WebSocket auth is handled in the endpoint itself
        if path == "/ws":
            await self.app(scope, receive, send)
            return
        # Check auth for API routes
        if path.startswith("/admin/") or path.startswith("/upload"):
            request = StarletteRequest(scope, receive)
            if not is_authenticated(request):
                response = StarletteJSONResponse({"ok": False, "error": "未登录"}, status_code=401)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)

app.add_middleware(AuthMiddleware)


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _media_response(candidate: Path, download: bool = False) -> FileResponse:
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    media_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
    if download:
        # Let Starlette encode non-ASCII names as RFC 5987 filename* values.
        return FileResponse(path=str(candidate), media_type=media_type, filename=candidate.name)
    return FileResponse(path=str(candidate), media_type=media_type)


@app.get("/media/workspaces/{file_path:path}")
async def get_workspace_media(file_path: str, download: int = 0):
    raw = unquote(file_path or "").lstrip("/")
    if raw.startswith("app/data/workspaces/"):
        raw = raw[len("app/data/workspaces/"):]
    candidate = (UPLOADS_DIR.parent / "workspaces" / raw).resolve()
    if not _is_within_root(candidate, UPLOADS_DIR.parent / "workspaces"):
        raise HTTPException(status_code=404, detail="文件不存在")
    return _media_response(candidate, bool(download))


@app.get("/admin/media/{file_path:path}")
async def get_admin_media(file_path: str, download: int = 0):
    raw = unquote(file_path or "").strip()
    if not raw:
        raise HTTPException(status_code=404, detail="文件不存在")
    candidate = Path("/") / raw.lstrip("/")
    allowed_roots = [UPLOADS_DIR.resolve(), (UPLOADS_DIR.parent / "workspaces").resolve()]
    if not any(_is_within_root(candidate, root) for root in allowed_roots):
        backend_root = (APP_ROOT / "backend").resolve()
        safe_exts = {'.zip', '.tar', '.gz', '.7z', '.rar', '.docx', '.doc', '.xlsx', '.xls',
                     '.pptx', '.ppt', '.pdf', '.csv', '.md', '.txt', '.json', '.png', '.jpg', '.jpeg'}
        if not (_is_within_root(candidate, backend_root) and candidate.suffix.lower() in safe_exts):
            raise HTTPException(status_code=404, detail="文件不存在")
    return _media_response(candidate, bool(download))


@app.get("/uploads/{file_path:path}")
async def get_upload_media(file_path: str, download: int = 0):
    candidate = (UPLOADS_DIR / unquote(file_path or "").lstrip("/")).resolve()
    if not _is_within_root(candidate, UPLOADS_DIR.resolve()):
        raise HTTPException(status_code=404, detail="文件不存在")
    return _media_response(candidate, bool(download))


# WebSocket endpoint
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    params = websocket.query_params
    is_ui = params.get("ui") == "1"
    api_key = params.get("api_key")
    
    if is_ui:
        # Wait for auth message from UI client (token no longer in URL for security)
        # Allow a short grace period for the auth message, but also support legacy
        # query-param auth_token for backward compatibility
        auth_token = params.get("auth_token")
        ui_authenticated = bool(auth_token)
        
        if not ui_authenticated:
            # Wait for first message which should be auth
            try:
                import json as _json
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                msg = _json.loads(raw)
                if msg.get("type") == "auth" and msg.get("token"):
                    auth_token = msg["token"]
                    ui_authenticated = True
            except (asyncio.TimeoutError, Exception):
                # No auth received — still allow unauthenticated UI connections
                # (the UI may not have a token yet, e.g. on login page)
                pass
        
        app.state.ws_manager.add_ui(websocket)
        try:
            await websocket.send_json({"type": "connected", "client": "ui"})
            # Send active streams for reconnection with ordered parts preserved.
            for stream_id, info in app.state.ws_manager.active_streams.items():
                await websocket.send_json({
                    "type": "stream_start",
                    "stream_id": stream_id,
                    **{k: v for k, v in info.items() if k not in ("text", "tool_calls", "parts")},
                })
                for part in info.get("parts") or []:
                    if part.get("type") == "text" and part.get("text"):
                        await websocket.send_json({
                            "type": "stream_token",
                            "stream_id": stream_id,
                            "room_id": info["room_id"],
                            "chunk": part.get("text", ""),
                        })
                    elif part.get("type") == "tool":
                        await websocket.send_json({
                            "type": "tool_call",
                            "stream_id": stream_id,
                            "room_id": info["room_id"],
                            "agent_id": info["agent_id"],
                            "tool": part.get("name"),
                            "args_summary": part.get("summary", ""),
                            "timestamp": 0,
                        })
                        if part.get("status") != "running":
                            await websocket.send_json({
                                "type": "tool_result",
                                "stream_id": stream_id,
                                "room_id": info["room_id"],
                                "agent_id": info["agent_id"],
                                "tool": part.get("name"),
                                "ok": part.get("status") == "done",
                                "output_preview": part.get("result", ""),
                            })
                if info.get("interrupted"):
                    await websocket.send_json({
                        "type": "stream_interrupted",
                        "stream_id": stream_id,
                        "room_id": info.get("room_id"),
                        "agent_id": info.get("agent_id"),
                        "thread_id": info.get("thread_id"),
                        "timestamp": info.get("timestamp"),
                    })
            while True:
                raw = await websocket.receive_text()
                # Handle UI commands (cancel stream, etc.)
                try:
                    import json as _json
                    cmd = _json.loads(raw)
                    if cmd.get("type") == "cancel_stream":
                        stream_id = cmd.get("stream_id")
                        if stream_id:
                            await app.state.ws_manager.interrupt_stream(stream_id)
                except:
                    pass
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            app.state.ws_manager.remove_ui(websocket)
    elif api_key:
        agent = app.state.db.get_agent_by_key(api_key)
        if not agent:
            await websocket.close(code=4001, reason="Invalid api_key")
            return
        app.state.ws_manager.add_agent(agent["id"], websocket)
        app.state.db.update_agent_status(agent["id"], "online")
        try:
            rooms = app.state.db.get_agent_rooms(agent["id"])
            await websocket.send_json({
                "type": "connected",
                "agent": {"id": agent["id"], "name": agent["name"]},
                "rooms": rooms
            })
            while True:
                data = await websocket.receive_json()
                await handle_agent_ws_message(app, agent, data)
        except WebSocketDisconnect:
            pass
        finally:
            app.state.ws_manager.remove_agent(agent["id"], websocket)
            app.state.db.update_agent_status(agent["id"], "offline")
    else:
        await websocket.close(code=4001, reason="api_key or ui=1 required")


async def handle_agent_ws_message(app, agent, msg):
    """Handle messages from agent WebSocket connections."""
    db = app.state.db
    ws_manager = app.state.ws_manager
    
    if msg.get("type") == "sendMessage":
        room_id = msg.get("room_id")
        text = msg.get("text")
        if not room_id or not text:
            return
        rooms = db.get_agent_rooms(agent["id"])
        if not any(r["id"] == room_id for r in rooms):
            return
        message = db.create_message(room_id, agent["id"], text, msg.get("parse_mode", "markdown"),
                                     msg.get("reply_to_message_id"), msg.get("mentions", []))
        members = db.get_room_members(room_id)
        for member in members:
            if member["id"] != agent["id"]:
                payload = {
                    "type": "message",
                    "message_id": message["id"],
                    "room_id": room_id,
                    "from": {"id": agent["id"], "name": agent["name"]},
                    "text": text,
                    "parse_mode": msg.get("parse_mode", "markdown"),
                    "date": message.get("created_at", "")
                }
                db.push_update(member["id"], "message", payload)
                await ws_manager.notify_agent(member["id"], payload)


# Health check
@app.get("/health")
async def health():
    agents = app.state.db.list_agents()
    rooms = app.state.db.list_rooms()
    return {
        "status": "ok",
        "agents": len(agents),
        "rooms": len(rooms),
        "online": len(app.state.ws_manager.get_online_agents()),
        "engine": "hermes-agent"
    }


def _share_page_html(token: str) -> str:
    template = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Myna 聊天分享</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
  <style>
    :root {
      color-scheme: light dark;
      --bg:#faf9f7; --surface:#ffffff; --surface2:#f4f2ee; --surface3:#ebe8e2;
      --text:#1a1916; --text-2:#44423d; --text-dim:#87847d; --text-faint:#b8b4ab;
      --border:#e8e4dc; --border-strong:#d6d1c5;
      --accent:#2d6a4f; --accent-hover:#1f4c38; --accent-soft:#e8f0eb; --accent-glow:rgba(45,106,79,.18);
      --amber:#d97706; --amber-soft:#fef3e6;
      --radius-sm:8px; --radius:12px; --radius-lg:16px;
      --shadow-sm:0 1px 2px rgba(60,50,30,.04);
      --header-height:52px;
      --font-sans:-apple-system,BlinkMacSystemFont,'Inter','SF Pro Display','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;
      --font-mono:'SF Mono','JetBrains Mono','Fira Code','Cascadia Code',Consolas,monospace;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg:#0f0e0c; --surface:#1a1916; --surface2:#232220; --surface3:#2d2c29;
        --text:#f5f2eb; --text-2:#d6d2c8; --text-dim:#8a857c; --text-faint:#5d5a52;
        --border:#2d2c29; --border-strong:#3d3b37;
        --accent:#4ea876; --accent-hover:#6dbf8e; --accent-soft:rgba(78,168,118,.14); --accent-glow:rgba(78,168,118,.22);
        --amber:#f59e0b;
        --shadow-sm:0 1px 2px rgba(0,0,0,.4);
      }
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    html, body { margin:0; min-height:100%; }
    body {
      font-family:var(--font-sans); background:var(--bg); color:var(--text);
      -webkit-font-smoothing:antialiased; -moz-osx-font-smoothing:grayscale;
      text-rendering:optimizeLegibility; font-feature-settings:'kern','liga','tnum';
    }
    .share-shell { min-height:100vh; display:flex; flex-direction:column; background:var(--bg); }
    .chat-header {
      position:sticky; top:0; z-index:10;
      min-height:var(--header-height); display:flex; align-items:center; gap:16px;
      padding:10px 20px; background:var(--surface); border-bottom:1px solid var(--border);
      flex-shrink:0; box-shadow:var(--shadow-sm);
    }
    .brand-mark {
      width:34px; height:34px; border-radius:11px; flex:0 0 auto;
      background:linear-gradient(135deg,var(--accent),var(--accent-hover));
      color:#fff; display:flex; align-items:center; justify-content:center;
      font-weight:800; font-size:15px; box-shadow:0 1px 3px var(--accent-glow);
    }
    .header-copy { min-width:0; flex:1; }
    .continue-btn {
      border:0; border-radius:999px; padding:10px 16px; background:var(--accent); color:#fff;
      font-weight:700; font-size:13px; cursor:pointer; text-decoration:none; white-space:nowrap;
      transition:transform .15s ease, opacity .15s ease;
    }
    .continue-btn:hover { opacity:.92; transform:translateY(-1px); }
    .title { overflow:hidden; display:-webkit-box; -webkit-box-orient:vertical; -webkit-line-clamp:1; line-clamp:1; font-size:15px; font-weight:700; line-height:1.25; color:var(--text); }
    .meta { margin-top:3px; color:var(--text-dim); font-size:12px; }
    .messages-area {
      flex:1; overflow-y:auto; padding:16px 0 40px; display:flex; flex-direction:column; gap:2px;
      -webkit-overflow-scrolling:touch; max-width:860px; width:100%; margin:0 auto;
    }
    .status { color:var(--text-dim); padding:48px 20px; text-align:center; font-size:14px; }
    .status.error { color:#c44545; }
    .time-separator { text-align:center; padding:14px 0 8px; }
    .time-separator span { font-size:11px; color:var(--text-dim); background:var(--surface2); padding:4px 12px; border-radius:999px; font-weight:500; }
    .msg-group { display:flex; flex-direction:column; gap:2px; padding:2px 16px; animation:msgSlideIn .22s cubic-bezier(.2,.8,.2,1); }
    .msg-group + .msg-group { margin-top:6px; }
    @keyframes msgSlideIn { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:none; } }
    .msg {
      max-width:78%; padding:10px 14px; border-radius:var(--radius-lg);
      font-size:14.5px; line-height:1.55; word-break:break-word; overflow-wrap:anywhere; position:relative;
    }
    .msg-group .msg:not(:first-child) { padding-top:6px; }
    .msg-group .msg:not(:first-child) .sender-name { display:none; }
    .msg-group:not(.self) .msg {
      align-self:flex-start; background:var(--surface); border:1px solid var(--border);
      color:var(--text); box-shadow:var(--shadow-sm);
    }
    .msg-group.self .msg {
      align-self:flex-end; background:var(--accent); border:1px solid transparent;
      color:#fff; box-shadow:0 1px 2px var(--accent-glow);
    }
    .msg-group .msg:not(:first-child) { border-radius:8px var(--radius-lg) var(--radius-lg) 8px; }
    .msg-group.self .msg:not(:first-child) { border-radius:var(--radius-lg) 8px 8px var(--radius-lg); }
    .msg.event {
      align-self:center; display:inline-flex; align-items:center; justify-content:center; gap:6px;
      max-width:78%; background:rgba(217,119,6,.08); color:var(--text-dim);
      border:1px solid rgba(217,119,6,.18); box-shadow:none; border-radius:999px;
      padding:6px 12px; font-size:12.5px; line-height:1.45; text-align:center;
    }
    .msg.event::before { content:'\2726'; color:var(--amber); flex:0 0 auto; font-size:11px; }
    .sender-name { font-size:12px; color:var(--accent); font-weight:600; margin-bottom:4px; letter-spacing:-.01em; }
    .msg-group.self .sender-name { color:rgba(255,255,255,.85); }
    .msg-text { white-space:normal; word-wrap:break-word; overflow-wrap:break-word; line-height:1.6; overflow:hidden; }
    .msg-text p { margin:0 0 8px; } .msg-text p:last-child { margin-bottom:0; }
    .msg-text h1,.msg-text h2,.msg-text h3 { font-size:15px; font-weight:700; margin:10px 0 4px; letter-spacing:-.01em; }
    .msg-text code {
      background:var(--surface2); padding:2px 6px; border-radius:5px; font-size:13px;
      font-family:var(--font-mono); color:var(--accent-hover); border:1px solid var(--border);
    }
    .msg-group.self .msg-text code { background:rgba(255,255,255,.18); color:#fff; border-color:rgba(255,255,255,.2); }
    .msg-text pre {
      background:#1a1916; color:#e8e4dc; padding:14px 16px; border-radius:var(--radius);
      overflow-x:auto; max-width:100%; margin:10px 0; font-size:13px; line-height:1.65;
      font-family:var(--font-mono); border:1px solid #2d2c29;
    }
    .msg-text pre code { background:transparent; padding:0; color:inherit; font-size:inherit; border:none; }
    .msg-text ul,.msg-text ol { padding-left:1.5em; margin:6px 0; }
    .msg-text li { margin:3px 0; line-height:1.6; }
    .msg-text blockquote {
      border-left:3px solid var(--accent); padding:6px 12px; margin:8px 0;
      color:var(--text-2); background:var(--accent-soft); border-radius:0 var(--radius-sm) var(--radius-sm) 0;
    }
    .msg-text strong { font-weight:700; }
    .msg-text a { color:#60a5fa; text-decoration:underline; text-decoration-thickness:1px; text-decoration-color:rgba(59,130,246,.45); text-underline-offset:3px; word-break:break-all; }
    .msg-text a:hover { color:#93c5fd; }
    .msg-group.self .msg-text a { color:#dbeafe; text-decoration-color:rgba(219,234,254,.65); }
    .msg-group.self .msg-text a:hover { color:#fff; }
    .msg-text table { border-collapse:collapse; width:100%; margin:8px 0; font-size:13px; }
    .msg-text th,.msg-text td { border:1px solid var(--border); padding:5px 8px; text-align:left; }
    .msg-text th { background:var(--surface2); font-weight:600; }
    .msg-text img { max-width:100%; max-height:320px; border-radius:var(--radius); display:block; margin:4px 0; cursor:zoom-in; }
    .katex-display { margin:10px 0; overflow-x:auto; overflow-y:hidden; padding:2px 0; }
    .msg-meta-row { display:flex; align-items:flex-end; justify-content:flex-end; gap:6px; margin-top:4px; min-width:0; }
    .msg-time { font-size:11px; color:var(--text-faint); font-weight:500; }
    .msg-group.self .msg-time { color:rgba(255,255,255,.7); }
    .share-footer { text-align:center; padding:18px 16px 28px; color:var(--text-faint); font-size:12px; }
    .lightbox { position:fixed; inset:0; z-index:100; background:rgba(0,0,0,.82); display:none; align-items:center; justify-content:center; cursor:zoom-out; }
    .lightbox.active { display:flex; }
    .lightbox img { max-width:94vw; max-height:94vh; border-radius:var(--radius); box-shadow:0 8px 40px rgba(0,0,0,.5); }
    @media (max-width:640px) {
      .chat-header { padding:9px 14px; gap:10px; }
      .continue-btn { padding:9px 12px; font-size:12px; }
      .messages-area { padding:12px 0 24px; }
      .msg-group { padding:2px 10px; }
      .msg { max-width:88%; padding:9px 12px; font-size:14px; }
      .msg.event { max-width:88%; }
      .title { font-size:14px; }
    }
  </style>
</head>
<body>
  <main class="share-shell">
    <header class="chat-header">
      <div class="brand-mark">M</div>
      <div class="header-copy">
        <div id="title" class="title">加载中…</div>
        <div id="meta" class="meta">只读聊天记录</div>
      </div>
      <a id="continueBtn" class="continue-btn" href="#">在我的马哥中继续</a>
    </header>
    <section id="content" class="messages-area"><div class="status">正在加载聊天记录…</div></section>
    <footer class="share-footer">由 Myna 多智能体协作平台生成 · 只读分享</footer>
  </main>
  <div id="lightbox" class="lightbox"><img id="lightboxImg" alt=""></div>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked@9/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/dompurify@3/dist/purify.min.js"></script>
  <script>
    const shareToken = __TOKEN__;

    const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

    function extractMath(text) {
      const blocks = [];
      let t = String(text ?? '');
      t = t.replace(/\$\$([\s\S]+?)\$\$/g, (_, tex) => { blocks.push({ d: true, tex }); return '__MATH_' + (blocks.length - 1) + '_'; });
      t = t.replace(/\$([^$\n]+?)\$/g, (_, tex) => { blocks.push({ d: false, tex }); return '__MATH_' + (blocks.length - 1) + '_'; });
      return { t, blocks };
    }

    function restoreMath(html, blocks) {
      return html.replace(/__MATH_([0-9]+)_/g, (m, i) => {
        const b = blocks[+i];
        if (!b) return m;
        const raw = (b.d ? '$$' + b.tex + '$$' : '$' + b.tex + '$');
        if (!window.katex) return '<code>' + escapeHtml(raw) + '</code>';
        try { return katex.renderToString(b.tex, { displayMode: b.d, throwOnError: false }); }
        catch (e) { return '<code>' + escapeHtml(raw) + '</code>'; }
      });
    }

    function plainRender(text) {
      return '<p>' + escapeHtml(text).split('\n').join('<br>') + '</p>';
    }

    function renderMd(text) {
      const { t, blocks } = extractMath(text);
      let html;
      try {
        if (window.marked && window.DOMPurify) {
          marked.setOptions({ breaks: true, gfm: true });
          html = DOMPurify.sanitize(marked.parse(t), { USE_PROFILES: { html: true } });
        } else {
          html = plainRender(t);
        }
      } catch (e) { html = plainRender(t); }
      return restoreMath(html, blocks);
    }

    function parseDate(v) {
      try {
        if (!v) return null;
        const s = String(v);
        const d = new Date(s.includes('T') || s.endsWith('Z') ? s : s.replace(' ', 'T') + 'Z');
        return isNaN(d.getTime()) ? null : d;
      } catch { return null; }
    }

    function formatHM(d) {
      return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false });
    }

    function dayLabel(d) {
      const now = new Date();
      const startOf = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
      const diff = (startOf(now) - startOf(d)) / 86400000;
      if (diff === 0) return '今天';
      if (diff === 1) return '昨天';
      return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
    }

    document.getElementById('continueBtn').href = '/?continue_share=' + encodeURIComponent(shareToken);

    fetch('/share/' + encodeURIComponent(shareToken) + '/data').then(r => r.json()).then(data => {
      if (!data.ok) throw new Error(data.error || '加载失败');
      const room = data.result.room;
      const msgs = data.result.messages || [];
      document.title = (room.name || 'Myna') + ' · 聊天记录';
      document.getElementById('title').textContent = room.name || 'Myna 聊天记录';
      const firstDay = msgs.length ? parseDate(msgs[0].created_at) : null;
      document.getElementById('meta').textContent =
        msgs.length + ' 条消息 · 只读分享' + (firstDay ? ' · ' + dayLabel(firstDay) : '');

      const content = document.getElementById('content');
      let html = '';
      let lastDay = null;
      let lastKey = null;

      msgs.forEach(m => {
        const d = parseDate(m.created_at);
        const day = d ? dayLabel(d) : '';
        if (day && day !== lastDay) {
          html += `<div class="time-separator"><span>${escapeHtml(day)}</span></div>`;
          lastDay = day;
          lastKey = null;
        }
        const self = m.sender_id === 'user';
        const event = m.sender_id === 'system';
        const key = event ? 'system' : (m.sender_id + '|' + (m.sender_name || ''));
        if (key !== lastKey) {
          if (lastKey !== null) html += '</article>';
          const cls = 'msg-group' + (self ? ' self' : '') + (event ? ' event' : '');
          html += `<article class="${cls}">`;
          lastKey = key;
        }
        const timeHtml = (!event && d) ? `<div class="msg-meta-row"><span class="msg-time">${formatHM(d)}</span></div>` : '';
        const nameHtml = (!event && !self) ? `<div class="sender-name">${escapeHtml(m.sender_name || '助手')}</div>` : '';
        const bodyHtml = event ? escapeHtml(m.text || '') : renderMd(m.text || '');
        html += `<div class="${event ? 'msg event' : 'msg'}">${nameHtml}<div class="msg-text">${bodyHtml}</div>${timeHtml}</div>`;
      });
      if (lastKey !== null) html += '</article>';

      content.innerHTML = html || '<div class="status">暂无聊天记录</div>';

      content.querySelectorAll('.msg-text img').forEach(img => {
        img.loading = 'lazy';
        img.addEventListener('click', () => {
          document.getElementById('lightboxImg').src = img.src;
          document.getElementById('lightbox').classList.add('active');
        });
      });
      document.getElementById('lightbox').addEventListener('click', () => {
        document.getElementById('lightbox').classList.remove('active');
      });
    }).catch(err => {
      document.getElementById('content').innerHTML =
        `<div class="status error">${escapeHtml(err.message || '加载失败')}</div>`;
    });
  </script>
</body>
</html>"""
    import json as _json
    return template.replace("__TOKEN__", _json.dumps(str(token)))

@app.get("/share/{token}", response_class=HTMLResponse)
async def share_room_page(token: str):
    return HTMLResponse(_share_page_html(token))


@app.get("/share/{token}/data")
async def share_room_data(token: str):
    import re
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,80}", token or ""):
        return JSONResponse({"ok": False, "error": "分享不存在或已失效"}, status_code=404)
    path = APP_ROOT / "data" / "shares" / f"{token}.json"
    try:
        snapshot = json.loads(path.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return JSONResponse({"ok": False, "error": "分享不存在或已失效"}, status_code=404)
    safe_room = {"id": token, "name": snapshot.get("title"), "description": snapshot.get("description"), "type": "shared_snapshot"}
    return {"ok": True, "result": {"room": safe_room, "messages": snapshot.get("messages", [])}}


# Serve uploaded files
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# Serve frontend static files
frontend_dist = APP_ROOT / "src" / "web" / "public"
if frontend_dist.exists():
    class NoCacheIndexStaticFiles(StaticFiles):
        def file_response(self, full_path, stat_result, scope, status_code=200):
            response = super().file_response(full_path, stat_result, scope, status_code)
            if Path(full_path).name == "index.html":
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
            return response

    app.mount("/", NoCacheIndexStaticFiles(directory=str(frontend_dist), html=True), name="static")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3456"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
