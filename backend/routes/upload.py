"""
File upload endpoint.
"""
import base64
import binascii
import json
import os
import random
import string
import time
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Request
from fastapi.responses import JSONResponse

from paths import UPLOADS_DIR

router = APIRouter()

UPLOAD_DIR = UPLOADS_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CHUNK_DIR = UPLOAD_DIR / ".chunks"
CHUNK_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_SIZE = 200 * 1024 * 1024
MAX_CHUNK_SIZE = 512 * 1024

ARCHIVE_SUFFIXES = (
    ".tar.gz", ".tar.bz2", ".tar.xz", ".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".tbz", ".xz", ".txz"
)
ARCHIVE_MIME_TYPES = {
    "application/zip",
    "application/x-zip-compressed",
    "application/x-7z-compressed",
    "application/vnd.rar",
    "application/x-rar-compressed",
    "application/x-tar",
    "application/gzip",
    "application/x-gzip",
    "application/x-bzip2",
    "application/x-xz",
}


def _safe_upload_suffix(filename: str | None) -> str:
    """Preserve normal and compound archive suffixes without trusting the name."""
    if not filename:
        return ""
    lower_name = filename.lower()
    for suffix in ARCHIVE_SUFFIXES:
        if lower_name.endswith(suffix):
            return suffix
    return Path(filename).suffix


def _upload_type(content_type: str | None, filename: str | None) -> str:
    if content_type and content_type.startswith("image/"):
        return "image"
    lower_name = (filename or "").lower()
    if (content_type in ARCHIVE_MIME_TYPES) or any(lower_name.endswith(s) for s in ARCHIVE_SUFFIXES):
        return "archive"
    return "file"


def _new_upload_name(filename: str | None) -> tuple[str, Path]:
    ext = _safe_upload_suffix(filename)
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    stored_name = f"{int(time.time())}-{rand}{ext}"
    return stored_name, UPLOAD_DIR / stored_name


def _upload_result(stored_name: str, original_name: str | None, content_type: str | None, size: int) -> dict:
    return {
        "ok": True,
        "url": f"/uploads/{stored_name}",
        "type": _upload_type(content_type, original_name),
        "name": original_name,
        "size": size,
    }


@router.post("/admin/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    filename, filepath = _new_upload_name(file.filename)
    tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")

    size = 0
    try:
        # Stream to disk instead of reading the whole file into memory. Large
        # archives previously failed easily because they were buffered entirely
        # in the backend process before writing.
        with tmp_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    raise ValueError("文件不能超过 200 MB")
                out.write(chunk)
        tmp_path.replace(filepath)
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        return JSONResponse({"ok": False, "error": f"文件保存失败: {exc}"}, status_code=500)
    finally:
        try:
            await file.close()
        except Exception:
            pass

    return _upload_result(filename, file.filename, file.content_type, size)


@router.post("/admin/upload/chunk")
async def upload_chunk(request: Request):
    """JSON chunk fallback for networks that block multipart uploads."""
    body = await request.json()
    upload_id = str(body.get("upload_id") or "")
    if not upload_id or not upload_id.replace("-", "").isalnum() or len(upload_id) > 80:
        return JSONResponse({"ok": False, "error": "无效上传标识"}, status_code=400)
    try:
        index = int(body.get("index"))
        total = int(body.get("total"))
        total_size = int(body.get("size"))
    except (TypeError, ValueError):
        return JSONResponse({"ok": False, "error": "无效分块参数"}, status_code=400)
    if index < 0 or total < 1 or index >= total or total_size < 0 or total_size > MAX_UPLOAD_SIZE:
        return JSONResponse({"ok": False, "error": "文件过大或分块参数无效"}, status_code=400)
    try:
        data = base64.b64decode(str(body.get("data") or ""), validate=True)
    except (binascii.Error, ValueError):
        return JSONResponse({"ok": False, "error": "分块数据无效"}, status_code=400)
    if len(data) > MAX_CHUNK_SIZE:
        return JSONResponse({"ok": False, "error": "单个分块过大"}, status_code=400)

    session_dir = CHUNK_DIR / upload_id
    session_dir.mkdir(mode=0o700, exist_ok=True)
    meta_path = session_dir / "meta.json"
    meta = {
        "name": str(body.get("name") or "file")[:255],
        "content_type": str(body.get("content_type") or "application/octet-stream")[:120],
        "size": total_size,
        "total": total,
    }
    if meta_path.exists():
        try:
            if json.loads(meta_path.read_text("utf-8")) != meta:
                return JSONResponse({"ok": False, "error": "上传参数发生变化"}, status_code=409)
        except Exception:
            return JSONResponse({"ok": False, "error": "上传会话损坏"}, status_code=409)
    else:
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    part_path = session_dir / f"{index:08d}.part"
    tmp_part = part_path.with_suffix(".tmp")
    tmp_part.write_bytes(data)
    os.replace(tmp_part, part_path)
    return {"ok": True, "received": index, "complete": len(list(session_dir.glob("*.part"))) == total}


@router.post("/admin/upload/complete")
async def complete_chunked_upload(request: Request):
    body = await request.json()
    upload_id = str(body.get("upload_id") or "")
    if not upload_id or not upload_id.replace("-", "").isalnum() or len(upload_id) > 80:
        return JSONResponse({"ok": False, "error": "无效上传标识"}, status_code=400)
    session_dir = CHUNK_DIR / upload_id
    meta_path = session_dir / "meta.json"
    if not meta_path.exists():
        return JSONResponse({"ok": False, "error": "上传会话不存在"}, status_code=404)
    completed = False
    try:
        meta = json.loads(meta_path.read_text("utf-8"))
        total = int(meta["total"])
        parts = [session_dir / f"{index:08d}.part" for index in range(total)]
        if not all(part.is_file() for part in parts):
            return JSONResponse({"ok": False, "error": "文件分块不完整"}, status_code=409)
        stored_name, filepath = _new_upload_name(meta.get("name"))
        tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
        size = 0
        with tmp_path.open("wb") as out:
            for part in parts:
                data = part.read_bytes()
                size += len(data)
                out.write(data)
        if size != int(meta.get("size", -1)) or size > MAX_UPLOAD_SIZE:
            tmp_path.unlink(missing_ok=True)
            return JSONResponse({"ok": False, "error": "文件大小校验失败"}, status_code=409)
        os.replace(tmp_path, filepath)
        result = _upload_result(stored_name, meta.get("name"), meta.get("content_type"), size)
        completed = True
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"文件合并失败: {exc}"}, status_code=500)
    finally:
        if completed and session_dir.exists():
            for child in session_dir.iterdir():
                child.unlink(missing_ok=True)
            session_dir.rmdir()
    return result
