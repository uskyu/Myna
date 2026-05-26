const express = require('express');
const { marked } = require('marked');
const db = require('../db');

const router = express.Router();

// Middleware: extract API key and validate agent
router.use('/bot:api_key', (req, res, next) => {
  const agent = db.getAgentByKey(req.params.api_key);
  if (!agent) {
    return res.status(401).json({ ok: false, error: 'Unauthorized: invalid API key' });
  }
  req.agent = agent;
  // Update status to online
  db.updateAgentStatus(agent.id, 'online');
  next();
});

// GET /bot{key}/getMe - Get bot info
router.get('/bot:api_key/getMe', (req, res) => {
  const { id, name, description, status } = req.agent;
  res.json({ ok: true, result: { id, name, description, status } });
});

// POST /bot{key}/sendMessage - Send a message to a room
router.post('/bot:api_key/sendMessage', (req, res) => {
  const { room_id, text, parse_mode, reply_to_message_id, mentions } = req.body;

  if (!room_id || !text) {
    return res.status(400).json({ ok: false, error: 'room_id and text are required' });
  }

  // Check agent is member of room
  const rooms = db.getAgentRooms(req.agent.id);
  if (!rooms.find(r => r.id === room_id)) {
    return res.status(403).json({ ok: false, error: 'Agent is not a member of this room' });
  }

  const message = db.createMessage(
    room_id,
    req.agent.id,
    text,
    parse_mode || 'markdown',
    reply_to_message_id || null,
    mentions || []
  );

  // Push updates to other room members
  const members = db.getRoomMembers(room_id);
  for (const member of members) {
    if (member.id !== req.agent.id) {
      db.pushUpdate(member.id, 'message', {
        message_id: message.id,
        room_id,
        from: { id: req.agent.id, name: req.agent.name },
        text,
        parse_mode: parse_mode || 'markdown',
        reply_to_message_id: reply_to_message_id || null,
        mentions: mentions || [],
        date: new Date().toISOString()
      });

      // Notify via WebSocket if connected
      const wsManager = req.app.get('wsManager');
      if (wsManager) {
        wsManager.notify(member.id, {
          type: 'message',
          message_id: message.id,
          room_id,
          from: { id: req.agent.id, name: req.agent.name },
          text,
          parse_mode: parse_mode || 'markdown',
          reply_to_message_id: reply_to_message_id || null,
          mentions: mentions || [],
          date: new Date().toISOString()
        });
      }
    }
  }

  res.json({ ok: true, result: message });
});

// POST /bot{key}/getUpdates - Long polling for updates
router.post('/bot:api_key/getUpdates', (req, res) => {
  const { offset, limit } = req.body;
  const updates = db.getUpdates(req.agent.id, offset || 0, limit || 100);
  res.json({ ok: true, result: updates });
});

// GET /bot{key}/getUpdates - Also support GET
router.get('/bot:api_key/getUpdates', (req, res) => {
  const offset = parseInt(req.query.offset) || 0;
  const limit = parseInt(req.query.limit) || 100;
  const updates = db.getUpdates(req.agent.id, offset, limit);
  res.json({ ok: true, result: updates });
});

// GET /bot{key}/getRooms - List rooms the agent is in
router.get('/bot:api_key/getRooms', (req, res) => {
  const rooms = db.getAgentRooms(req.agent.id);
  res.json({ ok: true, result: rooms });
});

// GET /bot{key}/getRoomMembers - List members of a room
router.get('/bot:api_key/getRoomMembers', (req, res) => {
  const { room_id } = req.query;
  if (!room_id) {
    return res.status(400).json({ ok: false, error: 'room_id is required' });
  }
  const members = db.getRoomMembers(room_id);
  res.json({ ok: true, result: members });
});

// GET /bot{key}/getMessages - Get room message history
router.get('/bot:api_key/getMessages', (req, res) => {
  const { room_id, limit, before_id } = req.query;
  if (!room_id) {
    return res.status(400).json({ ok: false, error: 'room_id is required' });
  }
  const messages = db.getRoomMessages(room_id, parseInt(limit) || 50, before_id ? parseInt(before_id) : null);
  
  // Render markdown for each message
  const rendered = messages.map(m => ({
    ...m,
    html: m.parse_mode === 'markdown' ? marked(m.text) : m.text,
    mentions: JSON.parse(m.mentions || '[]')
  }));
  
  res.json({ ok: true, result: rendered });
});

// POST /bot{key}/setWebhook - Set webhook URL for push notifications
router.post('/bot:api_key/setWebhook', (req, res) => {
  const { url } = req.body;
  // TODO: store webhook URL and push updates to it
  res.json({ ok: true, result: { url, status: 'webhook support coming soon' } });
});

module.exports = router;
