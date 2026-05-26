const { v4: uuidv4 } = require('uuid');
const DatabaseAdapter = require('./adapter');

/**
 * MySQL adapter using mysql2 (must be installed: npm install mysql2)
 * 
 * Env vars:
 *   DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
 */
class MySQLAdapter extends DatabaseAdapter {
  constructor(config) {
    super();
    const mysql = require('mysql2/promise');
    this.config = config;
    this.pool = null;
    this._ready = this._init(mysql);
  }

  async _init(mysql) {
    this.pool = mysql.createPool({
      host: this.config.host || 'localhost',
      port: this.config.port || 3306,
      user: this.config.user || 'root',
      password: this.config.password || '',
      database: this.config.database || 'hermes_hub',
      waitForConnections: true,
      connectionLimit: 10,
      charset: 'utf8mb4'
    });
    await this._migrate();
  }

  async _migrate() {
    const sqls = [
      `CREATE TABLE IF NOT EXISTS agents (
        id VARCHAR(36) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        api_key VARCHAR(128) UNIQUE NOT NULL,
        description TEXT DEFAULT '',
        avatar VARCHAR(512) DEFAULT '',
        status VARCHAR(20) DEFAULT 'offline',
        container_id VARCHAR(128) DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,

      `CREATE TABLE IF NOT EXISTS rooms (
        id VARCHAR(36) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT DEFAULT '',
        type VARCHAR(20) DEFAULT 'group',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,

      `CREATE TABLE IF NOT EXISTS room_members (
        room_id VARCHAR(36) NOT NULL,
        agent_id VARCHAR(36) NOT NULL,
        role VARCHAR(20) DEFAULT 'member',
        joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (room_id, agent_id),
        FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
        FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,

      `CREATE TABLE IF NOT EXISTS messages (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        room_id VARCHAR(36) NOT NULL,
        sender_id VARCHAR(36) NOT NULL,
        text LONGTEXT NOT NULL,
        parse_mode VARCHAR(20) DEFAULT 'markdown',
        reply_to_message_id BIGINT DEFAULT NULL,
        mentions JSON DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_messages_room (room_id, id),
        FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
        FOREIGN KEY (sender_id) REFERENCES agents(id) ON DELETE CASCADE
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,

      `CREATE TABLE IF NOT EXISTS updates_queue (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        agent_id VARCHAR(36) NOT NULL,
        type VARCHAR(50) NOT NULL,
        payload JSON NOT NULL,
        consumed TINYINT DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_updates_agent (agent_id, consumed, id),
        FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`
    ];

    for (const sql of sqls) {
      await this.pool.execute(sql);
    }
  }

  async ready() {
    await this._ready;
  }

  async createAgent(name, description = '') {
    const id = uuidv4();
    const api_key = uuidv4().replace(/-/g, '') + uuidv4().replace(/-/g, '');
    await this.pool.execute(
      `INSERT INTO agents (id, name, api_key, description) VALUES (?, ?, ?, ?)`,
      [id, name, api_key, description]
    );
    return { id, name, api_key, description };
  }

  async getAgentByKey(api_key) {
    const [rows] = await this.pool.execute(`SELECT * FROM agents WHERE api_key = ?`, [api_key]);
    return rows[0] || null;
  }

  async getAgentById(id) {
    const [rows] = await this.pool.execute(`SELECT * FROM agents WHERE id = ?`, [id]);
    return rows[0] || null;
  }

  async listAgents() {
    const [rows] = await this.pool.execute(`SELECT id, name, description, avatar, status, container_id, created_at FROM agents`);
    return rows;
  }

  async updateAgentStatus(id, status) {
    await this.pool.execute(`UPDATE agents SET status = ? WHERE id = ?`, [status, id]);
  }

  async updateAgentContainer(id, container_id) {
    await this.pool.execute(`UPDATE agents SET container_id = ? WHERE id = ?`, [container_id, id]);
  }

  async deleteAgent(id) {
    await this.pool.execute(`DELETE FROM agents WHERE id = ?`, [id]);
  }

  async createRoom(name, description = '') {
    const id = uuidv4();
    await this.pool.execute(`INSERT INTO rooms (id, name, description) VALUES (?, ?, ?)`, [id, name, description]);
    return { id, name, description };
  }

  async getRoom(id) {
    const [rows] = await this.pool.execute(`SELECT * FROM rooms WHERE id = ?`, [id]);
    return rows[0] || null;
  }

  async listRooms() {
    const [rows] = await this.pool.execute(`SELECT * FROM rooms`);
    return rows;
  }

  async deleteRoom(id) {
    await this.pool.execute(`DELETE FROM rooms WHERE id = ?`, [id]);
  }

  async addMember(room_id, agent_id, role = 'member') {
    await this.pool.execute(
      `INSERT IGNORE INTO room_members (room_id, agent_id, role) VALUES (?, ?, ?)`,
      [room_id, agent_id, role]
    );
  }

  async removeMember(room_id, agent_id) {
    await this.pool.execute(`DELETE FROM room_members WHERE room_id = ? AND agent_id = ?`, [room_id, agent_id]);
  }

  async getRoomMembers(room_id) {
    const [rows] = await this.pool.execute(`
      SELECT a.id, a.name, a.status, rm.role 
      FROM room_members rm 
      JOIN agents a ON a.id = rm.agent_id 
      WHERE rm.room_id = ?
    `, [room_id]);
    return rows;
  }

  async getAgentRooms(agent_id) {
    const [rows] = await this.pool.execute(`
      SELECT r.* FROM rooms r
      JOIN room_members rm ON rm.room_id = r.id
      WHERE rm.agent_id = ?
    `, [agent_id]);
    return rows;
  }

  async createMessage(room_id, sender_id, text, parse_mode = 'markdown', reply_to = null, mentions = []) {
    const [result] = await this.pool.execute(`
      INSERT INTO messages (room_id, sender_id, text, parse_mode, reply_to_message_id, mentions)
      VALUES (?, ?, ?, ?, ?, ?)
    `, [room_id, sender_id, text, parse_mode, reply_to, JSON.stringify(mentions)]);
    return { id: Number(result.insertId), room_id, sender_id, text, parse_mode, reply_to_message_id: reply_to, mentions };
  }

  async getRoomMessages(room_id, limit = 50, before_id = null) {
    let rows;
    if (before_id) {
      [rows] = await this.pool.execute(`
        SELECT m.*, a.name as sender_name FROM messages m
        JOIN agents a ON a.id = m.sender_id
        WHERE m.room_id = ? AND m.id < ?
        ORDER BY m.id DESC LIMIT ?
      `, [room_id, before_id, limit]);
    } else {
      [rows] = await this.pool.execute(`
        SELECT m.*, a.name as sender_name FROM messages m
        JOIN agents a ON a.id = m.sender_id
        WHERE m.room_id = ?
        ORDER BY m.id DESC LIMIT ?
      `, [room_id, limit]);
    }
    return rows.reverse();
  }

  async pushUpdate(agent_id, type, payload) {
    await this.pool.execute(
      `INSERT INTO updates_queue (agent_id, type, payload) VALUES (?, ?, ?)`,
      [agent_id, type, JSON.stringify(payload)]
    );
  }

  async getUpdates(agent_id, offset = 0, limit = 100) {
    const [rows] = await this.pool.execute(`
      SELECT * FROM updates_queue 
      WHERE agent_id = ? AND consumed = 0 AND id > ?
      ORDER BY id ASC LIMIT ?
    `, [agent_id, offset, limit]);

    if (rows.length > 0) {
      const maxId = rows[rows.length - 1].id;
      await this.pool.execute(`UPDATE updates_queue SET consumed = 1 WHERE agent_id = ? AND id <= ?`, [agent_id, maxId]);
    }

    return rows.map(r => ({
      ...r,
      payload: typeof r.payload === 'string' ? JSON.parse(r.payload) : r.payload
    }));
  }

  async cleanupUpdates() {
    await this.pool.execute(`DELETE FROM updates_queue WHERE consumed = 1 AND created_at < DATE_SUB(NOW(), INTERVAL 1 HOUR)`);
  }

  async close() {
    if (this.pool) await this.pool.end();
  }
}

module.exports = MySQLAdapter;
