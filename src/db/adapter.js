/**
 * Database adapter interface.
 * All adapters must implement these methods.
 * Local dev: SQLite (default)
 * Production: MySQL / PostgreSQL (via DB_DRIVER env)
 */

class DatabaseAdapter {
  // Agent operations
  createAgent(name, description) { throw new Error('Not implemented'); }
  getAgentByKey(api_key) { throw new Error('Not implemented'); }
  getAgentById(id) { throw new Error('Not implemented'); }
  listAgents() { throw new Error('Not implemented'); }
  updateAgentStatus(id, status) { throw new Error('Not implemented'); }
  updateAgentContainer(id, container_id) { throw new Error('Not implemented'); }
  deleteAgent(id) { throw new Error('Not implemented'); }

  // Room operations
  createRoom(name, description) { throw new Error('Not implemented'); }
  getRoom(id) { throw new Error('Not implemented'); }
  listRooms() { throw new Error('Not implemented'); }
  deleteRoom(id) { throw new Error('Not implemented'); }

  // Room membership
  addMember(room_id, agent_id, role) { throw new Error('Not implemented'); }
  removeMember(room_id, agent_id) { throw new Error('Not implemented'); }
  getRoomMembers(room_id) { throw new Error('Not implemented'); }
  getAgentRooms(agent_id) { throw new Error('Not implemented'); }

  // Messages
  createMessage(room_id, sender_id, text, parse_mode, reply_to, mentions) { throw new Error('Not implemented'); }
  getRoomMessages(room_id, limit, before_id) { throw new Error('Not implemented'); }

  // Update queue
  pushUpdate(agent_id, type, payload) { throw new Error('Not implemented'); }
  getUpdates(agent_id, offset, limit) { throw new Error('Not implemented'); }
  cleanupUpdates() { throw new Error('Not implemented'); }

  // Lifecycle
  close() {}
}

module.exports = DatabaseAdapter;
