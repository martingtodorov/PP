"""Uploads must survive a dead managed-storage mirror and files on disk must stay servable."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MEDIA_ROOT", "/tmp/pp-test-media")

import storage  # noqa: E402


@pytest.fixture(autouse=True)
def media_root(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "MEDIA_ROOT", tmp_path)
    yield tmp_path


def test_put_object_survives_remote_failure(monkeypatch):
    monkeypatch.setattr(storage, "REMOTE_ENABLED", True)

    def boom(*a, **k):
        raise RuntimeError("mirror down")

    monkeypatch.setattr(storage, "_mirror_remote", boom)
    result = storage.put_object("import/abc-test.png", b"bytes", "image/png")
    assert result["path"] == "import/abc-test.png"
    assert result["mirrored"] is False
    assert storage.local_exists("import/abc-test.png")
    data, ctype = storage.get_object("import/abc-test.png")
    assert data == b"bytes" and ctype == "image/png"


def test_put_object_mirrors_when_remote_ok(monkeypatch):
    monkeypatch.setattr(storage, "REMOTE_ENABLED", True)
    calls = []
    monkeypatch.setattr(storage, "_mirror_remote", lambda *a: calls.append(a))
    assert storage.put_object("import/x.png", b"1", "image/png")["mirrored"] is True
    assert calls


def test_local_exists_rejects_escape():
    assert storage.local_exists("../../etc/passwd") is False


def test_diagnose_reports_writable(monkeypatch):
    monkeypatch.setattr(storage, "REMOTE_ENABLED", False)
    info = storage.diagnose()
    assert info["writable"] is True and info["exists"] is True
    assert info["remote_ok"] is None
    assert not list(Path(info["media_root"]).glob(".probe-*"))


def test_diagnose_reports_unwritable(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "REMOTE_ENABLED", False)
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o555)
    monkeypatch.setattr(storage, "MEDIA_ROOT", ro)
    info = storage.diagnose()
    if os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")
    assert info["writable"] is False and "Permission" in info["write_error"]
