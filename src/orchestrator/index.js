const express = require('express');
const { getDatabase } = require('../db/index');

const router = express.Router();

// Admin auth middleware
router.use((req, res, next) => {
  const secretKey = process.env.SECRET_KEY;
  if (!secretKey || secretKey === 'change-me-to-a-random-string') {
    return next();
  }
  const auth = req.headers.authorization;
  if (!auth || auth !== `Bearer ${secretKey}`) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
});

// === Agents ===

router.get('/agents', async (req, res) => {
  const db = getDatabase();
  const agents = await db.listAgents();
  res.json({ ok: true, result: agents });
});

router.post('/agents', async (req, res) => {
  const db = getDatabase();
  const { name, description } = req.body;
  if (!name) {
    return res.status(400).json({ ok: false, error: 'name is required' });
  }
  const agent = await db.createAgent(name, description || '');
  res.json({ ok: true, result: agent });
});

router.delete('/agents/:id', async (req, res) => {
  const db = getDatabase();
  await db.deleteAgent(req.params.id);
  res.json({ ok: true });
});

// === Rooms ===

router.get('/rooms', async (req, res) => {
  const db = getDatabase();
  const rooms = await db.listRooms();
  const result = [];
  for (const r of rooms) {
    const members = await db.getRoomMembers(r.id);
    result.push({ ...r, members });
  }
  res.json({ ok: true, result });
});

router.post('/rooms', async (req, res) => {
  const db = getDatabase();
  const { name, description } = req.body;
  if (!name) {
    return res.status(400).json({ ok: false, error: 'name is required' });
  }
  const room = await db.createRoom(name, description || '');
  res.json({ ok: true, result: room });
});

router.delete('/rooms/:id', async (req, res) => {
  const db = getDatabase();
  await db.deleteRoom(req.params.id);
  res.json({ ok: true });
});

// Room membership
router.post('/rooms/:id/members', async (req, res) => {
  const db = getDatabase();
  const { agent_id, role } = req.body;
  if (!agent_id) {
    return res.status(400).json({ ok: false, error: 'agent_id is required' });
  }
  await db.addMember(req.params.id, agent_id, role || 'member');
  res.json({ ok: true });
});

router.delete('/rooms/:id/members/:agent_id', async (req, res) => {
  const db = getDatabase();
  await db.removeMember(req.params.id, req.params.agent_id);
  res.json({ ok: true });
});

// Room messages
router.get('/rooms/:id/messages', async (req, res) => {
  const db = getDatabase();
  const { limit, before_id } = req.query;
  const messages = await db.getRoomMessages(req.params.id, parseInt(limit) || 50, before_id ? parseInt(before_id) : null);
  res.json({ ok: true, result: messages });
});

// Broadcast (admin sends as System)
router.post('/rooms/:id/broadcast', async (req, res) => {
  const db = getDatabase();
  const { text } = req.body;
  if (!text) {
    return res.status(400).json({ ok: false, error: 'text is required' });
  }

  // Ensure system agent exists
  let systemAgent = await db.getAgentByKey('__system__');
  if (!systemAgent) {
    // Create system agent directly via SQLite (special case)
    const sqlite = db;
    if (sqlite.db) {
      sqlite.db.prepare(`INSERT OR IGNORE INTO agents (id, name, api_key, description, status) VALUES ('system', 'System', '__system__', 'System messages', 'online')`).run();
    }
    systemAgent = { id: 'system', name: 'System' };
  }

  const message = await db.createMessage(req.params.id, systemAgent.id, text, 'markdown');

  // Notify all members
  const members = await db.getRoomMembers(req.params.id);
  const wsManager = req.app.get('wsManager');
  for (const member of members) {
    await db.pushUpdate(member.id, 'message', {
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
