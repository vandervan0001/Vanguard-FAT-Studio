"""Portable lifecycle and update boundaries use isolated local processes/data."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import runpy
import socket
import sqlite3
import struct
import time
import urllib.error
import urllib.request
import zipfile

import pytest
import httpx

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
HOST = runpy.run_path(str(SCRIPTS / "portable_host.py"))
UPDATE = runpy.run_path(str(SCRIPTS / "portable_update.py"))
CHECK = runpy.run_path(str(SCRIPTS / "check-portable.py"))["validate_portable"]


def port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


@pytest.fixture
def service(tmp_path):
    root, data = tmp_path / "Portable with spaces", tmp_path / "Données FAT"
    root.mkdir()
    (root / "portable-manifest.json").write_text(json.dumps({"application_version": "0.3.0", "application_wheel_sha256": "a" * 64}))
    lease = HOST["InstanceLease"](data)
    assert lease.acquire()
    identity = HOST["build_identity"](root, data, port())
    instance = HOST["PortableService"](root, data, identity["port"], lease, identity)
    instance.start()
    assert instance.wait_ready(), instance.error
    try:
        yield instance, identity
    finally:
        instance.stop()
        assert instance.finished.wait(15), "Portable shutdown did not finish"
        instance.thread.join()


def test_reopen_and_authenticated_shutdown_preserve_history_and_release_lock(service):
    instance, identity = service
    second = HOST["InstanceLease"](instance.data)
    assert not second.acquire()
    record = HOST["existing_instance"](second, identity)
    result = HOST["owned_request"](record)
    assert result["root"] == str(instance.root)
    assert result["version"] == "0.3.0" and "secret" not in result
    with urllib.request.urlopen(instance.url + "/api/health") as response:
        assert json.load(response)["status"] == "ok"
    history = instance.data / "history.sqlite3"
    assert history.is_file()
    HOST["owned_request"](record, "stop")
    assert instance.finished.wait(15)
    assert history.is_file() and not (instance.data / "portable-instance.json").exists()
    assert second.acquire()
    second.close()


def test_control_rejects_unsigned_wrong_build_and_wrong_data_without_stopping(service):
    instance, identity = service
    for action in ("identity", "stop"):
        request = urllib.request.Request(instance.url + "/_portable/" + action, method="POST" if action == "stop" else "GET")
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        assert error.value.code == 403
    lease = HOST["InstanceLease"](instance.data)
    assert not lease.acquire()
    with pytest.raises(ValueError, match="autre version"):
        HOST["existing_instance"](lease, {**identity, "manifest_sha256": "0" * 64})
    with pytest.raises(ValueError, match="dossier"):
        HOST["existing_instance"](lease, {**identity, "data": "other data"})
    assert not instance.finished.is_set()


def test_control_rejects_origin_and_nonce_replay(service):
    instance, _ = service
    record = instance.record
    path, nonce = "/_portable/identity", "f" * 48
    headers = {"X-Portable-Nonce": nonce,
               "X-Portable-Signature": HOST["signature"](record["secret"], f"GET:{path}:{nonce}")}
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(urllib.request.Request(instance.url + path, headers={**headers, "Origin": "https://example.com"}))
    with urllib.request.urlopen(urllib.request.Request(instance.url + path, headers=headers)) as response:
        assert response.status == 200
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(urllib.request.Request(instance.url + path, headers=headers))


@pytest.mark.parametrize("field", [b"x-portable-signature", b"x-portable-nonce"])
def test_control_rejects_non_ascii_headers_as_forbidden_without_server_error(service, field):
    instance, _ = service
    headers = {b"x-portable-nonce": b"a" * 48, b"x-portable-signature": b"b" * 64, field: b"\xff" * 48}
    with httpx.Client(base_url=instance.url, trust_env=False) as client:
        response = client.get("/_portable/identity", headers=headers)
        assert response.status_code == 403
        assert client.get("/api/health").status_code == 200


def test_download_has_total_time_limit_for_trickling_response(tmp_path, monkeypatch):
    clock = [0.0]
    class Trickle(io.BytesIO):
        def read(self, size=-1):
            clock[0] += 100
            return super().read(1)
        read1 = read
    monkeypatch.setattr(UPDATE["download"].__globals__["urllib"].request, "urlopen", lambda *args, **kwargs: Trickle(b"ab"))
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    value = {"url": candidate()["browser_download_url"], "size": 2, "sha256": hashlib.sha256(b"ab").hexdigest()}
    with pytest.raises(ValueError, match="délai"):
        UPDATE["download"](value, tmp_path / "slow.zip")


def test_quit_closes_active_demo_and_next_process_keeps_samples_without_resuming(service):
    instance, identity = service
    with httpx.Client(base_url=instance.url, trust_env=False) as client:
        responses = {name: client.get("/api/" + name) for name in ("health", "project", "state", "catalog", "schema")}
        assert all(response.is_success for response in responses.values())
        project, state = responses["project"].json(), responses["state"].json()
        assert project["plc"]["mode"] == "demo" and state["status"] == "idle"
        headers = {"X-FAT-Token": client.get("/api/session").json()["token"], "X-FAT-Project-ID": project["id"],
                   "X-FAT-Project-Revision": responses["project"].headers["x-fat-project-revision"], "X-FAT-Run-ID": ""}
        started = client.post("/api/run/start", json={}, headers=headers)
        assert started.is_success, started.text
        run_id = started.json()["run_id"]
        deadline = time.monotonic() + 5
        while client.get("/api/state").json()["sim_time_s"] < .3 and time.monotonic() < deadline:
            time.sleep(.05)
    HOST["owned_request"](instance.record, "stop")
    assert instance.finished.wait(15)
    with sqlite3.connect(instance.data / "history.sqlite3") as database:
        count = database.execute("SELECT COUNT(*) FROM samples WHERE run_id=?", (run_id,)).fetchone()[0]
        result = database.execute("SELECT status,ended_at,result_json FROM runs WHERE id=?", (run_id,)).fetchone()
    assert count > 0 and result[0] == "stopped" and result[1] is not None
    assert json.loads(result[2])["verdict"] == "not_evaluated"
    lease = HOST["InstanceLease"](instance.data)
    assert lease.acquire()
    next_instance = HOST["PortableService"](instance.root, instance.data, instance.port, lease, identity)
    next_instance.start()
    try:
        assert next_instance.wait_ready(), next_instance.error
        with httpx.Client(base_url=instance.url, trust_env=False) as client:
            assert client.get("/api/state").json()["status"] == "idle"
        with sqlite3.connect(instance.data / "history.sqlite3") as database:
            assert database.execute("SELECT COUNT(*) FROM samples WHERE run_id=?", (run_id,)).fetchone()[0] == count
    finally:
        next_instance.stop()
        assert next_instance.finished.wait(15)


def test_foreign_port_refused_without_creating_application_storage(tmp_path):
    root, data = tmp_path / "root", tmp_path / "data"
    root.mkdir()
    (root / "portable-manifest.json").write_text("{}")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        identity = HOST["build_identity"](root, data, listener.getsockname()[1])
        lease = HOST["InstanceLease"](data)
        assert lease.acquire()
        instance = HOST["PortableService"](root, data, identity["port"], lease, identity)
        instance.start()
        assert instance.finished.wait(5)
        instance.thread.join()
        assert instance.error
        assert not (data / "history.sqlite3").exists()
        assert lease.acquire()
        lease.close()


def test_corrupt_owner_record_cannot_authorize_reopen_or_break_release(tmp_path):
    lease = HOST["InstanceLease"](tmp_path / "data")
    assert lease.acquire()
    lease.record_path.write_text("[]")
    with pytest.raises(ValueError, match="illisible"):
        HOST["existing_instance"](lease, {"data": str(lease.data)})
    lease.close("does-not-match")
    assert lease.acquire()
    assert lease.record_path.read_text() == "[]"
    lease.close()


def candidate(name="Vanguard-FAT-Studio-Windows-x64-2026-11-09-UX.zip", created="2026-11-09T10:00:00Z"):
    return {"name": name, "digest": "sha256:" + "1" * 64, "size": 123,
            "browser_download_url": "https://github.com/vandervan0001/Vanguard-FAT-Studio/releases/download/v0.3.0/" + name,
            "state": "uploaded", "created_at": created}


def test_update_selects_latest_release_and_latest_verified_portable_deterministically():
    old, new = candidate(created="2026-11-07T10:00:00Z"), candidate()
    assert UPDATE["latest_candidate"]([
        {"tag_name": "old", "published_at": "2026-11-07", "assets": [old]},
        {"tag_name": "v0.3.0", "published_at": "2026-11-09", "assets": [new, {**new, "digest": None}]},
        {"tag_name": "draft", "published_at": "2026-11-10", "draft": True, "assets": [new]},
    ])["release"] == "v0.3.0"
    with pytest.raises(ValueError, match="officielle"):
        UPDATE["latest_candidate"]([{"assets": [{**new, "browser_download_url": "https://example.com/payload.zip"}]}])


def portable_zip(path, extra=None):
    payloads = {"launch.py": b"raise SystemExit(0)\n", "runtime/pythonw.exe": b"fixture-not-executable", "app/value.txt": b"verified"}
    manifest = {"schema": 1, "platform": "Windows-x64", "python": "3.12.10", "application_version": "0.3.0",
                "files": [{"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in payloads.items()]}
    payloads["portable-manifest.json"] = json.dumps(manifest).encode()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in payloads.items():
            archive.writestr("Vanguard-FAT-Studio/" + name, data)
        if extra:
            archive.writestr(*extra)
    return path


def test_update_prepares_new_sibling_without_executing_payload_or_changing_old_data(tmp_path):
    old = tmp_path / "old"
    old.mkdir()
    (old / "history.sqlite3").write_bytes(b"user history")
    result = UPDATE["prepare_archive"](portable_zip(tmp_path / "update.zip"), tmp_path / "New portable", CHECK)
    assert result == tmp_path / "New portable/Vanguard-FAT-Studio"
    assert CHECK(result) == 3
    assert (old / "history.sqlite3").read_bytes() == b"user history"
    with pytest.raises(ValueError, match="existe"):
        UPDATE["prepare_archive"](tmp_path / "update.zip", tmp_path / "New portable", CHECK)


@pytest.mark.parametrize("name", ["../escape.txt", "C:/escape.txt", "x\\escape.txt", "x/CON.txt", "x/name. ", "VANGUARD-FAT-STUDIO/launch.py"])
def test_update_rejects_unsafe_paths_before_creating_destination(tmp_path, name):
    archive = portable_zip(tmp_path / "update.zip", (name, "bad"))
    if "\\" in name:
        # ZipInfo normalizes OS separators on Windows; inject a foreign ZIP name.
        archive.write_bytes(archive.read_bytes().replace(name.replace("\\", "/").encode(), name.encode()))
    with pytest.raises(ValueError, match="Chemin"):
        UPDATE["prepare_archive"](archive, tmp_path / "new", CHECK)
    assert not (tmp_path / "new").exists()


def test_update_rejects_symlink_and_modified_manifest_payload(tmp_path):
    item = zipfile.ZipInfo("linked")
    item.create_system = 3
    item.external_attr = 0o120777 << 16
    archive = portable_zip(tmp_path / "linked.zip", (item, "../elsewhere"))
    with pytest.raises(ValueError):
        UPDATE["prepare_archive"](archive, tmp_path / "new", CHECK)
    archive = portable_zip(tmp_path / "modified.zip")
    with zipfile.ZipFile(archive) as source:
        entries = {name: source.read(name) for name in source.namelist()}
    entries["Vanguard-FAT-Studio/app/value.txt"] = b"tampered"
    with zipfile.ZipFile(archive, "w") as output:
        for name, data in entries.items():
            output.writestr(name, data)
    with pytest.raises(ValueError, match="modified"):
        UPDATE["prepare_archive"](archive, tmp_path / "new", CHECK)
    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("damage", ["entry_count", "expanded_size", "encrypted"])
def test_update_resource_and_encryption_limits_precede_extraction(tmp_path, monkeypatch, damage):
    archive = portable_zip(tmp_path / "bounded.zip")
    raw = bytearray(archive.read_bytes())
    header = raw.index(b"PK\x01\x02")
    if damage == "entry_count":
        monkeypatch.setitem(UPDATE["safe_entries"].__globals__, "MAX_ENTRIES", 2)
    elif damage == "expanded_size":
        struct.pack_into("<I", raw, header + 24, UPDATE["MAX_EXPANDED"] + 1)
        archive.write_bytes(raw)
    else:
        struct.pack_into("<H", raw, header + 8, 1)
        archive.write_bytes(raw)
    with pytest.raises(ValueError, match="limites|Chemin"):
        UPDATE["prepare_archive"](archive, tmp_path / "new", CHECK)
    assert not (tmp_path / "new").exists()


def test_download_requires_exact_published_hash_and_size(tmp_path, monkeypatch):
    raw = b"download fixture"
    class Reply(io.BytesIO):
        pass
    monkeypatch.setattr(UPDATE["download"].__globals__["urllib"].request, "urlopen", lambda *args, **kwargs: Reply(raw))
    value = {"url": candidate()["browser_download_url"], "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    UPDATE["download"](value, tmp_path / "ok.zip")
    assert (tmp_path / "ok.zip").read_bytes() == raw
    with pytest.raises(ValueError, match="empreinte"):
        UPDATE["download"]({**value, "sha256": "f" * 64}, tmp_path / "bad.zip")
    with pytest.raises(ValueError, match="taille"):
        UPDATE["download"]({**value, "size": 1}, tmp_path / "short.zip")
