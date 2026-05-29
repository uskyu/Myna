"""
API routes for System Agent and Credential management.
"""

import uuid
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

router = APIRouter()


# ─── Credential CRUD ───────────────────────────────────────────────────────────

@router.get("/credentials")
async def list_credentials(request: Request):
    """List all stored credentials (masked values)."""
    store = request.app.state.credential_store
    if not store:
        return JSONResponse({"ok": False, "error": "Credential store not initialized"}, status_code=500)
    creds = store.list_all()
    return {"ok": True, "credentials": creds}


@router.post("/credentials")
async def add_credential(request: Request):
    """Add a new credential."""
    store = request.app.state.credential_store
    if not store:
        return JSONResponse({"ok": False, "error": "Credential store not initialized"}, status_code=500)

    body = await request.json()
    name = body.get("name", "").strip()
    cred_type = body.get("type", "").strip()
    value = body.get("value", "").strip()
    metadata = body.get("metadata", {})

    if not name:
        return JSONResponse({"ok": False, "error": "Name is required"}, status_code=400)
    if not cred_type:
        return JSONResponse({"ok": False, "error": "Type is required"}, status_code=400)
    if not value:
        return JSONResponse({"ok": False, "error": "Value is required"}, status_code=400)
    if cred_type not in store.TYPES:
        return JSONResponse({"ok": False, "error": f"Invalid type. Must be one of: {store.TYPES}"}, status_code=400)

    cred_id = str(uuid.uuid4())[:8]
    try:
        result = store.add(cred_id, name, cred_type, value, metadata)
        return {"ok": True, "credential": result}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.put("/credentials/{cred_id}")
async def update_credential(cred_id: str, request: Request):
    """Update an existing credential."""
    store = request.app.state.credential_store
    if not store:
        return JSONResponse({"ok": False, "error": "Credential store not initialized"}, status_code=500)

    existing = store.get(cred_id)
    if not existing:
        return JSONResponse({"ok": False, "error": "Credential not found"}, status_code=404)

    body = await request.json()
    name = body.get("name")
    value = body.get("value")
    metadata = body.get("metadata")

    store.update(cred_id, name=name, value=value, metadata=metadata)
    updated = store.get(cred_id)
    return {"ok": True, "credential": updated}


@router.delete("/credentials/{cred_id}")
async def delete_credential(cred_id: str, request: Request):
    """Delete a credential."""
    store = request.app.state.credential_store
    if not store:
        return JSONResponse({"ok": False, "error": "Credential store not initialized"}, status_code=500)

    existing = store.get(cred_id)
    if not existing:
        return JSONResponse({"ok": False, "error": "Credential not found"}, status_code=404)

    store.delete(cred_id)
    return {"ok": True, "message": f"Credential '{existing['name']}' deleted"}


# ─── System Agent Status & Control ─────────────────────────────────────────────

@router.get("/status")
async def system_agent_status(request: Request):
    """Get system agent status."""
    agent = request.app.state.system_agent
    if not agent:
        return JSONResponse({"ok": False, "error": "System agent not initialized"}, status_code=500)
    return {"ok": True, **agent.get_status()}


@router.get("/access-log")
async def system_agent_access_log(request: Request):
    """Get system agent access log."""
    agent = request.app.state.system_agent
    if not agent:
        return JSONResponse({"ok": False, "error": "System agent not initialized"}, status_code=500)

    limit = int(request.query_params.get("limit", "50"))
    return {"ok": True, "log": agent.get_access_log(limit)}


@router.post("/execute")
async def system_agent_execute(request: Request):
    """Execute a system agent action (for testing / admin use)."""
    agent = request.app.state.system_agent
    if not agent:
        return JSONResponse({"ok": False, "error": "System agent not initialized"}, status_code=500)

    body = await request.json()
    action = body.get("action", "")
    params = body.get("params", {})
    requester = body.get("requester", "admin")

    if not action:
        return JSONResponse({"ok": False, "error": "Action is required"}, status_code=400)

    result = agent.handle_request(action, params, requester)
    if result["ok"]:
        return result
    else:
        return JSONResponse(result, status_code=400)


@router.get("/repos")
async def list_repos(request: Request):
    """List repos in the system agent workspace."""
    agent = request.app.state.system_agent
    if not agent:
        return JSONResponse({"ok": False, "error": "System agent not initialized"}, status_code=500)

    result = agent.handle_request("list_repos", {}, "admin")
    return result
