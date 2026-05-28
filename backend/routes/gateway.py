"""
Telegram Bot API-compatible gateway routes.
/bot{api_key}/getMe, /bot{api_key}/sendMessage, etc.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/bot{api_key}/getMe")
async def get_me(api_key: str, request: Request):
    db = request.app.state.db
    agent = db.get_agent_by_key(api_key)
    if not agent:
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    db.update_agent_status(agent["id"], "online")
    return {"ok": True, "result": {"id": agent["id"], "name": agent["name"],
                                    "description": agent["description"], "status": agent["status"]}}


@router.post("/bot{api_key}/sendMessage")
async def send_message(api_key: str, request: Request):
    db = request.app.state.db
    ws_manager = request.app.state.ws_manager
    agent = db.get_agent_by_key(api_key)
    if not agent:
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)

    body = await request.json()
    room_id = body.get("room_id")
    text = body.get("text")
    if not room_id or not text:
        return JSONResponse({"ok": False, "error": "room_id and text required"}, status_code=400)

    rooms = db.get_agent_rooms(agent["id"])
    if not any(r["id"] == room_id for r in rooms):
        return JSONResponse({"ok": False, "error": "Not a member"}, status_code=403)

    message = db.create_message(room_id, agent["id"], text,
                                body.get("parse_mode", "markdown"),
                                body.get("reply_to_message_id"),
                                body.get("mentions", []))

    members = db.get_room_members(room_id)
    from datetime import datetime
    for member in members:
        if member["id"] != agent["id"]:
            payload = {
                "type": "message", "message_id": message["id"], "room_id": room_id,
                "from": {"id": agent["id"], "name": agent["name"]},
                "text": text, "parse_mode": body.get("parse_mode", "markdown"),
                "date": datetime.now().isoformat()
            }
            db.push_update(member["id"], "message", payload)
            await ws_manager.notify_agent(member["id"], payload)

    return {"ok": True, "result": message}


@router.post("/bot{api_key}/getUpdates")
async def get_updates_post(api_key: str, request: Request):
    db = request.app.state.db
    agent = db.get_agent_by_key(api_key)
    if not agent:
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    body = await request.json()
    updates = db.get_updates(agent["id"], body.get("offset", 0), body.get("limit", 100))
    return {"ok": True, "result": updates}


@router.get("/bot{api_key}/getUpdates")
async def get_updates_get(api_key: str, request: Request):
    db = request.app.state.db
    agent = db.get_agent_by_key(api_key)
    if not agent:
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    offset = int(request.query_params.get("offset", "0"))
    limit = int(request.query_params.get("limit", "100"))
    updates = db.get_updates(agent["id"], offset, limit)
    return {"ok": True, "result": updates}


@router.get("/bot{api_key}/getRooms")
async def get_rooms(api_key: str, request: Request):
    db = request.app.state.db
    agent = db.get_agent_by_key(api_key)
    if not agent:
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    rooms = db.get_agent_rooms(agent["id"])
    return {"ok": True, "result": rooms}


@router.get("/bot{api_key}/getRoomMembers")
async def get_room_members(api_key: str, request: Request):
    db = request.app.state.db
    agent = db.get_agent_by_key(api_key)
    if not agent:
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    room_id = request.query_params.get("room_id")
    if not room_id:
        return JSONResponse({"ok": False, "error": "room_id required"}, status_code=400)
    members = db.get_room_members(room_id)
    return {"ok": True, "result": members}


@router.get("/bot{api_key}/getMessages")
async def get_messages(api_key: str, request: Request):
    db = request.app.state.db
    agent = db.get_agent_by_key(api_key)
    if not agent:
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    room_id = request.query_params.get("room_id")
    if not room_id:
        return JSONResponse({"ok": False, "error": "room_id required"}, status_code=400)
    limit = int(request.query_params.get("limit", "50"))
    before_id = request.query_params.get("before_id")
    messages = db.get_room_messages(room_id, limit, int(before_id) if before_id else None)
    return {"ok": True, "result": messages}
