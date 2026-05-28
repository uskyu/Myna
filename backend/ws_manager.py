"""
WebSocket connection manager for UI clients and agent connections.
"""
import json
import asyncio
from fastapi import WebSocket


class WSManager:
    def __init__(self):
        self.ui_connections: set[WebSocket] = set()
        self.agent_connections: dict[str, set[WebSocket]] = {}  # agent_id -> set of ws
        self.active_streams: dict[str, dict] = {}  # stream_id -> info

    def add_ui(self, ws: WebSocket):
        self.ui_connections.add(ws)

    def remove_ui(self, ws: WebSocket):
        self.ui_connections.discard(ws)

    def add_agent(self, agent_id: str, ws: WebSocket):
        if agent_id not in self.agent_connections:
            self.agent_connections[agent_id] = set()
        self.agent_connections[agent_id].add(ws)

    def remove_agent(self, agent_id: str, ws: WebSocket):
        if agent_id in self.agent_connections:
            self.agent_connections[agent_id].discard(ws)
            if not self.agent_connections[agent_id]:
                del self.agent_connections[agent_id]

    def get_online_agents(self) -> list[str]:
        return list(self.agent_connections.keys())

    async def notify_ui(self, payload: dict):
        """Send event to all UI clients."""
        # Track active streams
        if payload.get("type") == "stream_start":
            self.active_streams[payload["stream_id"]] = {
                "room_id": payload.get("room_id"),
                "agent_id": payload.get("agent_id"),
                "agent_name": payload.get("agent_name"),
                "thread_id": payload.get("thread_id"),
                "text": "",
                "tool_calls": [],
            }
        elif payload.get("type") == "stream_end":
            self.active_streams.pop(payload.get("stream_id", ""), None)
        elif payload.get("type") == "stream_token":
            stream = self.active_streams.get(payload.get("stream_id", ""))
            if stream:
                stream["text"] += payload.get("chunk", "")
        elif payload.get("type") == "tool_call":
            stream = self.active_streams.get(payload.get("stream_id", ""))
            if stream:
                stream["tool_calls"].append({
                    "name": payload.get("tool"),
                    "summary": payload.get("args_summary", ""),
                    "status": "running",
                    "result": None,
                })
        elif payload.get("type") == "tool_result":
            stream = self.active_streams.get(payload.get("stream_id", ""))
            if stream:
                # Update the last matching running tool call
                for tc in reversed(stream["tool_calls"]):
                    if tc["name"] == payload.get("tool") and tc["status"] == "running":
                        tc["status"] = "done" if payload.get("ok") else "error"
                        tc["result"] = payload.get("output", "")[:200]
                        break

        data = json.dumps(payload)
        dead = set()
        for ws in self.ui_connections:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        self.ui_connections -= dead

    async def notify_agent(self, agent_id: str, payload: dict):
        """Send event to a specific agent's connections."""
        conns = self.agent_connections.get(agent_id, set())
        if not conns:
            return
        data = json.dumps(payload)
        dead = set()
        for ws in conns:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        conns -= dead

    def notify_ui_sync(self, payload: dict):
        """Fire-and-forget UI notification from sync context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.notify_ui(payload))
            else:
                loop.run_until_complete(self.notify_ui(payload))
        except RuntimeError:
            pass
