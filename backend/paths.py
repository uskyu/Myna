"""Runtime paths for Myna across Docker, local dev, and portable builds."""
from __future__ import annotations

import json
import os
import platform
import shutil
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent.parent

# Track whether a migration is pending (set by migrate_data_dir)
_migration_pending: str | None = None


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _default_data_root() -> Path:
    configured = os.environ.get("MYNA_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    if _is_windows():
        # Prefer non-C-drive if available: %LOCALAPPDATA% is typically C:\Users\<user>\AppData\Local
        # Allow user to override via MYNA_DATA_DIR; default to %LOCALAPPDATA%\Myna
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            return Path(local_app) / "Myna"
        app_data = os.environ.get("APPDATA", "")
        if app_data:
            # Fallback to APPDATA if LOCALAPPDATA is missing
            return Path(app_data) / "Myna"
    return APP_ROOT / "data"


def _default_db_root() -> Path:
    configured = os.environ.get("MYNA_DB_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    configured_data = os.environ.get("MYNA_DATA_DIR", "").strip()
    if configured_data:
        return Path(configured_data).expanduser() / "db"
    return _default_data_root() / "db"


def _default_profiles_root() -> Path:
    configured = os.environ.get("MYNA_PROFILES_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    configured_data = os.environ.get("MYNA_DATA_DIR", "").strip()
    if configured_data:
        return Path(configured_data).expanduser() / "hermes" / "profiles"
    return _default_data_root() / "hermes" / "profiles"


def _default_hermes_path() -> Path:
    configured = os.environ.get("HERMES_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    bundled = APP_ROOT / "vendor" / "hermes-agent"
    if bundled.exists():
        return bundled
    if _is_windows():
        # On Windows, check for bundled hermes in common locations
        local_bundled = APP_ROOT / "vendor" / "hermes-agent"
        if local_bundled.exists():
            return local_bundled
    return Path("/root/hermes")


DATA_ROOT = _default_data_root()
DB_ROOT = _default_db_root()
UPLOADS_DIR = DATA_ROOT / "uploads"
WORKSPACES_ROOT = Path(os.environ.get("MYNA_WORKSPACES_ROOT", "")).expanduser() if os.environ.get("MYNA_WORKSPACES_ROOT", "").strip() else DATA_ROOT / "workspaces"
PROFILES_ROOT = _default_profiles_root()
HERMES_PATH = _default_hermes_path()

# Config file for persisting custom data directory
_PATHS_CONFIG = DATA_ROOT / ".myna-paths.json"


def get_data_dir_info() -> dict:
    """Return current data directory information for the settings UI."""
    # Check if there's a persisted custom path
    custom_dir = None
    if _PATHS_CONFIG.exists():
        try:
            with open(_PATHS_CONFIG) as f:
                cfg = json.load(f)
                custom_dir = cfg.get("data_dir")
        except (json.JSONDecodeError, OSError):
            pass

    active_dir = custom_dir if custom_dir else str(DATA_ROOT)
    return {
        "current_dir": str(DATA_ROOT),
        "custom_dir": custom_dir,
        "is_default": custom_dir is None,
        "platform": platform.system(),
        "db_size": _dir_size(DB_ROOT),
        "uploads_size": _dir_size(UPLOADS_DIR),
        "workspaces_size": _dir_size(WORKSPACES_ROOT),
        "profiles_size": _dir_size(PROFILES_ROOT),
    }


def migrate_data_dir(new_dir: str) -> dict:
    """Migrate all data to a new directory. Returns status dict.
    
    This copies db/, uploads/, workspaces/, hermes/profiles/ to the new location
    and saves the new path to .myna-paths.json. The application must be restarted
    for the change to take full effect.
    """
    global _migration_pending
    
    new_path = Path(new_dir).resolve()
    if not new_path.exists():
        try:
            new_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return {"ok": False, "error": f"无法创建目录 {new_dir}: {e}"}
    
    # Verify write access
    test_file = new_path / ".myna-write-test"
    try:
        test_file.write_text("ok")
        test_file.unlink()
    except OSError as e:
        return {"ok": False, "error": f"目录不可写 {new_dir}: {e}"}
    
    # Copy subdirectories
    subdirs = [
        (DB_ROOT, new_path / "db"),
        (UPLOADS_DIR, new_path / "uploads"),
        (WORKSPACES_ROOT, new_path / "workspaces"),
        (PROFILES_ROOT, new_path / "hermes" / "profiles"),
    ]
    
    migrated = []
    for src, dst in subdirs:
        if src.exists() and any(src.iterdir()):
            try:
                if dst.exists():
                    # Merge: copy contents, don't delete existing
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copytree(src, dst)
                migrated.append(str(src.relative_to(DATA_ROOT)) if src.is_relative_to(DATA_ROOT) else str(src))
            except OSError as e:
                return {"ok": False, "error": f"复制 {src} → {dst} 失败: {e}"}
    
    # Save the new data directory path
    config = {"data_dir": str(new_path)}
    config_path = new_path / ".myna-paths.json"
    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    except OSError as e:
        return {"ok": False, "error": f"无法写入配置: {e}"}
    
    # Also write to current data root so it's found on next startup
    try:
        with open(_PATHS_CONFIG, "w") as f:
            json.dump(config, f, indent=2)
    except OSError:
        pass  # Non-critical
    
    _migration_pending = str(new_path)
    
    return {
        "ok": True,
        "migrated": migrated,
        "new_dir": str(new_path),
        "note": "数据已复制到新目录。请重启 Myna 以使新目录生效。旧数据仍保留在原位置，确认无误后可手动删除。"
    }


def _dir_size(path: Path) -> str:
    """Return human-readable directory size."""
    if not path.exists():
        return "0 B"
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except (OSError, PermissionError):
        pass
    if total < 1024:
        return f"{total} B"
    elif total < 1024 * 1024:
        return f"{total / 1024:.1f} KB"
    elif total < 1024 * 1024 * 1024:
        return f"{total / (1024 * 1024):.1f} MB"
    else:
        return f"{total / (1024 * 1024 * 1024):.2f} GB"


def ensure_runtime_dirs() -> None:
    for path in (DATA_ROOT, DB_ROOT, UPLOADS_DIR, WORKSPACES_ROOT, PROFILES_ROOT):
        path.mkdir(parents=True, exist_ok=True)

