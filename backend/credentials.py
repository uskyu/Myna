"""
Credential management module for Myna System Agent.
Encrypts secrets at rest using Fernet (AES-128-CBC + HMAC-SHA256).
The encryption key is derived from the instance's auth password hash.
"""

import os
import json
import hashlib
import base64
import time
from typing import Optional
from cryptography.fernet import Fernet


def _derive_key(secret: str) -> bytes:
    """Derive a Fernet key from a secret string."""
    # Use SHA-256 to get 32 bytes, then base64-encode for Fernet
    raw = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(raw)


class CredentialStore:
    """Encrypted credential storage backed by the database."""

    # Supported credential types
    TYPES = ("github_pat", "ssh_key", "api_key", "custom")

    def __init__(self, db, encryption_secret: str):
        self.db = db
        self._fernet = Fernet(_derive_key(encryption_secret))
        self._ensure_table()

    def _ensure_table(self):
        """Create credentials table if not exists."""
        # Works for both SQLite and MySQL
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS credentials (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                encrypted_value TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        self.db.commit()

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt a string value."""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt a stored value."""
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def add(self, cred_id: str, name: str, cred_type: str, value: str, metadata: dict = None) -> dict:
        """Store a new credential (encrypted)."""
        if cred_type not in self.TYPES:
            raise ValueError(f"Invalid type: {cred_type}. Must be one of {self.TYPES}")

        encrypted = self._encrypt(value)
        meta_json = json.dumps(metadata or {})
        ph = self.db._placeholder()

        self.db.execute(f"""
            INSERT INTO credentials (id, name, type, encrypted_value, metadata)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
        """, (cred_id, name, cred_type, encrypted, meta_json))
        self.db.commit()

        return {"id": cred_id, "name": name, "type": cred_type, "metadata": metadata or {}}

    def update(self, cred_id: str, name: str = None, value: str = None, metadata: dict = None) -> bool:
        """Update an existing credential."""
        ph = self.db._placeholder()
        updates = []
        params = []

        if name is not None:
            updates.append(f"name = {ph}")
            params.append(name)
        if value is not None:
            updates.append(f"encrypted_value = {ph}")
            params.append(self._encrypt(value))
        if metadata is not None:
            updates.append(f"metadata = {ph}")
            params.append(json.dumps(metadata))

        if not updates:
            return False

        updates.append(f"updated_at = datetime('now')")
        params.append(cred_id)

        self.db.execute(
            f"UPDATE credentials SET {', '.join(updates)} WHERE id = {ph}",
            tuple(params)
        )
        self.db.commit()
        return True

    def delete(self, cred_id: str) -> bool:
        """Delete a credential."""
        ph = self.db._placeholder()
        self.db.execute(f"DELETE FROM credentials WHERE id = {ph}", (cred_id,))
        self.db.commit()
        return True

    def get(self, cred_id: str, decrypt: bool = False) -> Optional[dict]:
        """Get a credential by ID. Only decrypts if explicitly requested."""
        ph = self.db._placeholder()
        row = self.db.fetchone(
            f"SELECT id, name, type, encrypted_value, metadata, created_at, updated_at FROM credentials WHERE id = {ph}",
            (cred_id,)
        )
        if not row:
            return None

        result = {
            "id": row["id"],
            "name": row["name"],
            "type": row["type"],
            "metadata": json.loads(row["metadata"] or "{}"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        if decrypt:
            result["value"] = self._decrypt(row["encrypted_value"])
        else:
            # Show masked value
            try:
                val = self._decrypt(row["encrypted_value"])
                if len(val) > 8:
                    result["value_preview"] = val[:4] + "****" + val[-4:]
                else:
                    result["value_preview"] = "****"
            except Exception:
                result["value_preview"] = "****"

        return result

    def get_by_type(self, cred_type: str) -> list:
        """Get all credentials of a given type (without decrypted values)."""
        ph = self.db._placeholder()
        rows = self.db.fetchall(
            f"SELECT id, name, type, encrypted_value, metadata, created_at, updated_at FROM credentials WHERE type = {ph}",
            (cred_type,)
        )
        results = []
        for row in rows:
            try:
                val = self._decrypt(row["encrypted_value"])
                preview = val[:4] + "****" + val[-4:] if len(val) > 8 else "****"
            except Exception:
                preview = "****"
            results.append({
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "value_preview": preview,
                "metadata": json.loads(row["metadata"] or "{}"),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            })
        return results

    def list_all(self) -> list:
        """List all credentials (without decrypted values)."""
        rows = self.db.fetchall(
            "SELECT id, name, type, encrypted_value, metadata, created_at, updated_at FROM credentials"
        )
        results = []
        for row in rows:
            try:
                val = self._decrypt(row["encrypted_value"])
                preview = val[:4] + "****" + val[-4:] if len(val) > 8 else "****"
            except Exception:
                preview = "****"
            results.append({
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "value_preview": preview,
                "metadata": json.loads(row["metadata"] or "{}"),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            })
        return results

    def get_decrypted(self, cred_id: str) -> Optional[str]:
        """Get only the decrypted value (for system agent internal use)."""
        ph = self.db._placeholder()
        row = self.db.fetchone(
            f"SELECT encrypted_value FROM credentials WHERE id = {ph}",
            (cred_id,)
        )
        if not row:
            return None
        return self._decrypt(row["encrypted_value"])
