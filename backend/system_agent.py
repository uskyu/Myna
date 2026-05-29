"""
System Agent for Myna.
A built-in privileged agent that manages credentials, executes git operations,
and provides shared resources to other agents on request.

The system agent is NOT a regular LLM-powered agent — it's a deterministic
service that responds to structured tool calls from other agents.
"""

import os
import json
import subprocess
import tempfile
import shutil
import time
import uuid
from typing import Optional
from pathlib import Path


# Workspace root for git operations
WORKSPACE_ROOT = os.environ.get("MYNA_WORKSPACE", "/tmp/myna-workspace")


class SystemAgent:
    """
    Built-in system agent that handles:
    - Credential distribution (encrypted, scoped)
    - Git operations (clone, pull, push)
    - Workspace management
    """

    AGENT_ID = "__system__"
    AGENT_NAME = "System"
    AGENT_AVATAR = "🔐"

    def __init__(self, credential_store):
        self.credential_store = credential_store
        self._workspace = Path(WORKSPACE_ROOT)
        self._workspace.mkdir(parents=True, exist_ok=True)
        # Audit log of credential access
        self._access_log = []

    def handle_request(self, action: str, params: dict, requester_agent_id: str) -> dict:
        """
        Process a request from another agent.
        Returns a result dict with {ok, data/error}.
        """
        handlers = {
            "git_clone": self._git_clone,
            "git_pull": self._git_pull,
            "git_push": self._git_push,
            "git_status": self._git_status,
            "git_commit": self._git_commit,
            "list_repos": self._list_repos,
            "list_credentials": self._list_credentials,
            "exec_command": self._exec_command,
        }

        handler = handlers.get(action)
        if not handler:
            return {"ok": False, "error": f"Unknown action: {action}. Available: {list(handlers.keys())}"}

        # Log the access
        self._access_log.append({
            "time": time.time(),
            "requester": requester_agent_id,
            "action": action,
            "params": {k: v for k, v in params.items() if k != "value"},  # Don't log secrets
        })

        try:
            result = handler(params, requester_agent_id)
            return {"ok": True, "data": result}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _get_github_token(self) -> Optional[str]:
        """Get the first available GitHub PAT."""
        creds = self.credential_store.get_by_type("github_pat")
        if not creds:
            return None
        # Get the decrypted value of the first one
        return self.credential_store.get_decrypted(creds[0]["id"])

    def _get_auth_url(self, url: str) -> str:
        """Inject GitHub token into clone URL if available."""
        token = self._get_github_token()
        if token and "github.com" in url:
            # https://github.com/user/repo.git → https://TOKEN@github.com/user/repo.git
            if url.startswith("https://"):
                return url.replace("https://", f"https://{token}@")
        return url

    def _repo_path(self, repo_name: str) -> Path:
        """Get the workspace path for a repo."""
        # Sanitize repo name
        safe_name = repo_name.replace("/", "_").replace("\\", "_")
        return self._workspace / safe_name

    def _git_clone(self, params: dict, requester: str) -> dict:
        """Clone a repository into the workspace."""
        url = params.get("url")
        if not url:
            raise ValueError("Missing 'url' parameter")

        # Determine repo name from URL
        repo_name = params.get("name") or url.rstrip("/").split("/")[-1].replace(".git", "")
        target = self._repo_path(repo_name)

        if target.exists():
            # Already cloned, do a pull instead
            return self._git_pull({"repo": repo_name}, requester)

        auth_url = self._get_auth_url(url)
        branch = params.get("branch")

        cmd = ["git", "clone", "--depth", "1"]
        if branch:
            cmd.extend(["-b", branch])
        cmd.extend([auth_url, str(target)])

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        )

        if result.returncode != 0:
            # Sanitize error (remove token from output)
            error = result.stderr.replace(self._get_github_token() or "", "***")
            raise RuntimeError(f"git clone failed: {error}")

        return {
            "repo": repo_name,
            "path": str(target),
            "message": f"Successfully cloned {url} to {target}",
        }

    def _git_pull(self, params: dict, requester: str) -> dict:
        """Pull latest changes for a repo."""
        repo_name = params.get("repo")
        if not repo_name:
            raise ValueError("Missing 'repo' parameter")

        target = self._repo_path(repo_name)
        if not target.exists():
            raise ValueError(f"Repo '{repo_name}' not found in workspace. Clone it first.")

        # Set credential helper for this operation
        token = self._get_github_token()
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        if token:
            env["GIT_ASKPASS"] = "/bin/echo"

        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            capture_output=True, text=True, timeout=60,
            cwd=str(target), env=env
        )

        if result.returncode != 0:
            error = result.stderr.replace(token or "", "***")
            raise RuntimeError(f"git pull failed: {error}")

        return {
            "repo": repo_name,
            "path": str(target),
            "message": result.stdout.strip() or "Already up to date.",
        }

    def _git_push(self, params: dict, requester: str) -> dict:
        """Push changes for a repo."""
        repo_name = params.get("repo")
        if not repo_name:
            raise ValueError("Missing 'repo' parameter")

        target = self._repo_path(repo_name)
        if not target.exists():
            raise ValueError(f"Repo '{repo_name}' not found in workspace.")

        branch = params.get("branch", "")
        token = self._get_github_token()
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

        # Rewrite remote URL with token for push
        if token:
            remote_result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, cwd=str(target)
            )
            if remote_result.returncode == 0:
                remote_url = remote_result.stdout.strip()
                auth_url = self._get_auth_url(remote_url)
                subprocess.run(
                    ["git", "remote", "set-url", "origin", auth_url],
                    capture_output=True, cwd=str(target)
                )

        cmd = ["git", "push"]
        if branch:
            cmd.extend(["origin", branch])

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            cwd=str(target), env=env
        )

        # Restore original URL (without token)
        if token:
            subprocess.run(
                ["git", "remote", "set-url", "origin", remote_url],
                capture_output=True, cwd=str(target)
            )

        if result.returncode != 0:
            error = result.stderr.replace(token or "", "***")
            raise RuntimeError(f"git push failed: {error}")

        return {
            "repo": repo_name,
            "message": result.stdout.strip() or result.stderr.strip().replace(token or "", "***"),
        }

    def _git_status(self, params: dict, requester: str) -> dict:
        """Get git status for a repo."""
        repo_name = params.get("repo")
        if not repo_name:
            raise ValueError("Missing 'repo' parameter")

        target = self._repo_path(repo_name)
        if not target.exists():
            raise ValueError(f"Repo '{repo_name}' not found in workspace.")

        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, timeout=10,
            cwd=str(target)
        )

        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=10,
            cwd=str(target)
        )

        return {
            "repo": repo_name,
            "branch": branch_result.stdout.strip(),
            "status": result.stdout.strip() or "(clean)",
            "path": str(target),
        }

    def _git_commit(self, params: dict, requester: str) -> dict:
        """Stage and commit changes."""
        repo_name = params.get("repo")
        message = params.get("message", "Update from Myna agent")
        files = params.get("files")  # Optional: specific files to stage

        if not repo_name:
            raise ValueError("Missing 'repo' parameter")

        target = self._repo_path(repo_name)
        if not target.exists():
            raise ValueError(f"Repo '{repo_name}' not found in workspace.")

        # Stage files
        if files:
            for f in files:
                subprocess.run(["git", "add", f], cwd=str(target), capture_output=True)
        else:
            subprocess.run(["git", "add", "-A"], cwd=str(target), capture_output=True)

        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", message, "--author", f"{requester} <agent@myna.local>"],
            capture_output=True, text=True, timeout=30,
            cwd=str(target)
        )

        if result.returncode != 0:
            if "nothing to commit" in result.stdout:
                return {"repo": repo_name, "message": "Nothing to commit, working tree clean."}
            raise RuntimeError(f"git commit failed: {result.stderr}")

        return {
            "repo": repo_name,
            "message": result.stdout.strip(),
        }

    def _list_repos(self, params: dict, requester: str) -> dict:
        """List all repos in the workspace."""
        repos = []
        if self._workspace.exists():
            for item in self._workspace.iterdir():
                if item.is_dir() and (item / ".git").exists():
                    # Get branch info
                    branch_result = subprocess.run(
                        ["git", "branch", "--show-current"],
                        capture_output=True, text=True, timeout=5,
                        cwd=str(item)
                    )
                    repos.append({
                        "name": item.name,
                        "path": str(item),
                        "branch": branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown",
                    })
        return {"repos": repos, "workspace": str(self._workspace)}

    def _list_credentials(self, params: dict, requester: str) -> dict:
        """List available credential types (not values!)."""
        creds = self.credential_store.list_all()
        # Only expose type and name, never values
        return {
            "credentials": [
                {"id": c["id"], "name": c["name"], "type": c["type"]}
                for c in creds
            ]
        }

    def _exec_command(self, params: dict, requester: str) -> dict:
        """Execute a shell command in a repo workspace (sandboxed)."""
        repo_name = params.get("repo")
        command = params.get("command")

        if not command:
            raise ValueError("Missing 'command' parameter")

        # Determine working directory
        if repo_name:
            cwd = str(self._repo_path(repo_name))
            if not os.path.exists(cwd):
                raise ValueError(f"Repo '{repo_name}' not found.")
        else:
            cwd = str(self._workspace)

        # Block dangerous commands
        dangerous = ["rm -rf /", "mkfs", "dd if=", "> /dev/sd"]
        for d in dangerous:
            if d in command:
                raise ValueError(f"Blocked dangerous command pattern: {d}")

        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=60, cwd=cwd,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        )

        output = result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout
        return {
            "exit_code": result.returncode,
            "stdout": output,
            "stderr": result.stderr[-500:] if result.stderr else "",
        }

    def get_access_log(self, limit: int = 50) -> list:
        """Get recent access log entries."""
        return self._access_log[-limit:]

    def get_status(self) -> dict:
        """Get system agent status summary."""
        creds = self.credential_store.list_all()
        repos = []
        if self._workspace.exists():
            repos = [d.name for d in self._workspace.iterdir() if d.is_dir() and (d / ".git").exists()]

        return {
            "agent_id": self.AGENT_ID,
            "name": self.AGENT_NAME,
            "status": "online",
            "credentials_count": len(creds),
            "credential_types": list(set(c["type"] for c in creds)),
            "repos_count": len(repos),
            "repos": repos,
            "workspace": str(self._workspace),
            "recent_requests": len(self._access_log),
        }
