"""Portable-only process ownership and authenticated lifecycle control."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import socket
import threading
import time
import urllib.request

CONTROL = "/_portable/"


def signature(secret: str, message: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


class InstanceLease:
    """An OS-held lock, released even after a crash; records never authorize a PID kill."""

    def __init__(self, data: Path):
        self.data = data.resolve()
        self.record_path = self.data / "portable-instance.json"
        self.handle = None

    def acquire(self) -> bool:
        self.data.mkdir(parents=True, exist_ok=True)
        handle = (self.data / "portable-instance.lock").open("a+b")
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self.handle = handle
        return True

    def publish(self, record: dict) -> None:
        if self.handle is None:
            raise ValueError("Le lanceur ne possède pas le dossier de données.")
        temporary = self.data / (".portable-instance-" + secrets.token_hex(8) + ".tmp")
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(record, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.record_path)
        finally:
            temporary.unlink(missing_ok=True)

    def close(self, instance_id: str = "") -> None:
        if self.handle:
            try:
                record = json.loads(self.record_path.read_text(encoding="utf-8"))
                if isinstance(record, dict) and instance_id and record.get("instance_id") == instance_id:
                    self.record_path.unlink()
            except (OSError, ValueError):
                pass
            self.handle.close()
            self.handle = None


def build_identity(root: Path, data: Path, port: int) -> dict:
    manifest = json.loads((root / "portable-manifest.json").read_text(encoding="utf-8"))
    return {"root": str(root.resolve()), "data": str(data.resolve()), "port": port,
            "manifest_sha256": hashlib.sha256((root / "portable-manifest.json").read_bytes()).hexdigest(),
            "version": manifest.get("application_version", "0.2.1"),
            "source_commit": manifest.get("source_commit", ""),
            "wheel_sha256": manifest.get("application_wheel_sha256", "")}


def owned_request(record: dict, action: str = "identity", timeout: float = 2) -> dict:
    port = record.get("port")
    secret = record.get("secret")
    if (type(port) is not int or not 1 <= port <= 65535
            or not isinstance(secret, str) or len(secret) < 40 or action not in {"identity", "stop"}):
        raise ValueError("Identité du lanceur invalide.")
    method = "POST" if action == "stop" else "GET"
    path = CONTROL + action
    nonce = secrets.token_hex(24)
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method,
                                    headers={"X-Portable-Nonce": nonce,
                                             "X-Portable-Signature": signature(secret, f"{method}:{path}:{nonce}")})
    # Local lifecycle requests never go through a machine proxy.
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=timeout) as response:
        raw = response.read(32769)
        if len(raw) > 32768 or not hmac.compare_digest(response.headers.get("X-Portable-Signature", ""),
                                                      signature(secret, nonce + ":" + raw.decode())):
            raise ValueError("Le service ne correspond pas à ce lanceur.")
    result = json.loads(raw)
    for key in ("instance_id", "root", "data", "port", "manifest_sha256"):
        if result.get(key) != record.get(key):
            raise ValueError("L’instance locale a changé. Aucun arrêt demandé.")
    return result


def existing_instance(lease: InstanceLease, identity: dict) -> dict:
    deadline = time.monotonic() + 20
    while True:
        try:
            record = json.loads(lease.record_path.read_text(encoding="utf-8"))
            if not isinstance(record, dict):
                raise ValueError("Identité du lanceur illisible. Fermez sa fenêtre avant de continuer.")
            if record.get("data") != identity["data"]:
                raise ValueError("Le dossier de l’instance active ne correspond pas.")
            actual = owned_request(record)
            if any(actual.get(key) != identity[key] for key in ("root", "manifest_sha256", "port")):
                raise ValueError("Une autre version ou un autre port utilise ces données. Fermez son lanceur avant de continuer.")
            return record
        except (OSError, json.JSONDecodeError):
            if time.monotonic() >= deadline:
                raise ValueError("Un lanceur utilise ces données mais ne répond pas. Attendez son démarrage ou fermez sa fenêtre.") from None
            time.sleep(.1)


class PortableService:
    def __init__(self, root: Path, data: Path, port: int, lease: InstanceLease, identity: dict):
        self.root, self.data, self.port, self.lease = root, data, port, lease
        self.record = {**identity, "instance_id": secrets.token_hex(24), "secret": secrets.token_urlsafe(48)}
        self.server = None
        self.thread = None
        self.error = ""
        self.ready = False
        self.stopping = False
        self.finished = threading.Event()
        self._nonces: set[str] = set()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def public_identity(self) -> dict:
        return {key: value for key, value in self.record.items() if key != "secret"}

    def stop(self) -> None:
        self.stopping = True
        if self.server:
            self.server.should_exit = True

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name="vanguard-portable", daemon=False)
        self.thread.start()

    def _run(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if os.name == "nt":
                # Windows needs exclusive ownership, not SO_REUSEADDR semantics.
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                # POSIX TIME_WAIT sockets must not block a deliberate restart.
                # SO_REUSEPORT is never enabled; an active listener still refuses bind.
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", self.port))
            listener.listen(128)
            from fat_studio.app import create_app
            import uvicorn

            app = create_app(data_dir=self.data)
            async def wrapped(scope, receive, send):
                if scope["type"] == "http" and scope["path"].startswith(CONTROL):
                    await self._control(scope, send)
                else:
                    await app(scope, receive, send)
            self.server = uvicorn.Server(uvicorn.Config(wrapped, host="127.0.0.1", port=self.port,
                                                        log_level="info", access_log=False))
            if self.stopping:
                self.server.should_exit = True
                return
            self.lease.publish(self.record)
            self.server.run(sockets=[listener])
            if not self.server.started and not self.stopping:
                self.error = "Le service n’a pas démarré. Consultez le journal du lanceur."
        except BaseException as exc:
            self.error = (f"Le port {self.port} est déjà utilisé. Fermez l’autre instance ou choisissez un autre port."
                          if isinstance(exc, OSError) and getattr(exc, "errno", None) in {98, 10048, 48}
                          else str(exc) or "Le service local n’a pas démarré.")
        finally:
            listener.close()
            self.lease.close(self.record["instance_id"])
            self.finished.set()

    async def _control(self, scope, send):
        # HTTP field values are bytes; malformed authentication is a refusal, not a 500.
        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope["headers"]}
        method, path = scope["method"], scope["path"]
        nonce = headers.get("x-portable-nonce", "")
        expected = signature(self.record["secret"], f"{method}:{path}:{nonce}")
        allowed = ((method, path) in {("GET", CONTROL + "identity"), ("POST", CONTROL + "stop")}
                   and headers.get("host") == f"127.0.0.1:{self.port}"
                   and not headers.get("origin") and re.fullmatch(r"[0-9a-f]{48}", nonce) is not None
                   and re.fullmatch(r"[0-9a-f]{64}", headers.get("x-portable-signature", "")) is not None
                   and nonce not in self._nonces
                   and hmac.compare_digest(headers.get("x-portable-signature", ""), expected))
        body = json.dumps(self.public_identity() if allowed else {"detail": "Accès refusé."}).encode()
        response_headers = [(b"content-type", b"application/json"), (b"cache-control", b"no-store")]
        if allowed:
            self._nonces.add(nonce)
            if len(self._nonces) > 4096:
                # Requests carry fresh nonces; keep memory bounded for long sessions.
                self._nonces = {nonce}
            response_headers.append((b"x-portable-signature", signature(self.record["secret"], nonce + ":" + body.decode()).encode()))
        await send({"type": "http.response.start", "status": 200 if allowed else 403, "headers": response_headers})
        await send({"type": "http.response.body", "body": body})
        if allowed and method == "POST":
            self.stop()

    def wait_ready(self, timeout: float = 25) -> bool:
        deadline = time.monotonic() + timeout
        while not self.finished.is_set() and time.monotonic() < deadline:
            if self.server and self.server.started:
                self.ready = True
                return True
            time.sleep(.05)
        if not self.error:
            self.error = "Le démarrage a dépassé le délai prévu. Consultez le journal."
        self.stop()
        return False
