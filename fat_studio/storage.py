"""Readable project files, atomic saves, and an append-only SQLite test record."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Project
from .branding import APP_NAME
from .security import atomic_json, safe_id


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.projects_dir = self.root / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self._lock_file = (self.root / "instance.lock").open("a+b")
        self._lock_file.seek(0, 2)
        if self._lock_file.tell() == 0:
            self._lock_file.write(b"0")
            self._lock_file.flush()
        self._lock_file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._lock_file.close()
            raise ValueError(f"Un autre processus {APP_NAME} utilise déjà ce dossier de données.") from exc
        self.db = None
        try:
            self.db = sqlite3.connect(self.root / "history.sqlite3", check_same_thread=False)
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT,
                project_name TEXT NOT NULL, project_json TEXT NOT NULL,
                scenario_json TEXT, status TEXT NOT NULL, result_json TEXT NOT NULL,
                connection_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
                timestamp TEXT NOT NULL, sim_time_s REAL NOT NULL,
                values_json TEXT NOT NULL, quality_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS sample_run ON samples(run_id, id);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
                timestamp TEXT NOT NULL, sim_time_s REAL NOT NULL,
                kind TEXT NOT NULL, message TEXT NOT NULL, details_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS event_run ON events(run_id, id);
            """)
            # A process restart never resumes a PLC run. Preserve evidence of interruption.
            with self.db:
                self.db.execute(
                    "UPDATE runs SET status='interrupted', ended_at=? WHERE ended_at IS NULL", (utc_now(),)
                )
        except BaseException:
            if self.db is not None:
                self.db.close()
            self._lock_file.close()
            raise

    def close(self) -> None:
        try:
            self.db.close()
        finally:
            self._lock_file.close()

    def save_project(self, project: Project) -> None:
        path = self.projects_dir / f"{safe_id(project.id)}.json"
        if path.is_symlink():
            raise ValueError("Un fichier projet ne peut pas être un lien symbolique.")
        current = project.model_dump(mode="json")
        if path.exists():
            backup = self.projects_dir / f"{project.id}.previous.json"
            previous = json.loads(path.read_text(encoding="utf-8"))
            # Loading or re-saving an unchanged document is not a new revision.
            # Keep the last distinct saved version available for recovery.
            if previous != current:
                atomic_json(backup, previous)
                atomic_json(path, current)
        else:
            atomic_json(path, current)
        atomic_json(self.root / "last-project.json", {"id": project.id})

    def load_project(self, project_id: str) -> Project:
        path = self.projects_dir / f"{safe_id(project_id)}.json"
        if path.is_symlink():
            raise ValueError("Un fichier projet ne peut pas être un lien symbolique.")
        project = Project.model_validate_json(path.read_text(encoding="utf-8"))
        if project.id != project_id:
            raise ValueError("L'identifiant interne du projet ne correspond pas au nom du fichier.")
        return project

    def last_project(self) -> Project | None:
        path = self.root / "last-project.json"
        if not path.exists():
            if any(self.projects_dir.glob("*.json")):
                raise ValueError("Le fichier last-project.json est absent alors que des projets sont enregistrés.")
            return None
        pointer = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(pointer, dict) or not isinstance(pointer.get("id"), str):
            raise ValueError("Le fichier last-project.json doit contenir un identifiant de projet texte.")
        return self.load_project(pointer["id"])

    def list_projects(self) -> list[dict]:
        result = []
        for path in sorted(self.projects_dir.glob("*.json")):
            if path.name.endswith(".previous.json") or path.is_symlink():
                continue
            try:
                project = self.load_project(path.stem)
                result.append({"id": project.id, "name": project.name,
                               "updated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()})
            except (ValueError, OSError) as exc:
                result.append({"id": path.stem, "name": path.stem, "updated_at": None, "error": str(exc)})
        return result

    def start_run(self, run_id: str, project: Project, scenario, connection: dict) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO runs VALUES (?, ?, NULL, ?, ?, ?, 'running', ?, ?)",
                (run_id, utc_now(), project.name, encode(project.model_dump(mode="json")),
                 encode(scenario.model_dump(mode="json")) if scenario else None,
                 encode({"verdict": "not_evaluated", "comment": ""}), encode(connection)),
            )

    def event(self, run_id: str, sim_time_s: float, kind: str, message: str, details=None) -> dict:
        with self.db:
            return self._insert_event(run_id, sim_time_s, kind, message, details)

    def _insert_event(self, run_id: str, sim_time_s: float, kind: str, message: str, details=None) -> dict:
        """Insert into the caller's transaction, so related evidence is atomic."""
        timestamp = utc_now()
        cursor = self.db.execute(
            "INSERT INTO events(run_id,timestamp,sim_time_s,kind,message,details_json) VALUES (?,?,?,?,?,?)",
            (run_id, timestamp, sim_time_s, kind, message, encode(details or {})),
        )
        return {"id": cursor.lastrowid, "timestamp": timestamp, "sim_time_s": sim_time_s,
                "kind": kind, "message": message, "details": details or {}}

    def sample(self, run_id: str, sim_time_s: float, values: dict, qualities: dict) -> str:
        timestamp = utc_now()
        with self.db:
            self.db.execute(
                "INSERT INTO samples(run_id,timestamp,sim_time_s,values_json,quality_json) VALUES (?,?,?,?,?)",
                (run_id, timestamp, sim_time_s, encode(values), encode(qualities)),
            )
        return timestamp

    def set_status(self, run_id: str, status: str, ended: bool = False) -> None:
        with self.db:
            if ended:
                self.db.execute("UPDATE runs SET status=?,ended_at=? WHERE id=?", (status, utc_now(), run_id))
            else:
                self.db.execute("UPDATE runs SET status=? WHERE id=?", (status, run_id))

    def set_result(self, run_id: str, verdict: str, comment: str, *, sim_time_s: float = 0) -> dict:
        result = {"verdict": verdict, "comment": comment}
        with self.db:
            updated = self.db.execute("UPDATE runs SET result_json=? WHERE id=?", (encode(result), run_id))
            if updated.rowcount != 1:
                raise ValueError("Essai introuvable.")
            return self._insert_event(run_id, sim_time_s, "user_result", "Verdict utilisateur : " + verdict, result)

    def runs(self) -> list[dict]:
        return [dict(row) for row in self.db.execute(
            "SELECT id,started_at,ended_at,project_name,status,result_json FROM runs ORDER BY started_at DESC LIMIT 500"
        )]

    def run(self, run_id: str) -> dict:
        # One statement fixes metadata and both append-only table boundaries at
        # the same instant. Streaming later includes exactly this finite prefix.
        row = self.db.execute("""
            SELECT runs.*,
                (SELECT count(*) FROM samples WHERE run_id=runs.id) AS sample_count,
                (SELECT coalesce(max(id), 0) FROM samples WHERE run_id=runs.id) AS last_sample_id,
                (SELECT coalesce(max(id), 0) FROM events WHERE run_id=runs.id) AS last_event_id
            FROM runs WHERE id=?
        """, (safe_id(run_id),)).fetchone()
        if row is None:
            raise ValueError("Essai introuvable.")
        result = dict(row)
        result["snapshot"] = {"captured_at": utc_now(),
                              "last_sample_id": result.pop("last_sample_id"),
                              "last_event_id": result.pop("last_event_id")}
        for key in ("project", "scenario", "result", "connection"):
            raw = result.pop(key + "_json")
            result[key] = json.loads(raw) if raw else None
        result["events"] = []
        for event in self.db.execute("SELECT * FROM events WHERE run_id=? AND id<=? ORDER BY id",
                                     (run_id, result["snapshot"]["last_event_id"])):
            entry = dict(event)
            entry["details"] = json.loads(entry.pop("details_json"))
            result["events"].append(entry)
        return result

    def samples(self, run_id: str, *, through_id: int | None = None):
        # Dedicated read-only connection: large streamed exports cannot alter the runtime cursor.
        # AnyIO may resume a synchronous generator on a different worker thread;
        # each iterator still executes sequentially and owns this connection.
        uri = (self.root / "history.sqlite3").as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        try:
            query = "SELECT * FROM samples WHERE run_id=?"
            arguments = [safe_id(run_id)]
            if through_id is not None:
                query += " AND id<=?"
                arguments.append(through_id)
            for row in connection.execute(query + " ORDER BY id", arguments):
                item = dict(row)
                item["values"] = json.loads(item.pop("values_json"))
                item["qualities"] = json.loads(item.pop("quality_json"))
                yield item
        finally:
            connection.close()
