"""
Database layer - SQLite with same schema as the Node.js version.
Synchronous operations (SQLite is fast enough for single-user).
"""
import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def _migrate(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                avatar TEXT DEFAULT '',
                status TEXT DEFAULT 'offline',
                container_id TEXT DEFAULT NULL,
                model_config_id TEXT DEFAULT NULL,
                execution_mode TEXT DEFAULT 'auto',
                self_improve INTEGER DEFAULT 1,
                self_improve_threshold INTEGER DEFAULT 2,
                tools_config TEXT DEFAULT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS rooms (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                type TEXT DEFAULT 'group',
                settings_json TEXT DEFAULT '{}',
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
                thread_id TEXT DEFAULT NULL,
                metadata TEXT DEFAULT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
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

            CREATE TABLE IF NOT EXISTS model_configs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                base_url TEXT NOT NULL,
                api_key TEXT NOT NULL,
                model TEXT NOT NULL,
                max_tokens INTEGER DEFAULT 2048,
                temperature REAL DEFAULT 0.7,
                is_default INTEGER DEFAULT 0,
                params_json TEXT DEFAULT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS threads (
                id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                workflow_id TEXT DEFAULT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_threads_room ON threads(room_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                steps_json TEXT NOT NULL,
                trigger_type TEXT DEFAULT 'manual',
                trigger_config TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS workflow_runs (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                status TEXT DEFAULT 'running',
                current_step INTEGER DEFAULT 0,
                context_json TEXT DEFAULT '{}',
                started_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT DEFAULT NULL,
                FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
                FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS agent_skills (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                content TEXT DEFAULT '',
                file_type TEXT DEFAULT 'text',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            );
        """)
        self.conn.commit()

    def _row_to_dict(self, row):
        if row is None:
            return None
        return dict(row)

    def _rows_to_list(self, rows):
        return [dict(r) for r in rows]

    # === Agents ===
    def create_agent(self, name: str, description: str = "") -> dict:
        id = str(uuid.uuid4())
        api_key = uuid.uuid4().hex + uuid.uuid4().hex
        self.conn.execute(
            "INSERT INTO agents (id, name, api_key, description) VALUES (?, ?, ?, ?)",
            (id, name, api_key, description)
        )
        self.conn.commit()
        return {"id": id, "name": name, "api_key": api_key, "description": description}

    def get_agent_by_key(self, api_key: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM agents WHERE api_key = ?", (api_key,)).fetchone()
        return self._row_to_dict(row)

    def get_agent_by_id(self, id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM agents WHERE id = ?", (id,)).fetchone()
        return self._row_to_dict(row)

    def list_agents(self) -> list:
        rows = self.conn.execute(
            "SELECT id, name, description, avatar, status, container_id, model_config_id, "
            "execution_mode, self_improve, self_improve_threshold, tools_config, created_at FROM agents"
        ).fetchall()
        return self._rows_to_list(rows)

    def update_agent(self, id: str, fields: dict):
        sets = []
        vals = []
        allowed = ["name", "description", "status", "model_config_id", "execution_mode",
                   "self_improve", "self_improve_threshold", "tools_config", "container_id"]
        for key in allowed:
            if key in fields and fields[key] is not None:
                sets.append(f"{key} = ?")
                vals.append(fields[key])
        if not sets:
            return
        sets.append("updated_at = datetime('now')")
        vals.append(id)
        self.conn.execute(f"UPDATE agents SET {', '.join(sets)} WHERE id = ?", vals)
        self.conn.commit()

    def update_agent_status(self, id: str, status: str):
        self.conn.execute("UPDATE agents SET status = ?, updated_at = datetime('now') WHERE id = ?", (status, id))
        self.conn.commit()

    def delete_agent(self, id: str):
        self.conn.execute("DELETE FROM agents WHERE id = ?", (id,))
        self.conn.commit()

    # === Rooms ===
    def create_room(self, name: str, description: str = "", type: str = "group") -> dict:
        id = str(uuid.uuid4())
        self.conn.execute("INSERT INTO rooms (id, name, description, type) VALUES (?, ?, ?, ?)",
                         (id, name, description, type))
        self.conn.commit()
        return {"id": id, "name": name, "description": description, "type": type}

    def get_room(self, id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM rooms WHERE id = ?", (id,)).fetchone()
        return self._row_to_dict(row)

    def list_rooms(self) -> list:
        return self._rows_to_list(self.conn.execute("SELECT * FROM rooms").fetchall())

    def delete_room(self, id: str):
        self.conn.execute("DELETE FROM rooms WHERE id = ?", (id,))
        self.conn.commit()

    def get_room_settings(self, room_id: str) -> dict:
        row = self.conn.execute("SELECT settings_json FROM rooms WHERE id = ?", (room_id,)).fetchone()
        try:
            return json.loads(row["settings_json"]) if row else {}
        except:
            return {}

    def update_room_settings(self, room_id: str, settings: dict) -> dict:
        current = self.get_room_settings(room_id)
        merged = {**current, **settings}
        self.conn.execute("UPDATE rooms SET settings_json = ? WHERE id = ?", (json.dumps(merged), room_id))
        self.conn.commit()
        return merged

    # === Room Members ===
    def add_member(self, room_id: str, agent_id: str, role: str = "member"):
        self.conn.execute("INSERT OR IGNORE INTO room_members (room_id, agent_id, role) VALUES (?, ?, ?)",
                         (room_id, agent_id, role))
        self.conn.commit()

    def remove_member(self, room_id: str, agent_id: str):
        self.conn.execute("DELETE FROM room_members WHERE room_id = ? AND agent_id = ?", (room_id, agent_id))
        self.conn.commit()

    def get_room_members(self, room_id: str) -> list:
        rows = self.conn.execute("""
            SELECT a.id, a.name, a.status, rm.role
            FROM room_members rm JOIN agents a ON a.id = rm.agent_id
            WHERE rm.room_id = ?
        """, (room_id,)).fetchall()
        return self._rows_to_list(rows)

    def get_agent_rooms(self, agent_id: str) -> list:
        rows = self.conn.execute("""
            SELECT r.* FROM rooms r
            JOIN room_members rm ON rm.room_id = r.id
            WHERE rm.agent_id = ?
        """, (agent_id,)).fetchall()
        return self._rows_to_list(rows)

    # === Messages ===
    def create_message(self, room_id: str, sender_id: str, text: str,
                       parse_mode: str = "markdown", reply_to=None,
                       mentions: list = None, metadata: dict = None, thread_id: str = None) -> dict:
        mentions_json = json.dumps(mentions or [])
        metadata_json = json.dumps(metadata) if metadata else None
        cur = self.conn.execute("""
            INSERT INTO messages (room_id, sender_id, text, parse_mode, reply_to_message_id, mentions, metadata, thread_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (room_id, sender_id, text, parse_mode, reply_to, mentions_json, metadata_json, thread_id))
        self.conn.commit()
        msg_id = cur.lastrowid
        if thread_id:
            self.conn.execute("UPDATE threads SET updated_at = datetime('now') WHERE id = ?", (thread_id,))
            self.conn.commit()
        return {"id": msg_id, "room_id": room_id, "sender_id": sender_id, "text": text,
                "parse_mode": parse_mode, "reply_to_message_id": reply_to, "mentions": mentions or [],
                "metadata": metadata, "thread_id": thread_id, "created_at": datetime.now().isoformat()}

    def get_room_messages(self, room_id: str, limit: int = 50, before_id: int = None) -> list:
        if before_id:
            rows = self.conn.execute("""
                SELECT m.*, a.name as sender_name FROM messages m
                JOIN agents a ON a.id = m.sender_id
                WHERE m.room_id = ? AND m.id < ? ORDER BY m.id DESC LIMIT ?
            """, (room_id, before_id, limit)).fetchall()
        else:
            rows = self.conn.execute("""
                SELECT m.*, a.name as sender_name FROM messages m
                JOIN agents a ON a.id = m.sender_id
                WHERE m.room_id = ? ORDER BY m.id DESC LIMIT ?
            """, (room_id, limit)).fetchall()
        return list(reversed(self._rows_to_list(rows)))

    def clear_room_messages(self, room_id: str):
        self.conn.execute("DELETE FROM messages WHERE room_id = ?", (room_id,))
        self.conn.commit()

    def update_message(self, id: int, text: str):
        self.conn.execute("UPDATE messages SET text = ? WHERE id = ?", (text, id))
        self.conn.commit()

    def delete_message(self, id: int):
        self.conn.execute("DELETE FROM messages WHERE id = ?", (id,))
        self.conn.commit()

    # === Updates (polling) ===
    def push_update(self, agent_id: str, type: str, payload: dict):
        self.conn.execute("INSERT INTO updates (agent_id, type, payload) VALUES (?, ?, ?)",
                         (agent_id, type, json.dumps(payload)))
        self.conn.commit()

    def get_updates(self, agent_id: str, offset: int = 0, limit: int = 100) -> list:
        rows = self.conn.execute("""
            SELECT * FROM updates WHERE agent_id = ? AND consumed = 0 AND id > ?
            ORDER BY id ASC LIMIT ?
        """, (agent_id, offset, limit)).fetchall()
        result = self._rows_to_list(rows)
        if result:
            max_id = result[-1]["id"]
            self.conn.execute("UPDATE updates SET consumed = 1 WHERE agent_id = ? AND id <= ?",
                            (agent_id, max_id))
            self.conn.commit()
        for r in result:
            r["payload"] = json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"]
        return result

    def cleanup_updates(self):
        self.conn.execute("DELETE FROM updates WHERE consumed = 1 AND created_at < datetime('now', '-1 hour')")
        self.conn.commit()

    # === Model Configs ===
    def create_model_config(self, config: dict) -> dict:
        id = str(uuid.uuid4())
        self.conn.execute("""
            INSERT INTO model_configs (id, name, provider, base_url, api_key, model, max_tokens, temperature, is_default, params_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (id, config["name"], config["provider"], config["base_url"], config["api_key"],
              config["model"], config.get("max_tokens", 2048), config.get("temperature", 0.7),
              1 if config.get("is_default") else 0, config.get("params_json")))
        if config.get("is_default"):
            self.conn.execute("UPDATE model_configs SET is_default = 0 WHERE id != ?", (id,))
        self.conn.commit()
        return {"id": id, **config}

    def list_model_configs(self) -> list:
        return self._rows_to_list(self.conn.execute(
            "SELECT * FROM model_configs ORDER BY is_default DESC, created_at ASC"
        ).fetchall())

    def get_model_config(self, id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM model_configs WHERE id = ?", (id,)).fetchone()
        return self._row_to_dict(row)

    def get_default_model_config(self) -> dict | None:
        row = self.conn.execute("SELECT * FROM model_configs WHERE is_default = 1").fetchone()
        return self._row_to_dict(row)

    def update_model_config(self, id: str, fields: dict):
        sets = []
        vals = []
        for key in ["name", "provider", "base_url", "api_key", "model", "params_json"]:
            if key in fields:
                sets.append(f"{key} = ?")
                vals.append(fields[key])
        if "max_tokens" in fields:
            sets.append("max_tokens = ?"); vals.append(fields["max_tokens"])
        if "temperature" in fields:
            sets.append("temperature = ?"); vals.append(fields["temperature"])
        if fields.get("is_default"):
            sets.append("is_default = 1")
            self.conn.execute("UPDATE model_configs SET is_default = 0 WHERE id != ?", (id,))
        if not sets:
            return
        vals.append(id)
        self.conn.execute(f"UPDATE model_configs SET {', '.join(sets)} WHERE id = ?", vals)
        self.conn.commit()

    def delete_model_config(self, id: str):
        self.conn.execute("DELETE FROM model_configs WHERE id = ?", (id,))
        self.conn.execute("UPDATE agents SET model_config_id = NULL WHERE model_config_id = ?", (id,))
        self.conn.commit()

    # === Threads ===
    def create_thread(self, room_id: str, title: str, workflow_id: str = None) -> dict:
        id = str(uuid.uuid4())
        self.conn.execute("INSERT INTO threads (id, room_id, title, workflow_id) VALUES (?, ?, ?, ?)",
                         (id, room_id, title, workflow_id))
        self.conn.commit()
        return self._row_to_dict(self.conn.execute("SELECT * FROM threads WHERE id = ?", (id,)).fetchone())

    def get_threads(self, room_id: str) -> list:
        return self._rows_to_list(self.conn.execute(
            "SELECT * FROM threads WHERE room_id = ? ORDER BY updated_at DESC", (room_id,)
        ).fetchall())

    def get_thread(self, thread_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM threads WHERE id = ?", (thread_id,)).fetchone()
        return self._row_to_dict(row)

    def update_thread(self, thread_id: str, fields: dict):
        sets = []
        vals = []
        if "title" in fields:
            sets.append("title = ?"); vals.append(fields["title"])
        if "status" in fields:
            sets.append("status = ?"); vals.append(fields["status"])
        if not sets:
            return
        sets.append("updated_at = datetime('now')")
        vals.append(thread_id)
        self.conn.execute(f"UPDATE threads SET {', '.join(sets)} WHERE id = ?", vals)
        self.conn.commit()

    def delete_thread(self, thread_id: str):
        self.conn.execute("DELETE FROM messages WHERE thread_id = ?", (thread_id,))
        self.conn.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
        self.conn.commit()

    def get_thread_messages(self, thread_id: str, limit: int = 30) -> list:
        rows = self.conn.execute("""
            SELECT m.*, a.name as sender_name FROM messages m
            JOIN agents a ON a.id = m.sender_id
            WHERE m.thread_id = ? ORDER BY m.id DESC LIMIT ?
        """, (thread_id, limit)).fetchall()
        return list(reversed(self._rows_to_list(rows)))

    # === Workflows ===
    def create_workflow(self, room_id: str, name: str, description: str,
                       steps_json: str, trigger_type: str = "manual", trigger_config: str = "{}") -> dict:
        id = str(uuid.uuid4())
        self.conn.execute("""
            INSERT INTO workflows (id, room_id, name, description, steps_json, trigger_type, trigger_config)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (id, room_id, name, description or "", steps_json, trigger_type, trigger_config))
        self.conn.commit()
        return self._row_to_dict(self.conn.execute("SELECT * FROM workflows WHERE id = ?", (id,)).fetchone())

    def get_workflows(self, room_id: str) -> list:
        return self._rows_to_list(self.conn.execute(
            "SELECT * FROM workflows WHERE room_id = ? ORDER BY created_at DESC", (room_id,)
        ).fetchall())

    def get_workflow(self, workflow_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        return self._row_to_dict(row)

    def update_workflow(self, workflow_id: str, fields: dict):
        sets = []
        vals = []
        for key in ["name", "description", "steps_json", "trigger_type", "trigger_config"]:
            if key in fields:
                val = fields[key]
                if key in ("steps_json", "trigger_config") and not isinstance(val, str):
                    val = json.dumps(val)
                sets.append(f"{key} = ?")
                vals.append(val)
        if not sets:
            return
        vals.append(workflow_id)
        self.conn.execute(f"UPDATE workflows SET {', '.join(sets)} WHERE id = ?", vals)
        self.conn.commit()

    def delete_workflow(self, workflow_id: str):
        self.conn.execute("DELETE FROM workflow_runs WHERE workflow_id = ?", (workflow_id,))
        self.conn.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
        self.conn.commit()

    def create_workflow_run(self, workflow_id: str, thread_id: str) -> dict:
        id = str(uuid.uuid4())
        self.conn.execute("INSERT INTO workflow_runs (id, workflow_id, thread_id) VALUES (?, ?, ?)",
                         (id, workflow_id, thread_id))
        self.conn.commit()
        return self._row_to_dict(self.conn.execute("SELECT * FROM workflow_runs WHERE id = ?", (id,)).fetchone())

    def get_workflow_run(self, run_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
        return self._row_to_dict(row)

    def update_workflow_run(self, run_id: str, fields: dict):
        sets = []
        vals = []
        for key in ["status", "current_step", "context_json", "completed_at"]:
            if key in fields:
                val = fields[key]
                if key == "context_json" and not isinstance(val, str):
                    val = json.dumps(val)
                sets.append(f"{key} = ?")
                vals.append(val)
        if not sets:
            return
        vals.append(run_id)
        self.conn.execute(f"UPDATE workflow_runs SET {', '.join(sets)} WHERE id = ?", vals)
        self.conn.commit()

    def get_workflow_runs(self, workflow_id: str) -> list:
        return self._rows_to_list(self.conn.execute("""
            SELECT id, workflow_id, thread_id, status, current_step, started_at, completed_at
            FROM workflow_runs WHERE workflow_id = ? ORDER BY started_at DESC
        """, (workflow_id,)).fetchall())

    def get_workflow_run_count(self, workflow_id: str) -> int:
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM workflow_runs WHERE workflow_id = ?",
                               (workflow_id,)).fetchone()
        return row["cnt"] if row else 0

    # === Agent Skills ===
    def get_agent_skills(self, agent_id: str) -> list:
        return self._rows_to_list(self.conn.execute(
            "SELECT * FROM agent_skills WHERE agent_id = ? ORDER BY created_at ASC", (agent_id,)
        ).fetchall())

    def get_all_skills(self) -> list:
        return self._rows_to_list(self.conn.execute("""
            SELECT s.*, a.name as agent_name FROM agent_skills s
            LEFT JOIN agents a ON s.agent_id = a.id ORDER BY s.created_at DESC
        """).fetchall())

    def get_skill_by_id(self, skill_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM agent_skills WHERE id = ?", (skill_id,)).fetchone()
        return self._row_to_dict(row)

    def create_skill(self, agent_id: str, name: str, description: str = "",
                     content: str = "", file_type: str = "text") -> dict:
        id = str(uuid.uuid4())
        self.conn.execute("""
            INSERT INTO agent_skills (id, agent_id, name, description, content, file_type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (id, agent_id, name, description, content, file_type))
        self.conn.commit()
        return self._row_to_dict(self.conn.execute("SELECT * FROM agent_skills WHERE id = ?", (id,)).fetchone())

    def update_skill(self, skill_id: str, fields: dict) -> dict | None:
        sets = []
        vals = []
        for key in ["name", "description", "content", "file_type"]:
            if key in fields and fields[key] is not None:
                sets.append(f"{key} = ?")
                vals.append(fields[key])
        sets.append("updated_at = datetime('now')")
        vals.append(skill_id)
        self.conn.execute(f"UPDATE agent_skills SET {', '.join(sets)} WHERE id = ?", vals)
        self.conn.commit()
        return self.get_skill_by_id(skill_id)

    def delete_skill(self, skill_id: str):
        self.conn.execute("DELETE FROM agent_skills WHERE id = ?", (skill_id,))
        self.conn.commit()

    def copy_skill_to_agent(self, skill_id: str, target_agent_id: str) -> dict | None:
        skill = self.get_skill_by_id(skill_id)
        if not skill:
            return None
        return self.create_skill(target_agent_id, skill["name"], skill["description"],
                                skill["content"], skill["file_type"])

    # === DM Rooms ===
    def get_dm_room(self, user_id: str, agent_id: str) -> dict | None:
        row = self.conn.execute("""
            SELECT r.* FROM rooms r
            WHERE r.type = 'dm'
            AND EXISTS (SELECT 1 FROM room_members rm1 WHERE rm1.room_id = r.id AND rm1.agent_id = ?)
            AND EXISTS (SELECT 1 FROM room_members rm2 WHERE rm2.room_id = r.id AND rm2.agent_id = ?)
        """, (user_id, agent_id)).fetchone()
        return self._row_to_dict(row)

    def list_dm_rooms(self) -> list:
        return self._rows_to_list(self.conn.execute("SELECT * FROM rooms WHERE type = 'dm'").fetchall())

    # === Utility ===
    def ensure_system_agents(self):
        """Ensure user and system agents exist."""
        self.conn.execute("""
            INSERT OR IGNORE INTO agents (id, name, api_key, description, status)
            VALUES ('user', '我', '__user__', '用户', 'online')
        """)
        self.conn.execute("""
            INSERT OR IGNORE INTO agents (id, name, api_key, description, status)
            VALUES ('system', '系统', '__system__', '系统消息', 'online')
        """)
        self.conn.commit()

    def close(self):
        self.conn.close()
