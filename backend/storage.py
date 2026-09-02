"""Object storage helper.

Two backends, transparently combined:

* local disk (`MEDIA_ROOT`) — the source of truth on our own servers
* Emergent managed object storage — used while running on the platform

Reads try the local disk first and lazily mirror remote objects to it, so a server that
starts empty fills up on demand and keeps working if the remote is ever unavailable.
"""
import logging
import os
from pathlib import Path
from typing import Tuple

import requests

log = logging.getLogger("purepeptide.storage")

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "purepeptide"

MEDIA_ROOT = Path(os.environ["MEDIA_ROOT"]).resolve()
REMOTE_ENABLED = bool((EMERGENT_KEY or "").strip())

MIME_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp", "svg": "image/svg+xml",
}

_storage_key = None


def _local_path(path: str) -> Path:
    target = (MEDIA_ROOT / path.lstrip("/")).resolve()
    if MEDIA_ROOT not in target.parents and target != MEDIA_ROOT:
        raise ValueError("Невалиден път за файл")
    return target


def init_storage(force: bool = False) -> str:
    """Prepare the media directory and (when available) the remote storage session."""
    global _storage_key
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    if not REMOTE_ENABLED:
        return "local"
    if _storage_key and not force:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def _write_local(path: str, data: bytes) -> None:
    target = _local_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def local_exists(path: str) -> bool:
    try:
        return _local_path(path).is_file()
    except ValueError:
        return False


def _mirror_remote(path: str, data: bytes, content_type: str) -> None:
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=120,
        )
    resp.raise_for_status()


def put_object(path: str, data: bytes, content_type: str) -> dict:
    """The disk is the source of truth; the managed storage is a best-effort mirror."""
    _write_local(path, data)
    result = {"path": path, "size": len(data), "mirrored": False}
    if REMOTE_ENABLED:
        try:
            _mirror_remote(path, data, content_type)
            result["mirrored"] = True
        except Exception as ex:  # a dead mirror must never break an upload
            log.warning("Remote mirror failed for %s: %s", path, ex)
    return result


def diagnose() -> dict:
    """Everything an admin needs to see why an image could be missing on this server."""
    import getpass
    import uuid

    info = {
        "media_root": str(MEDIA_ROOT),
        "process_user": getpass.getuser(),
        "exists": MEDIA_ROOT.is_dir(),
        "writable": False,
        "write_error": None,
        "files_on_disk": 0,
        "size_mb": 0.0,
        "remote_enabled": REMOTE_ENABLED,
        "remote_ok": None,
        "remote_error": None,
    }
    probe = MEDIA_ROOT / f".probe-{uuid.uuid4().hex}"
    try:
        MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
        probe.write_bytes(b"ok")
        probe.unlink()
        info["writable"] = True
    except Exception as ex:
        info["write_error"] = f"{type(ex).__name__}: {ex}"
    if info["exists"]:
        files = [f for f in MEDIA_ROOT.rglob("*") if f.is_file()]
        info["files_on_disk"] = len(files)
        info["size_mb"] = round(sum(f.stat().st_size for f in files) / 1_048_576, 1)
    if REMOTE_ENABLED:
        try:
            init_storage(force=True)
            info["remote_ok"] = True
        except Exception as ex:
            info["remote_ok"] = False
            info["remote_error"] = f"{type(ex).__name__}: {ex}"
    return info


def get_object(path: str) -> Tuple[bytes, str]:
    """Local disk first, then the managed storage (mirroring the object on the way)."""
    ext = path.rsplit(".", 1)[-1].lower()
    content_type = MIME_TYPES.get(ext, "application/octet-stream")
    local = _local_path(path)
    if local.exists():
        return local.read_bytes(), content_type
    if not REMOTE_ENABLED:
        raise FileNotFoundError(path)
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    _write_local(path, resp.content)
    return resp.content, resp.headers.get("Content-Type", content_type)
