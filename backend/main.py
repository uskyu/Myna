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

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

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
from routes.system_agent import router as system_agent_router
from workflow_engine import WorkflowRunner, WorkflowScheduler
from credentials import CredentialStore
from system_agent import SystemAgent
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

    # Initialize credential store and system agent
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
    system_agent = SystemAgent(credential_store)
    
    # Store in app state
    app.state.db = db
    app.state.ws_manager = ws_manager
    app.state.workflow_runner = workflow_runner
    app.state.workflow_scheduler = workflow_scheduler
    app.state.credential_store = credential_store
    app.state.system_agent = system_agent
    
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
app.include_router(system_agent_router, prefix="/admin/system-agent")
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


def _share_page_html(room_id: str) -> str:
    room_json = json.dumps(room_id)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Myna 房间分享</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg:#f7f3ea; --surface:#fffaf1; --surface2:#f2eadc; --text:#1f2933; --text-dim:#6b7280;
      --text-faint:#9ca3af; --border:rgba(45,106,79,.18); --accent:#2d6a4f; --accent-soft:#e8f0eb;
      --accent-glow:rgba(45,106,79,.18); --radius-lg:18px; --shadow-sm:0 1px 2px rgba(0,0,0,.05);
      --header-height:64px;
    }}
    @media (prefers-color-scheme: dark) {{ :root {{ --bg:#11140f; --surface:#1a211b; --surface2:#222b24; --text:#f3f5ef; --text-dim:#b7c0b4; --text-faint:#879083; --border:rgba(232,240,235,.16); --accent:#7fb096; --accent-soft:#233529; --accent-glow:rgba(127,176,150,.22); }} }}
    * {{ box-sizing:border-box; }}
    html, body {{ margin:0; min-height:100%; }}
    body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:var(--bg); color:var(--text); }}
    .share-shell {{ min-height:100vh; display:flex; flex-direction:column; background:var(--bg); }}
    .chat-header {{ height:var(--header-height); display:flex; flex-direction:column; justify-content:center; padding:0 20px; background:var(--surface); border-bottom:1px solid var(--border); flex-shrink:0; }}
    .title {{ min-width:0; overflow:hidden; display:-webkit-box; -webkit-box-orient:vertical; -webkit-line-clamp:1; line-clamp:1; font-size:16px; font-weight:700; line-height:1.25; color:var(--text); }}
    .meta {{ margin-top:5px; color:var(--text-dim); font-size:12px; }}
    .messages-area {{ flex:1; overflow-y:auto; padding:16px 20px 24px; display:flex; flex-direction:column; gap:6px; -webkit-overflow-scrolling:touch; }}
    .status {{ color:var(--text-dim); padding:30px 4px; text-align:center; }} .error {{ color:#dc2626; }}
    .msg-group {{ display:flex; flex-direction:column; gap:2px; }}
    .msg {{ max-width:78%; padding:10px 14px; border-radius:var(--radius-lg); font-size:14.5px; line-height:1.55; word-break:break-word; position:relative; }}
    .msg-group:not(.self) .msg {{ align-self:flex-start; background:var(--surface); border:1px solid var(--border); color:var(--text); box-shadow:var(--shadow-sm); }}
    .msg-group.self .msg {{ align-self:flex-end; background:var(--accent); border:1px solid transparent; color:white; box-shadow:0 1px 2px var(--accent-glow); }}
    .msg.event {{ align-self:center; max-width:78%; background:rgba(217,119,6,.08); color:var(--text-dim); border:1px solid rgba(217,119,6,.18); box-shadow:none; border-radius:999px; padding:6px 12px; font-size:12.5px; text-align:center; }}
    .sender-name {{ font-size:12px; color:var(--accent); font-weight:600; margin-bottom:4px; letter-spacing:-.01em; }}
    .msg-group.self .sender-name {{ color:rgba(255,255,255,.85); }}
    .msg-text {{ white-space:normal; word-wrap:break-word; overflow-wrap:break-word; line-height:1.6; overflow:hidden; }}
    .msg-text p {{ margin:0 0 8px 0; }} .msg-text p:last-child {{ margin-bottom:0; }}
    .msg-text pre {{ background:var(--surface2); padding:10px; border-radius:10px; overflow:auto; max-width:100%; }}
    .msg-text code {{ background:var(--surface2); padding:1px 4px; border-radius:4px; font-size:.92em; }}
    .msg-group.self .msg-text code {{ background:rgba(255,255,255,.16); }}
    .msg-text ul, .msg-text ol {{ padding-left:1.5em; margin:6px 0; }} .msg-text li {{ margin:3px 0; }}
    .msg-text blockquote {{ margin:8px 0; padding-left:10px; border-left:3px solid var(--border); color:var(--text-dim); }}
    .msg-text a {{ color:var(--accent); text-decoration:underline; text-underline-offset:2px; word-break:break-all; }}
    .msg-group.self .msg-text a {{ color:#bbf7d0; }}
    .msg-meta-row {{ display:flex; align-items:flex-end; justify-content:flex-end; gap:6px; margin-top:4px; min-width:0; }}
    .msg-speaker, .msg-time {{ font-size:11px; color:var(--text-faint); font-weight:500; }}
    .msg-group.self .msg-speaker, .msg-group.self .msg-time {{ color:rgba(255,255,255,.7); }}
    @media (max-width:640px) {{ .chat-header {{ height:56px; padding:0 14px; }} .messages-area {{ padding:12px 10px 18px; }} .msg {{ max-width:88%; padding:9px 12px; font-size:14px; }} .msg.event {{ max-width:88%; }} .title {{ font-size:15px; }} }}
  </style>
</head>
<body>
  <main class="share-shell">
    <header class="chat-header"><div id="title" class="title">Myna 房间分享</div><div id="meta" class="meta">只读聊天记录</div></header>
    <section id="content" class="messages-area"><div class="status">正在加载聊天记录...</div></section>
  </main>
  <script>
    const roomId = {room_json};
    const escapeHtml = (s) => String(s ?? '').replace(/[&<>\"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[c]));
    const linkifyHiddenUrls = (s) => escapeHtml(s).replace(/https?:\/\/[^\s<]+/g, url => `<a href="${{url}}" target="_blank" rel="noopener noreferrer">查看链接</a>`).replace(/\n/g, '<br>');
    const formatTime = (v) => {{ try {{ return v ? new Date(v).toLocaleString() : ''; }} catch {{ return v || ''; }} }};
    const isSelf = (m) => m.sender_id === 'user';
    const isEvent = (m) => m.sender_id === 'system' || m.event;
    fetch(`/share/${{encodeURIComponent(roomId)}}/data`).then(r => r.json()).then(data => {{
      if (!data.ok) throw new Error(data.error || '加载失败');
      document.title = `${{data.result.room.name}} - Myna 房间分享`;
      document.getElementById('title').textContent = data.result.room.name || 'Myna 房间分享';
      document.getElementById('meta').textContent = `${{data.result.messages.length}} 条消息 · 只读分享`;
      const html = data.result.messages.map(m => {{
        const cls = isEvent(m) ? 'msg event' : 'msg';
        const groupCls = `msg-group${{isSelf(m) ? ' self' : ''}}${{isEvent(m) ? ' event' : ''}}`;
        const sender = escapeHtml(m.sender_name || m.sender_id || '未知');
        return `<article class="${{groupCls}}"><div class="${{cls}}">${{!isEvent(m) ? `<div class="sender-name">${{sender}}</div>` : ''}}<div class="msg-text"><p>${{linkifyHiddenUrls(m.text || '')}}</p></div>${{!isEvent(m) ? `<div class="msg-meta-row"><span class="msg-speaker">${{sender}}</span><span class="msg-time">${{escapeHtml(formatTime(m.created_at))}}</span></div>` : ''}}</div></article>`;
      }}).join('');
      document.getElementById('content').innerHTML = html || '<div class="status">暂无聊天记录</div>';
    }}).catch(err => {{
      document.getElementById('content').innerHTML = `<div class="status error">${{escapeHtml(err.message || '加载失败')}}</div>`;
    }});
  </script>
</body>
</html>"""


@app.get("/share/{room_id}", response_class=HTMLResponse)
async def share_room_page(room_id: str):
    return HTMLResponse(_share_page_html(room_id))


@app.get("/share/{room_id}/data")
async def share_room_data(room_id: str):
    room = app.state.db.get_room(room_id)
    if not room:
        return JSONResponse({"ok": False, "error": "Room not found"}, status_code=404)
    messages = app.state.db.get_all_room_messages(room_id)
    safe_room = {"id": room.get("id"), "name": room.get("name"), "description": room.get("description"), "type": room.get("type")}
    return {"ok": True, "result": {"room": safe_room, "messages": messages}}


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
