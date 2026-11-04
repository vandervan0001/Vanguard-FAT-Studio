"""Portable project evidence archives. No global database, credentials or connection activation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import io
import json
import math
import re
import sqlite3
import zipfile

from .mapping import export_mapping
from .exchange import project_package, scenarios_package
from .models import PLCConfig, Project, Scenario, validate_project, validate_value
from .reporting import csv_stream, html_report, json_stream
from .security import safe_id
from .storage import Store, encode, utc_now


MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_EXPANDED_BYTES = 250 * 1024 * 1024
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_FILES = 3000
MAX_RATIO = 1000


class ArchiveSnapshot:
    """A pinned read-only SQLite transaction, owned sequentially by one exporter.

    Capture under the runtime lock, then export outside it. A worker owns this
    connection until export has actually finished, including on HTTP cancellation.
    No Store constructor, startup recovery or instance lock is involved.
    """

    def __init__(self, store: Store, project: Project):
        self.root = store.root
        self.project = project.model_copy(deep=True)
        uri = (self.root / "history.sqlite3").as_uri() + "?mode=ro"
        self.db = sqlite3.connect(uri, uri=True, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self._closed = False
        try:
            self.db.execute("PRAGMA query_only=ON")
            self.db.execute("BEGIN")
            # BEGIN alone is deferred. The first table read pins the WAL view,
            # even when runs is empty, before the caller releases its lock.
            cursor = self.db.execute("SELECT id FROM runs LIMIT 1")
            try:
                cursor.fetchone()
            finally:
                cursor.close()
            self.captured_at = utc_now()
        except BaseException:
            self.db.close()
            self._closed = True
            raise

    def run(self, run_id: str) -> dict:
        result = Store.run(self, run_id)
        result["snapshot"]["captured_at"] = self.captured_at
        return result

    def samples(self, run_id: str, *, through_id: int | None = None):
        query = "SELECT * FROM samples WHERE run_id=?"
        arguments = [safe_id(run_id)]
        if through_id is not None:
            query += " AND id<=?"
            arguments.append(through_id)
        cursor = self.db.execute(query + " ORDER BY id", arguments)
        try:
            for row in cursor:
                item = dict(row)
                item["values"] = json.loads(item.pop("values_json"))
                item["qualities"] = json.loads(item.pop("quality_json"))
                yield item
        finally:
            cursor.close()

    def close(self) -> None:
        if not self._closed:
            self.db.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def capture_archive(store: Store, project: Project) -> ArchiveSnapshot:
    """Pin a global read view quickly; caller closes it after the worker finishes."""
    return ArchiveSnapshot(store, project)


def _json(value: bytes):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field: " + key)
            result[key] = item
        return result

    def constant(value):
        raise ValueError("Non-finite JSON number: " + value)

    try:
        result = json.loads(value.decode("utf-8-sig"), object_pairs_hook=unique, parse_constant=constant)
    except RecursionError as exc:
        raise ValueError("JSON nesting limit exceeded") from exc
    def finite(item):
        if type(item) is float and not math.isfinite(item):
            raise ValueError("Non-finite JSON number")
        if isinstance(item, dict):
            for nested in item.values():
                finite(nested)
        elif isinstance(item, list):
            for nested in item:
                finite(nested)
    try:
        finite(result)
    except RecursionError as exc:
        raise ValueError("JSON nesting limit exceeded") from exc
    return result


def _bytes(value) -> bytes:
    return (encode(value) + "\n").encode("utf-8")


def _name(name: str) -> str:
    if (not isinstance(name, str) or not name or name.startswith("/") or "\\" in name or ":" in name
            or any(part in {"", ".", ".."} or part.endswith((".", " ")) for part in name.split("/"))):
        raise ValueError("Invalid archive path")
    if any(part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)],
                                           *[f"LPT{i}" for i in range(1, 10)]} for part in name.split("/")):
        raise ValueError("Reserved archive path")
    return name


@dataclass(frozen=True)
class ArchivePlan:
    """Immutable validated bytes; every use reparses rather than trusting mutable models."""

    payload: bytes
    project_id: str
    archive_sha256: str
    files: tuple[tuple[str, bytes], ...]

    @property
    def project(self) -> Project:
        return Project.model_validate(_json(dict(self.files)["project.json"])["project"])

    @property
    def run_count(self) -> int:
        return sum(name.startswith("runs/") and name.endswith("/evidence.json") for name, _ in self.files)

    @property
    def validation(self) -> dict:
        # A draft is archivable; communication remains gated by Runtime validation.
        return validate_project(self.project)


def export_archive(store: Store | ArchiveSnapshot, project: Project) -> bytes:
    """Capture one finite prefix per run and share it across JSON, CSV and HTML."""
    files = {"project.json": _bytes(project_package(project).model_dump(mode="json")),
             "mapping.csv": export_mapping(project).encode("utf-8")}
    if project.scenarios:
        files["scenarios.json"] = _bytes(scenarios_package(project).model_dump(mode="json"))
    # Do not use Store.runs(), which deliberately caps the UI list at 500.
    run_ids = [row[0] for row in store.db.execute("SELECT id,project_json FROM runs ORDER BY started_at,id")
               if _json(row[1].encode())["id"] == project.id]
    for run_id in run_ids:
        run = store.run(run_id)
        prefix = f"runs/{safe_id(run_id)}/"
        files[prefix + "evidence.json"] = "".join(json_stream(store, run_id, run=run)).encode("utf-8")
        files[prefix + "samples.csv"] = "".join(csv_stream(store, run_id, run=run)).encode("utf-8")
        files[prefix + "report.html"] = html_report(store, run_id, run=run).encode("utf-8")
    manifest = {"format": "fat-studio/archive", "version": "1.0", "project_id": project.id,
                "files": [{"path": name, "size": len(content), "sha256": sha256(content).hexdigest()}
                          for name, content in sorted(files.items())]}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr("manifest.json", _bytes(manifest))
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    payload = output.getvalue()
    # The exporter must obey exactly the same bounds as the receiver.
    prepare_archive(payload)
    return payload


def _run(document: dict, project_id: str, run_id: str) -> None:
    required = {"id", "started_at", "ended_at", "project_name", "status", "sample_count", "snapshot",
                "project", "scenario", "result", "connection", "events", "samples", "software_version", "project_sha256"}
    if not isinstance(document, dict) or set(document) != required or document["id"] != run_id:
        raise ValueError("Invalid run evidence fields/identity")
    project = Project.model_validate(document["project"])
    if project.id != project_id or document["project_sha256"] != sha256(encode(document["project"]).encode()).hexdigest():
        raise ValueError("Run project identity/checksum mismatch")
    if document["scenario"] is not None:
        Scenario.model_validate(document["scenario"])
    if (not isinstance(document["status"], str)
            or document["status"] not in {"running", "paused", "stopped", "completed", "error", "interrupted", "idle"}):
        raise ValueError("Invalid archived run status")
    if (not isinstance(document["started_at"], str) or not document["started_at"]
            or document["ended_at"] is not None and not isinstance(document["ended_at"], str)
            or not isinstance(document["project_name"], str) or not isinstance(document["software_version"], str)):
        raise ValueError("Invalid run metadata types")
    result = document["result"]
    if (not isinstance(result, dict) or set(result) != {"verdict", "comment"}
            or not isinstance(result["verdict"], str) or result["verdict"] not in {"pass", "fail", "not_evaluated"}
            or not isinstance(result["comment"], str)):
        raise ValueError("Invalid recorded human result")
    snapshot = document["snapshot"]
    if (not isinstance(snapshot, dict) or set(snapshot) != {"captured_at", "last_sample_id", "last_event_id"}
            or not isinstance(snapshot["captured_at"], str)
            or any(type(snapshot[key]) is not int or snapshot[key] < 0 for key in ("last_sample_id", "last_event_id"))):
        raise ValueError("Invalid finite snapshot boundary")
    if not isinstance(document["connection"], dict) or not isinstance(document["connection"].get("target"), str):
        raise ValueError("Invalid historical connection metadata")
    samples, events = document["samples"], document["events"]
    if (not isinstance(samples, list) or not isinstance(events, list) or type(document["sample_count"]) is not int
            or document["sample_count"] != len(samples)):
        raise ValueError("Invalid sample count")
    tags = {tag.id: tag for tag in project.tags}
    for entries, kind in ((samples, "sample"), (events, "event")):
        last = 0
        for entry in entries:
            fields = ({"id", "run_id", "timestamp", "sim_time_s", "values", "qualities"} if kind == "sample" else
                      {"id", "run_id", "timestamp", "sim_time_s", "kind", "message", "details"})
            if (not isinstance(entry, dict) or set(entry) != fields or type(entry["id"]) is not int
                    or entry["id"] <= last or entry["id"] > snapshot["last_" + kind + "_id"]
                    or entry["run_id"] != run_id or not isinstance(entry["timestamp"], str)
                    or type(entry["sim_time_s"]) not in (int, float) or not 0 <= entry["sim_time_s"] <= 1e15):
                raise ValueError("Invalid " + kind + " identity/boundary/types")
            last = entry["id"]
            if kind == "sample":
                values, qualities = entry["values"], entry["qualities"]
                if (not isinstance(values, dict) or not isinstance(qualities, dict) or set(values) != set(tags)
                        or set(qualities) != set(tags) or any(not isinstance(q, str) for q in qualities.values())):
                    raise ValueError("Sample tag contract mismatch")
                for tag_id, value in values.items():
                    validate_value(tags[tag_id], value, enforce_limits=False)
            elif (not isinstance(entry["kind"], str) or not isinstance(entry["message"], str)
                  or not isinstance(entry["details"], dict)):
                raise ValueError("Invalid event fields")
        if last != snapshot["last_" + kind + "_id"]:
            raise ValueError("Evidence does not reach its declared boundary")


class _FrozenSamples:
    def __init__(self, document: dict):
        self.document = document

    def samples(self, run_id: str, *, through_id=None):
        for sample in self.document["samples"]:
            if sample["run_id"] != run_id or through_id is not None and sample["id"] > through_id:
                raise ValueError("Frozen evidence boundary mismatch")
            yield sample


def prepare_archive(payload: bytes) -> ArchivePlan:
    """Validate the entire container and typed evidence without writing or connecting."""
    if not isinstance(payload, bytes) or len(payload) > MAX_ARCHIVE_BYTES:
        raise ValueError("Archive exceeds compressed size limit")
    files = {}
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_FILES:
                raise ValueError("Archive contains too many files")
            total, seen = 0, set()
            for item in entries:
                name = _name(item.filename)
                mode = (item.external_attr >> 16) & 0o170000
                if (item.is_dir() or item.orig_filename != item.filename or item.flag_bits & 1 or mode not in (0, 0o100000)
                        or name.casefold() in seen or item.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}):
                    raise ValueError("Archive duplicate, link, encryption or unsupported entry")
                seen.add(name.casefold())
                total += item.file_size
                if (item.file_size > MAX_FILE_BYTES or total > MAX_EXPANDED_BYTES
                        or item.file_size > max(1, item.compress_size) * MAX_RATIO):
                    raise ValueError("Archive expansion limit exceeded")
                files[name] = archive.read(item)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, UnicodeError) as exc:
        raise ValueError("Invalid ZIP archive") from exc
    if "manifest.json" not in files:
        raise ValueError("Archive manifest missing")
    manifest = _json(files.pop("manifest.json"))
    if (not isinstance(manifest, dict) or set(manifest) != {"format", "version", "project_id", "files"}
            or manifest["format"] != "fat-studio/archive" or manifest["version"] != "1.0"):
        raise ValueError("Unsupported archive manifest format/version")
    if not isinstance(manifest["project_id"], str):
        raise ValueError("Invalid manifest project identity type")
    project_id = safe_id(manifest["project_id"])
    if not isinstance(manifest["files"], list):
        raise ValueError("Invalid archive manifest file list")
    listed = set()
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or set(entry) != {"path", "size", "sha256"}:
            raise ValueError("Invalid archive manifest entry")
        name = _name(entry["path"])
        if (name in listed or name not in files or type(entry["size"]) is not int
                or entry["size"] != len(files[name]) or entry["sha256"] != sha256(files[name]).hexdigest()):
            raise ValueError("Archive manifest hash/size/list mismatch")
        listed.add(name)
    if listed != set(files) or not {"project.json", "mapping.csv"} <= listed:
        raise ValueError("Archive payload missing or unlisted")
    project_package = _json(files["project.json"])
    if (not isinstance(project_package, dict) or set(project_package) != {"format", "version", "project"}
            or project_package["format"] != "fat-studio/project" or project_package["version"] != "1.0"):
        raise ValueError("Invalid project package")
    project = Project.model_validate(project_package["project"])
    if project.id != project_id:
        raise ValueError("Project/manifest identity mismatch")
    scenarios = _json(files["scenarios.json"]) if "scenarios.json" in files else None
    expected_scenarios = scenarios_package(project).model_dump(mode="json") if project.scenarios else None
    if scenarios != expected_scenarios:
        raise ValueError("Scenario file differs from archived project")
    if files["mapping.csv"] != export_mapping(project).encode("utf-8"):
        raise ValueError("Mapping differs from archived project")
    run_ids = set()
    sample_ids, event_ids = set(), set()
    for name in files:
        if name in {"project.json", "scenarios.json", "mapping.csv"}:
            continue
        match = re.fullmatch(r"runs/([A-Za-z0-9][A-Za-z0-9_-]{0,79})/(evidence\.json|samples\.csv|report\.html)", name)
        if not match:
            raise ValueError("Unexpected archive payload: " + name)
        run_ids.add(match[1])
    for run_id in sorted(run_ids):
        prefix = f"runs/{run_id}/"
        if not all(prefix + name in files for name in ("evidence.json", "samples.csv", "report.html")):
            raise ValueError("Incomplete run export")
        document = _json(files[prefix + "evidence.json"])
        _run(document, project_id, run_id)
        csv = "".join(csv_stream(_FrozenSamples(document), run_id, run=document)).encode("utf-8")
        if csv != files[prefix + "samples.csv"]:
            raise ValueError("CSV differs from the finite JSON evidence")
        # HTML remains a documentary export, never imported as executable UI content.
        report = files[prefix + "report.html"].decode("utf-8")
        if document["project_sha256"] not in report or run_id not in report:
            raise ValueError("HTML report identity differs from JSON evidence")
        for entries, used in ((document["samples"], sample_ids), (document["events"], event_ids)):
            for entry in entries:
                if entry["id"] in used:
                    raise ValueError("Evidence row identity collision")
                used.add(entry["id"])
    return ArchivePlan(payload, project_id, sha256(payload).hexdigest(), tuple(sorted(files.items())))


def restore_archive(store: Store, plan: ArchivePlan) -> Project:
    """Restore into a virgin Store. Publish a staged directory only after closing it."""
    if not isinstance(plan, ArchivePlan):
        raise ValueError("A validated ArchivePlan is required")
    plan = prepare_archive(plan.payload)
    # This boundary avoids cross-database ID collisions and partial merges.
    if (any(store.projects_dir.iterdir()) or store.db.execute("SELECT count(*) FROM runs").fetchone()[0]
            or (store.root / "last-project.json").exists() or (store.root / "machine-policy.json").exists()
            or (store.root / "archive-source.fat.zip").exists()):
        raise ValueError("Restore requires a new empty project directory; existing evidence is never overwritten")
    project = plan.project
    # Historical projects/connections remain evidence only; active credentials are never restored.
    project.plc = PLCConfig(mode="demo", tia_version=project.plc.tia_version,
                            demo_controller=project.plc.demo_controller)
    try:
        with store.db:
            for name, content in plan.files:
                if not name.startswith("runs/") or not name.endswith("/evidence.json"):
                    continue
                run = _json(content)
                status, ended = run["status"], run["ended_at"]
                if ended is None:
                    status, ended = "interrupted", run["snapshot"]["captured_at"]
                store.db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?)", (
                    run["id"], run["started_at"], ended, run["project_name"], encode(run["project"]),
                    encode(run["scenario"]) if run["scenario"] is not None else None, status,
                    encode(run["result"]), encode(run["connection"])))
                store.db.executemany("INSERT INTO samples VALUES (?,?,?,?,?,?)", [(
                    sample["id"], run["id"], sample["timestamp"], sample["sim_time_s"],
                    encode(sample["values"]), encode(sample["qualities"])) for sample in run["samples"]])
                store.db.executemany("INSERT INTO events VALUES (?,?,?,?,?,?,?)", [(
                    event["id"], run["id"], event["timestamp"], event["sim_time_s"], event["kind"],
                    event["message"], encode(event["details"])) for event in run["events"]])
            store.save_project(project)
            (store.root / "archive-source.fat.zip").write_bytes(plan.payload)
    except (OSError, sqlite3.Error, ValueError):
        # The caller owns the unpublished staging directory; do not claim a filesystem transaction.
        raise
    return project
