const WebSocket = require('ws');
const db = require('../db');

class WSManager {
  constructor() {
    this.connections = new Map(); // agent_id -> Set<ws>
  }

  init(server) {
    this.wss = new WebSocket.Server({ server, path: '/ws' });

    this.wss.on('connection', (ws, req) => {
      // Expect ?api_key=xxx in URL
      const url = new URL(req.url, 'http://localhost');
      const apiKey = url.searchParams.get('api_key');

      if (!apiKey) {
        ws.close(4001, 'api_key required');
        return;
      }

      const agent = db.getAgentByKey(apiKey);
      if (!agent) {
        ws.close(4001, 'Invalid api_key');
        return;
      }

      // Register connection
      if (!this.connections.has(agent.id)) {
        this.connections.set(agent.id, new Set());
      }
      this.connections.get(agent.id).add(ws);
      db.updateAgentStatus(agent.id, 'online');

      console.log(`[WS] Agent "${agent.name}" connected`);

      // Handle incoming messages from agent via WebSocket
      ws.on('message', (data) => {
        try {
          const msg = JSON.parse(data.toString());
          this.handleAgentMessage(agent, msg);
        } catch (e) {
          ws.send(JSON.stringify({ error: 'Invalid JSON' }));
        }
      });

      ws.on('close', () => {
        this.connections.get(agent.id)?.delete(ws);
        if (this.connections.get(agent.id)?.size === 0) {
          this.connections.delete(agent.id);
          db.updateAgentStatus(agent.id, 'offline');
          console.log(`[WS] Agent "${agent.name}" disconnected`);
        }
      });

      // Send welcome
      ws.send(JSON.stringify({
        type: 'connected',
        agent: { id: agent.id, name: agent.name },
        rooms: db.getAgentRooms(agent.id)
      }));
    });
  }

  handleAgentMessage(agent, msg) {
    switch (msg.type) {
      case 'sendMessage': {
        const { room_id, text, parse_mode, reply_to_message_id, mentions } = msg;
        if (!room_id || !text) return;

        // Verify membership
        const rooms = db.getAgentRooms(agent.id);
        if (!rooms.find(r => r.id === room_id)) return;

        const message = db.createMessage(
          room_id, agent.id, text,
          parse_mode || 'markdown',
          reply_to_message_id || null,
          mentions || []
        );

        // Broadcast to room members
        const members = db.getRoomMembers(room_id);
        for (const member of members) {
          if (member.id !== agent.id) {
            const payload = {
              type: 'message',
              message_id: message.id,
              room_id,
              from: { id: agent.id, name: agent.name },
              text,
              parse_mode: parse_mode || 'markdown',
              reply_to_message_id: reply_to_message_id || null,
              mentions: mentions || [],
              date: new Date().toISOString()
            };
            db.pushUpdate(member.id, 'message', payload);
            this.notify(member.id, payload);
          }
        }

        // ACK back to sender
        this.notifyOne(agent.id, { type: 'message_sent', message_id: message.id, room_id });
        break;
      }

      case 'typing': {
        const { room_id } = msg;
        if (!room_id) return;
        const members = db.getRoomMembers(room_id);
        for (const member of members) {
          if (member.id !== agent.id) {
            this.notify(member.id, {
              type: 'typing',
              room_id,
              from: { id: agent.id, name: agent.name }
            });
          }
        }
        break;
      }
    }
  }

  notify(agentId, payload) {
    const conns = this.connections.get(agentId);
    if (!conns) return;
    const data = JSON.stringify(payload);
    for (const ws of conns) {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data);
      }
    }
  }

  notifyOne(agentId, payload) {
    this.notify(agentId, payload);
  }

  broadcastToRoom(roomId, payload, excludeAgentId = null) {
    const members = db.getRoomMembers(roomId);
    const data = JSON.stringify(payload);
    for (const member of members) {
      if (member.id === excludeAgentId) continue;
      const conns = this.connections.get(member.id);
      if (!conns) continue;
      for (const ws of conns) {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(data);
        }
      }
    }
  }

  getOnlineAgents() {
    return [...this.connections.keys()];
  }
}

module.exports = WSManager;
