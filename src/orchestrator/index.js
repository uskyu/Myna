const express = require('express');
const db = require('../db');

const router = express.Router();

// Admin auth middleware
router.use((req, res, next) => {
  const secretKey = process.env.SECRET_KEY;
  if (!secretKey || secretKey === 'change-me-to-a-random-string') {
    // No auth in dev mode
    return next();
  }
  const auth = req.headers.authorization;
  if (!auth || auth !== `Bearer ${secretKey}`) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
});

// === Agents ===

// GET /admin/agents - List all agents
router.get('/agents', (req, res) => {
  const agents = db.listAgents();
  res.json({ ok: true, result: agents });
});

// POST /admin/agents - Create agent
router.post('/agents', (req, res) => {
  const { name, description } = req.body;
  if (!name) {
    return res.status(400).json({ ok: false, error: 'name is required' });
  }
  const agent = db.createAgent(name, description || '');
  res.json({ ok: true, result: agent });
});

// DELETE /admin/agents/:id - Delete agent
router.delete('/agents/:id', (req, res) => {
  db.deleteAgent(req.params.id);
  res.json({ ok: true });
});

// === Rooms ===

// GET /admin/rooms - List all rooms
router.get('/rooms', (req, res) => {
  const rooms = db.listRooms();
  // Attach member count
  const result = rooms.map(r => ({
    ...r,
    members: db.getRoomMembers(r.id)
  }));
  res.json({ ok: true, result });
});

// POST /admin/rooms - Create room
router.post('/rooms', (req, res) => {
  const { name, description } = req.body;
  if (!name) {
    return res.status(400).json({ ok: false, error: 'name is required' });
  }
  const room = db.createRoom(name, description || '');
  res.json({ ok: true, result: room });
});

// DELETE /admin/rooms/:id - Delete room
router.delete('/rooms/:id', (req, res) => {
  db.deleteRoom(req.params.id);
  res.json({ ok: true });
});

// POST /admin/rooms/:id/members - Add member to room
router.post('/rooms/:id/members', (req, res) => {
  const { agent_id, role } = req.body;
  if (!agent_id) {
    return res.status(400).json({ ok: false, error: 'agent_id is required' });
  }
  db.addMember(req.params.id, agent_id, role || 'member');
  res.json({ ok: true });
});

// DELETE /admin/rooms/:id/members/:agent_id - Remove member
router.delete('/rooms/:id/members/:agent_id', (req, res) => {
  db.removeMember(req.params.id, req.params.agent_id);
  res.json({ ok: true });
});

// GET /admin/rooms/:id/messages - Get room messages
router.get('/rooms/:id/messages', (req, res) => {
  const { limit, before_id } = req.query;
  const messages = db.getRoomMessages(req.params.id, parseInt(limit) || 50, before_id ? parseInt(before_id) : null);
  res.json({ ok: true, result: messages });
});

// POST /admin/rooms/:id/broadcast - Admin sends message to room (as system)
router.post('/rooms/:id/broadcast', (req, res) => {
  const { text } = req.body;
  if (!text) {
    return res.status(400).json({ ok: false, error: 'text is required' });
  }
  
  // Create a system agent if not exists
  let systemAgent = db.getAgentByKey('__system__');
  if (!systemAgent) {
    const { db: rawDb } = require('../db');
    rawDb.prepare(`INSERT OR IGNORE INTO agents (id, name, api_key, description, status) VALUES ('system', 'System', '__system__', 'System messages', 'online')`).run();
    systemAgent = { id: 'system', name: 'System' };
  }

  const message = db.createMessage(req.params.id, systemAgent.id, text, 'markdown');
  
  // Notify all members
  const members = db.getRoomMembers(req.params.id);
  const wsManager = req.app.get('wsManager');
  for (const member of members) {
    db.pushUpdate(member.id, 'message', {
      message_id: message.id,
      room_id: req.params.id,
      from: { id: 'system', name: 'System' },
      text,
      parse_mode: 'markdown',
      date: new Date().toISOString()
    });
    if (wsManager) {
      wsManager.notify(member.id, {
        type: 'message',
        message_id: message.id,
        room_id: req.params.id,
        from: { id: 'system', name: 'System' },
        text,
        parse_mode: 'markdown',
        date: new Date().toISOString()
      });
    }
  }

  res.json({ ok: true, result: message });
});

module.exports = router;
