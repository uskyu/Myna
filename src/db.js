const Database = require('better-sqlite3');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, '..', 'db');
const db = new Database(path.join(DATA_DIR, 'hermes-hub.sqlite'));

// WAL mode for better concurrency
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

// Schema
db.exec(`
  CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    api_key TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    avatar TEXT DEFAULT '',
    status TEXT DEFAULT 'offline',
    container_id TEXT DEFAULT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS rooms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    type TEXT DEFAULT 'group',
    created_at TEXT DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS room_members (
    room_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    role TEXT DEFAULT 'member',
    joined_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (room_id, agent_id),
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    text TEXT NOT NULL,
    parse_mode TEXT DEFAULT 'markdown',
    reply_to_message_id INTEGER DEFAULT NULL,
    mentions TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
    FOREIGN KEY (sender_id) REFERENCES agents(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    consumed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_messages_room ON messages(room_id, id);
  CREATE INDEX IF NOT EXISTS idx_updates_agent ON updates(agent_id, consumed, id);
  CREATE INDEX IF NOT EXISTS idx_agents_api_key ON agents(api_key);
`);

// Agent operations
const createAgent = (name, description = '') => {
  const id = uuidv4();
  const api_key = uuidv4().replace(/-/g, '') + uuidv4().replace(/-/g, '');
  db.prepare(`INSERT INTO agents (id, name, api_key, description) VALUES (?, ?, ?, ?)`)
    .run(id, name, api_key, description);
  return { id, name, api_key, description };
};

const getAgentByKey = (api_key) => {
  return db.prepare(`SELECT * FROM agents WHERE api_key = ?`).get(api_key);
};

const getAgentById = (id) => {
  return db.prepare(`SELECT * FROM agents WHERE id = ?`).get(id);
};

const listAgents = () => {
  return db.prepare(`SELECT id, name, description, avatar, status, container_id, created_at FROM agents`).all();
};

const updateAgentStatus = (id, status) => {
  db.prepare(`UPDATE agents SET status = ?, updated_at = datetime('now') WHERE id = ?`).run(status, id);
};

const updateAgentContainer = (id, container_id) => {
  db.prepare(`UPDATE agents SET container_id = ?, updated_at = datetime('now') WHERE id = ?`).run(container_id, id);
};

const deleteAgent = (id) => {
  db.prepare(`DELETE FROM agents WHERE id = ?`).run(id);
};

// Room operations
const createRoom = (name, description = '') => {
  const id = uuidv4();
  db.prepare(`INSERT INTO rooms (id, name, description) VALUES (?, ?, ?)`)
    .run(id, name, description);
  return { id, name, description };
};

const getRoom = (id) => {
  return db.prepare(`SELECT * FROM rooms WHERE id = ?`).get(id);
};

const listRooms = () => {
  return db.prepare(`SELECT * FROM rooms`).all();
};

const deleteRoom = (id) => {
  db.prepare(`DELETE FROM rooms WHERE id = ?`).run(id);
};

// Room membership
const addMember = (room_id, agent_id, role = 'member') => {
  db.prepare(`INSERT OR IGNORE INTO room_members (room_id, agent_id, role) VALUES (?, ?, ?)`)
    .run(room_id, agent_id, role);
};

const removeMember = (room_id, agent_id) => {
  db.prepare(`DELETE FROM room_members WHERE room_id = ? AND agent_id = ?`)
    .run(room_id, agent_id);
};

const getRoomMembers = (room_id) => {
  return db.prepare(`
    SELECT a.id, a.name, a.status, rm.role 
    FROM room_members rm 
    JOIN agents a ON a.id = rm.agent_id 
    WHERE rm.room_id = ?
  `).all(room_id);
};

const getAgentRooms = (agent_id) => {
  return db.prepare(`
    SELECT r.* FROM rooms r
    JOIN room_members rm ON rm.room_id = r.id
    WHERE rm.agent_id = ?
  `).all(agent_id);
};

// Message operations
const createMessage = (room_id, sender_id, text, parse_mode = 'markdown', reply_to = null, mentions = []) => {
  const result = db.prepare(`
    INSERT INTO messages (room_id, sender_id, text, parse_mode, reply_to_message_id, mentions)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(room_id, sender_id, text, parse_mode, reply_to, JSON.stringify(mentions));
  return { id: result.lastInsertRowid, room_id, sender_id, text, parse_mode, reply_to_message_id: reply_to, mentions };
};

const getRoomMessages = (room_id, limit = 50, before_id = null) => {
  if (before_id) {
    return db.prepare(`
      SELECT m.*, a.name as sender_name FROM messages m
      JOIN agents a ON a.id = m.sender_id
      WHERE m.room_id = ? AND m.id < ?
      ORDER BY m.id DESC LIMIT ?
    `).all(room_id, before_id, limit).reverse();
  }
  return db.prepare(`
    SELECT m.*, a.name as sender_name FROM messages m
    JOIN agents a ON a.id = m.sender_id
    WHERE m.room_id = ?
    ORDER BY m.id DESC LIMIT ?
  `).all(room_id, limit).reverse();
};

// Update queue (for getUpdates polling)
const pushUpdate = (agent_id, type, payload) => {
  db.prepare(`INSERT INTO updates (agent_id, type, payload) VALUES (?, ?, ?)`)
    .run(agent_id, type, JSON.stringify(payload));
};

const getUpdates = (agent_id, offset = 0, limit = 100) => {
  const rows = db.prepare(`
    SELECT * FROM updates 
    WHERE agent_id = ? AND consumed = 0 AND id > ?
    ORDER BY id ASC LIMIT ?
  `).all(agent_id, offset, limit);
  
  // Mark as consumed
  if (rows.length > 0) {
    const maxId = rows[rows.length - 1].id;
    db.prepare(`UPDATE updates SET consumed = 1 WHERE agent_id = ? AND id <= ?`)
      .run(agent_id, maxId);
  }
  
  return rows.map(r => ({ ...r, payload: JSON.parse(r.payload) }));
};

// Cleanup old consumed updates
const cleanupUpdates = () => {
  db.prepare(`DELETE FROM updates WHERE consumed = 1 AND created_at < datetime('now', '-1 hour')`).run();
};

module.exports = {
  db,
  createAgent, getAgentByKey, getAgentById, listAgents, updateAgentStatus, updateAgentContainer, deleteAgent,
  createRoom, getRoom, listRooms, deleteRoom,
  addMember, removeMember, getRoomMembers, getAgentRooms,
  createMessage, getRoomMessages,
  pushUpdate, getUpdates, cleanupUpdates
};
