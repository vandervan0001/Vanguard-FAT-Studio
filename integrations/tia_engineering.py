"""Guarded, interactive TIA engineering CLI using Czarnak's existing MCP server.

No MCP server is implemented here. AI clients use Czarnak in read-only mode.
This human-operated CLI is the only provided path to project writes. Its narrow
allowlist contains no PLC download, online CPU control, or network provisioning.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import difflib
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Protocol
import unicodedata
import uuid

from integrations.tia_versions import SERVER_VERSION, profile, server_environment, validate_server_profile

READ_TOOLS = frozenset({"bind_project", "get_project_status", "browse_project_tree", "plc_read"})
WRITE_TOOLS = frozenset({"archive_project", "plc_write", "compile_check", "save_project"})
MAX_DOCUMENT_BYTES = 500_000


class EngineeringError(RuntimeError):
    """A precondition or upstream operation failed; never automatically retry."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value: str | bytes) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def canonical(path: str | Path, *, must_exist: bool = False) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        raise EngineeringError(f"Absolute path required: {path}")
    return p.resolve(strict=must_exist)


def read_text(path: Path) -> str:
    if path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise EngineeringError(f"Document exceeds {MAX_DOCUMENT_BYTES} bytes: {path}")
    return path.read_bytes().decode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class Policy:
    project_path: str
    sandbox_root: str
    server_executable: str
    backup_root: str
    audit_path: str
    allow_write: bool = False
    schema_version: int = 1
    expected_server_version: str = SERVER_VERSION
    tia_version: str = "V21"

    @classmethod
    def load(cls, path: Path) -> "Policy":
        try:
            value = json.loads(read_text(path))
            policy = cls(**value)
        except (TypeError, ValueError) as exc:
            raise EngineeringError(f"Invalid policy: {exc}") from exc
        policy.validate()
        return policy

    def validate(self) -> None:
        if self.schema_version != 1 or self.expected_server_version != SERVER_VERSION:
            raise EngineeringError("Only policy v1 and the pinned TiaMcpServer 4.3.0 contract are supported.")
        try:
            selected = profile(self.tia_version)
        except ValueError as exc:
            raise EngineeringError(str(exc)) from exc
        if type(self.allow_write) is not bool:
            raise EngineeringError("allow_write must be a JSON boolean.")
        if any(not isinstance(value, str) or not value.strip() for value in (
                self.project_path, self.sandbox_root, self.server_executable, self.backup_root, self.audit_path)):
            raise EngineeringError("All policy paths must be nonempty strings.")
        target = canonical(self.project_path, must_exist=True)
        root = canonical(self.sandbox_root, must_exist=True)
        if target.suffix.lower() != selected.project_suffix or not target.is_file():
            raise EngineeringError(f"An existing standalone {selected.project_suffix} work copy is required for {selected.version}.")
        if not root.is_dir() or len(root.parts) < 3 or not target.is_relative_to(root):
            raise EngineeringError("Project must resolve inside the explicit, dedicated sandbox directory.")
        backup = canonical(self.backup_root)
        if backup.is_relative_to(target.parent):
            raise EngineeringError("Backup directory must be outside the TIA project directory.")
        audit = canonical(self.audit_path)
        if audit.is_relative_to(target.parent) or audit.suffix.lower() != ".jsonl":
            raise EngineeringError("Audit must be a .jsonl file outside the TIA project directory.")
        if audit.exists() and not audit.is_file():
            raise EngineeringError("Audit path must be a regular file.")
        executable = canonical(self.server_executable, must_exist=True)
        if not executable.is_file():
            raise EngineeringError("MCP executable must be an existing local file.")
        try:
            validate_server_profile(executable, self.tia_version)
        except ValueError as exc:
            raise EngineeringError(str(exc)) from exc
        if audit.exists() and (audit.samefile(target) or audit.samefile(executable)):
            raise EngineeringError("Audit must not alias the TIA project or the MCP executable.")

    def require_write(self) -> None:
        self.validate()
        if not self.allow_write:
            raise EngineeringError("Writes disabled. A human must run enable-write from a terminal first.")
        marker = canonical(self.sandbox_root) / ".fat-workcopy.json"
        if not marker.is_file():
            raise EngineeringError("Missing work-copy acknowledgment. Run enable-write interactively.")
        acknowledgment = json.loads(read_text(marker))
        if acknowledgment.get("project_path") != str(canonical(self.project_path)):
            raise EngineeringError("Work-copy acknowledgment does not match the exact project.")
        if (acknowledgment.get("tia_version", "V21") != self.tia_version
                or acknowledgment.get("profile_id", profile("V21").profile_id) != profile(self.tia_version).profile_id):
            raise EngineeringError("Work-copy acknowledgment does not match the selected TIA version and server profile.")


class Audit:
    """Durable append-only-by-application log; not a tamper-proof compliance ledger."""

    def __init__(self, path: Path, project: str, tia_version: str = "V21"):
        self.path = path
        self.project = project
        self.tia_version = tia_version
        try:
            self.profile_id = profile(tia_version).profile_id
        except ValueError as exc:
            raise EngineeringError(str(exc)) from exc

    def require_policy(self, policy: Policy) -> None:
        if (canonical(self.project) != canonical(policy.project_path) or self.tia_version != policy.tia_version
                or self.profile_id != profile(policy.tia_version).profile_id):
            raise EngineeringError("Audit context does not match the selected project and TIA server profile.")

    def record(self, event: str, **detail: Any) -> None:
        row = {
            "timestamp": utc_now(), "event": event, "project_path": self.project,
            "tia_version": self.tia_version, "profile_id": self.profile_id,
            "user": getpass.getuser(), "pid": os.getpid(), **detail,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())


class Console:
    def show(self, text: str) -> None:
        # A reviewed block is untrusted text: terminal escapes must not hide its diff.
        print("".join(f"\\u{ord(c):04x}" if ((ord(c) < 32 and c not in "\n\t")
                    or 127 <= ord(c) <= 159 or unicodedata.category(c) == "Cf") else c for c in text))

    def require_interactive(self) -> None:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise EngineeringError("This operation requires an interactive terminal; piped approvals are refused.")

    def confirm(self, message: str, phrase: str) -> bool:
        self.require_interactive()
        self.show(f"\n{message}\nType exactly: {phrase}")
        try:
            return input("> ") == phrase
        except (EOFError, KeyboardInterrupt):
            return False


class Transport(Protocol):
    async def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


def decode_mcp_result(result: Any) -> dict[str, Any]:
    """MCP SDK v2 exposes snake_case model fields and preserves JSON wire aliases."""
    payload = result.model_dump(mode="json", by_alias=True)
    if payload.get("isError") is True:
        raise EngineeringError("MCP tool rejected the request: " + json.dumps(payload, ensure_ascii=False))
    document = payload.get("structuredContent")
    if document is None:
        texts = [item["text"] for item in payload.get("content", []) if item.get("type") == "text"]
        if len(texts) != 1:
            raise EngineeringError("Expected one canonical structured MCP response.")
        try:
            document = json.loads(texts[0])
        except ValueError as exc:
            raise EngineeringError("MCP result is not a JSON document.") from exc
    if not isinstance(document, dict):
        raise EngineeringError("MCP structured result is not an object.")
    return document


class SdkTransport:
    def __init__(self, client: Any, *, writable: bool):
        self.client = client
        self.writable = writable

    async def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        allowed = READ_TOOLS | (WRITE_TOOLS if self.writable else frozenset())
        if tool not in allowed:
            raise EngineeringError(f"Tool is outside the engineering allowlist: {tool}")
        return decode_mcp_result(await self.client.call_tool(tool, arguments))


@asynccontextmanager
async def connect(policy: Policy, *, writable: bool, console: Console, audit: Audit):
    """Launch the pinned existing server through the official SDK's stdio transport."""
    try:
        from mcp.client import Client
        from mcp.client.stdio import StdioServerParameters
        from mcp import types
    except ImportError as exc:
        raise EngineeringError("Install the optional extra: python -m pip install '.[engineering]'") from exc
    policy.validate()
    audit.require_policy(policy)
    if writable:
        policy.require_write()
        console.require_interactive()

    async def elicit(_context: Any, params: Any) -> Any:
        # The pinned Czarnak lifecycle contract asks exactly one boolean.
        if not writable or getattr(params, "mode", "form") != "form":
            return types.ElicitResult(action="decline")
        schema = params.requested_schema
        properties = schema.get("properties", {})
        if set(properties) != {"confirm"} or properties["confirm"].get("type") != "boolean":
            audit.record("elicitation_rejected", reason="unknown_schema", schema=schema)
            return types.ElicitResult(action="decline")
        accepted = console.confirm(params.message, f"CONFIRM {policy.project_path}")
        audit.record("elicitation", message=params.message, accepted=accepted)
        return types.ElicitResult(action="accept" if accepted else "decline", content={"confirm": accepted})

    args = ["--access-mode", "read-write" if writable else "read-only", "--project", policy.project_path]
    # No shell, no arbitrary CLI tail, no full access mode, no network listener.
    try:
        environment = server_environment(Path(policy.server_executable), policy.tia_version)
    except ValueError as exc:
        raise EngineeringError(str(exc)) from exc
    params = StdioServerParameters(command=policy.server_executable, args=args, env=environment)
    async with Client(params, mode="legacy", read_timeout_seconds=180,
                      elicitation_callback=elicit if writable else None) as client:
        info = client.server_info
        reported = info.version.split("+", 1)[0] if info else ""
        if reported not in {SERVER_VERSION, SERVER_VERSION + ".0"}:
            raise EngineeringError(f"Unexpected server version {reported!r}; expected {SERVER_VERSION}.")
        audit.record("connected", server=info.model_dump(mode="json"), mode=args[1])
        yield SdkTransport(client, writable=writable)


def successful(document: dict[str, Any], tool: str, *, phase: str | None = None) -> dict[str, Any]:
    if document.get("tool") != tool or document.get("success") is not True:
        raise EngineeringError(f"{tool} failed or omitted its result: " + json.dumps(document, ensure_ascii=False))
    expected_contract = "2.0" if tool == "plc_write" else "1.0"
    if document.get("contractVersion") != expected_contract:
        raise EngineeringError(f"Unsupported {tool} response contract; re-audit the integration.")
    if phase and document.get("phase") != phase:
        raise EngineeringError(f"Unexpected {tool} phase: {document.get('phase')!r}")
    if document.get("omission"):
        raise EngineeringError(f"{tool} diagnostics omitted; review full evidence before retrying.")
    return document


def standalone(document: dict[str, Any], tool: str) -> dict[str, Any]:
    successful(document, tool)
    result = document.get("result") or {}
    if result.get("status") != "succeeded" or result.get("omission") or not isinstance(result.get("value"), dict):
        raise EngineeringError(f"Incomplete {tool} standalone result.")
    return result["value"]


def block_content(document: dict[str, Any]) -> dict[str, str]:
    successful(document, "plc_read")
    batch = document.get("batch") or {}
    operations = batch.get("operations", [])
    if len(operations) != 1 or operations[0].get("status") != "succeeded" or operations[0].get("omission"):
        raise EngineeringError("Expected one complete block read; no omitted content is acceptable.")
    value = operations[0].get("result") or {}
    if not isinstance(value.get("content"), str) or not re.fullmatch(r"(?:source|xml):sha256:[0-9a-fA-F]{64}", value.get("contentHash") or ""):
        raise EngineeringError("Block read has no complete content/hash; dependency exports cannot be edited.")
    if len(value["content"].encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise EngineeringError("Block exceeds the local review size limit.")
    return value


@dataclass(frozen=True)
class Proposal:
    project_path: str
    block_path: str
    format: str
    expected_content_hash: str
    before_sha256: str
    created_at: str
    schema_version: int = 1
    server_version: str = SERVER_VERSION
    tia_version: str = "V21"
    profile_id: str = "czarnak-4.3.0-v21"

    @property
    def extension(self) -> str:
        return "xml" if self.format == "xml" else "scl"

    def validate(self) -> None:
        if self.schema_version != 1 or self.server_version != SERVER_VERSION or self.format not in {"source", "xml"}:
            raise EngineeringError("Unsupported proposal schema, format, or server version.")
        try:
            selected = profile(self.tia_version)
        except ValueError as exc:
            raise EngineeringError(str(exc)) from exc
        if self.profile_id != selected.profile_id or canonical(self.project_path).suffix.lower() != selected.project_suffix:
            raise EngineeringError("Proposal does not match its TIA version and server profile.")
        if not self.block_path or len(self.block_path) > 300 or any(ord(c) < 32 for c in self.block_path):
            raise EngineeringError("Invalid PLC block path.")
        if not re.fullmatch(self.format + r":sha256:[0-9a-fA-F]{64}", self.expected_content_hash):
            raise EngineeringError("Invalid expected upstream content hash.")


def require_proposal_policy(proposal: Proposal, policy: Policy) -> None:
    if canonical(proposal.project_path) != canonical(policy.project_path):
        raise EngineeringError("Proposal belongs to another project; import refused.")
    if proposal.tia_version != policy.tia_version or proposal.profile_id != profile(policy.tia_version).profile_id:
        raise EngineeringError("Proposal belongs to another TIA version or server profile; import refused.")


def load_proposal(directory: Path) -> tuple[Proposal, str, str, str]:
    directory = directory.resolve(strict=True)
    try:
        proposal = Proposal(**json.loads(read_text(directory / "proposal.json")))
    except (TypeError, ValueError) as exc:
        raise EngineeringError(f"Invalid proposal: {exc}") from exc
    proposal.validate()
    before_path = directory / f"before.{proposal.extension}"
    after_path = directory / f"after.{proposal.extension}"
    for p in (before_path, after_path):
        if p.is_symlink() or p.resolve(strict=True).parent != directory:
            raise EngineeringError("Proposal content files must remain regular files in their review directory.")
    before, after = read_text(before_path), read_text(after_path)
    if digest(before) != proposal.before_sha256:
        raise EngineeringError("Baseline was modified. Export a fresh proposal from TIA.")
    if not after.strip():
        raise EngineeringError("Empty replacement source is refused.")
    difference = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                            fromfile=f"before/{proposal.block_path}", tofile=f"after/{proposal.block_path}"))
    # Show final newlines explicitly rather than silently hiding a newline-only change.
    if before != after and not difference:
        difference = f"Content bytes differ: {digest(before)} -> {digest(after)}\n"
    return proposal, before, after, difference


class Engineering:
    def __init__(self, policy: Policy, transport: Transport, audit: Audit, console: Console):
        audit.require_policy(policy)
        self.policy, self.transport, self.audit, self.console = policy, transport, audit, console

    async def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool not in READ_TOOLS | WRITE_TOOLS:
            raise EngineeringError("Tool is not allowed.")
        if tool in WRITE_TOOLS:
            self.policy.require_write()
        call_id = uuid.uuid4().hex
        self.audit.record("call_started", call_id=call_id, tool=tool, arguments=arguments)
        try:
            result = await self.transport.call(tool, arguments)
        except BaseException as exc:
            self.audit.record("call_failed", call_id=call_id, tool=tool, error=str(exc))
            raise
        self.audit.record("call_finished", call_id=call_id, tool=tool, result=result)
        return result

    async def verify_target(self, *, saved: bool = False) -> dict[str, Any]:
        self.policy.validate()
        bound = standalone(await self.call("bind_project", {"projectPath": self.policy.project_path}), "bind_project")
        binding = bound.get("binding") or {}
        if binding.get("state") != "verified" or canonical(binding.get("projectPath") or "") != canonical(self.policy.project_path):
            raise EngineeringError("Upstream binding does not match the exact work copy.")
        status = standalone(await self.call("get_project_status", {}), "get_project_status")
        if status.get("isOpen") is not True or canonical(status.get("path") or "") != canonical(self.policy.project_path):
            raise EngineeringError("TIA is not attached to the exact work copy.")
        if status.get("context") is not None:
            raise EngineeringError("Multiuser/server projects are outside this standalone-work-copy workflow.")
        if saved and status.get("isModified") is not False:
            raise EngineeringError("Save the work copy in TIA before this operation, then retry. Unsaved state is not archived.")
        return status

    async def read_block(self, path: str, format: str) -> dict[str, str]:
        result = await self.call("plc_read", {"operations": [{
            "operationId": "fat-read", "operation": "get_block_content", "blockPath": path,
            "format": format, "withDependencies": False,
        }]})
        value = block_content(result)
        if value.get("format") != format:
            raise EngineeringError("Upstream returned a different export format.")
        return value

    async def tree(self) -> dict[str, Any]:
        """Drain v3 pages before closing stdio: upstream cursors are process-local."""
        await self.verify_target()
        arguments: dict[str, Any] = {"pageSize": 100}
        snapshot = query = None
        nodes: list[dict[str, Any]] = []
        warnings: list[Any] = []
        seen_cursors: set[str] = set()
        seen_nodes: set[str] = set()
        pages = 0
        while True:
            document = await self.call("browse_project_tree", arguments)
            value = document.get("result")
            if (document.get("contractVersion") != "3.0" or document.get("status") != "succeeded" or document.get("failure")
                    or not isinstance(value, dict)):
                raise EngineeringError("Project tree failed: " + json.dumps(document, ensure_ascii=False))
            current_snapshot, current_query = value.get("snapshot"), value.get("query")
            pagination, page_nodes = value.get("pagination"), value.get("nodes")
            if (not isinstance(current_snapshot, dict) or not current_snapshot.get("snapshotId")
                    or type(current_snapshot.get("totalNodes")) is not int
                    or current_snapshot["totalNodes"] < 0 or not isinstance(current_query, dict)
                    or not isinstance(pagination, dict) or not isinstance(page_nodes, list)
                    or type(pagination.get("offset")) is not int or pagination["offset"] != len(nodes)
                    or type(pagination.get("returnedCount")) is not int
                    or pagination["returnedCount"] != len(page_nodes)):
                raise EngineeringError("Project tree returned incomplete or out-of-order page metadata.")
            if snapshot is None:
                snapshot, query = current_snapshot, current_query
                if not isinstance(query.get("projectPath"), str) or canonical(query["projectPath"]) != canonical(self.policy.project_path):
                    raise EngineeringError("Project tree belongs to another project.")
            elif (current_snapshot.get("snapshotId") != snapshot["snapshotId"]
                  or current_snapshot["totalNodes"] != snapshot["totalNodes"] or current_query != query):
                raise EngineeringError("Project tree snapshot changed during pagination; start a fresh read.")
            for node in page_nodes:
                if (not isinstance(node, dict) or not isinstance(node.get("nodeId"), str)
                        or not node["nodeId"] or node["nodeId"] in seen_nodes
                        or type(node.get("sequence")) is not int or node["sequence"] != len(nodes)
                        or (node.get("parentNodeId") is not None and node["parentNodeId"] not in seen_nodes)):
                    raise EngineeringError("Project tree contains an invalid or duplicated node.")
                seen_nodes.add(node["nodeId"])
                nodes.append(node)
            if len(nodes) > snapshot["totalNodes"]:
                raise EngineeringError("Project tree contains more nodes than its snapshot.")
            page_warnings = document.get("warnings", [])
            if not isinstance(page_warnings, list):
                raise EngineeringError("Project tree returned malformed warnings.")
            warnings.extend(page_warnings)
            pages += 1
            cursor = pagination.get("nextCursor")
            if cursor is None:
                if len(nodes) != snapshot["totalNodes"]:
                    raise EngineeringError("Project tree stopped before the complete snapshot was read.")
                break
            if not isinstance(cursor, str) or not cursor or cursor in seen_cursors or not page_nodes:
                raise EngineeringError("Project tree cursor did not make progress.")
            seen_cursors.add(cursor)
            arguments = {"cursor": cursor}
        return {"status": "succeeded", "snapshot": snapshot, "query": query,
                "nodes": nodes, "pages": pages, "warnings": warnings}

    async def export(self, path: str, format: str, directory: Path) -> Path:
        await self.verify_target()
        value = await self.read_block(path, format)
        proposal = Proposal(str(canonical(self.policy.project_path)), path, format,
                            value["contentHash"], digest(value["content"]), utc_now(),
                            tia_version=self.policy.tia_version, profile_id=profile(self.policy.tia_version).profile_id)
        proposal.validate()
        directory.mkdir(parents=True, exist_ok=False)
        for name in ("before", "after"):
            (directory / f"{name}.{proposal.extension}").write_bytes(value["content"].encode("utf-8"))
        write_json(directory / "proposal.json", asdict(proposal))
        self.audit.record("proposal_exported", directory=str(directory.resolve()), proposal=asdict(proposal))
        return directory

    async def archive(self) -> Path:
        await self.verify_target(saved=True)
        root = canonical(self.policy.backup_root)
        root.mkdir(parents=True, exist_ok=True)
        name = "fat-before-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:10]
        target = root / (name + profile(self.policy.tia_version).archive_suffix)
        arguments = {"archiveDirectory": str(root), "archiveName": name, "mode": "Compressed", "saveBeforeArchive": False}
        successful(await self.call("archive_project", {**arguments, "dryRun": True}), "archive_project", phase="preview")
        result = successful(await self.call("archive_project", {**arguments, "dryRun": False}), "archive_project", phase="applied")
        standalone(result, "archive_project")
        if not target.is_file() or target.stat().st_size == 0:
            raise EngineeringError("TIA did not produce the expected nonempty archive; import refused.")
        sha = hashlib.sha256()
        with target.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                sha.update(chunk)
        self.audit.record("backup_verified", path=str(target), size=target.stat().st_size, sha256=sha.hexdigest())
        return target

    async def apply(self, directory: Path) -> dict[str, Any]:
        self.policy.require_write()
        self.console.require_interactive()
        proposal, before, after, difference = load_proposal(directory)
        require_proposal_policy(proposal, self.policy)
        if before == after:
            raise EngineeringError("Proposal has no changes.")
        await self.verify_target(saved=True)
        current = await self.read_block(proposal.block_path, proposal.format)
        if current["contentHash"] != proposal.expected_content_hash or digest(current["content"]) != proposal.before_sha256:
            raise EngineeringError("TIA source changed since export. Create a new proposal; no overwrite occurred.")
        operation = {"operationId": "fat-update", "operation": "update_block_logic", "blockPath": proposal.block_path,
                     "format": proposal.format, "content": after, "expectedContentHash": proposal.expected_content_hash}
        preview = successful(await self.call("plc_write", {"operations": [operation], "dryRun": True}), "plc_write", phase="preview")
        if any(g.get("severity") == "block" for g in preview.get("guards", [])):
            raise EngineeringError("Upstream preview contains a blocking guard.")
        (directory / "change.diff").write_text(difference, encoding="utf-8", newline="\n")
        write_json(directory / "preview.json", preview)
        self.console.show(difference)
        self.console.show(json.dumps(preview, ensure_ascii=False, indent=2))
        review_hash = digest(after)[:12]
        accepted = self.console.confirm(
            f"Work copy: {self.policy.project_path}\nBlock: {proposal.block_path}\n"
            "Approve archive, this exact import, and any compile/read-back performed by TIA during the import. "
            "No CPU command is issued. Full PLC compilation and saving are confirmed separately.",
            f"APPLY {self.policy.project_path} {review_hash}",
        )
        self.audit.record("import_approval", accepted=accepted, block=proposal.block_path,
                          after_sha256=digest(after), diff_sha256=digest(difference))
        if not accepted:
            return {"status": "rejected", "project_changed": False}
        backup = await self.archive()
        await self.verify_target(saved=True)
        latest = await self.read_block(proposal.block_path, proposal.format)
        if latest["contentHash"] != proposal.expected_content_hash or digest(latest["content"]) != proposal.before_sha256:
            raise EngineeringError("Source changed after approval/archive; import refused.")
        receipt: dict[str, Any] = {"backup": str(backup), "project": self.policy.project_path,
                                  "tia_version": self.policy.tia_version, "profile_id": profile(self.policy.tia_version).profile_id,
                                  "block": proposal.block_path, "approved_sha256": digest(after), "timestamp": utc_now()}
        try:
            imported = await self.call("plc_write", {"operations": [operation], "dryRun": False})
            receipt["import"] = imported
            successful(imported, "plc_write", phase="applied")
            verification = imported.get("verification") or {}
            if verification.get("success") is not True or verification.get("omission"):
                raise EngineeringError("Import verification failed; the work copy may already have changed.")
            receipt["status"] = "imported_in_memory"
            receipt["compile"] = await self.compile(archive_first=False)
            if receipt["compile"].get("status") == "passed":
                saved = self.console.confirm("Compilation completed. Save this work copy?", f"SAVE {self.policy.project_path}")
                self.audit.record("save_approval", accepted=saved)
                if saved:
                    await self.verify_target()
                    receipt["save"] = successful(await self.call("save_project", {"dryRun": False}), "save_project", phase="applied")
                    standalone(receipt["save"], "save_project")
                    receipt["status"] = "saved_and_compiled"
            else:
                receipt["status"] = "imported_compile_" + receipt["compile"]["status"]
        except BaseException as exc:
            receipt["status"] = "inspect_before_retry"
            receipt["error"] = str(exc)
            raise
        finally:
            write_json(directory / "receipt.json", receipt)
            self.audit.record("apply_finished", receipt=receipt)
        return receipt

    async def compile(self, *, archive_first: bool = True) -> dict[str, Any]:
        self.policy.require_write()
        self.console.require_interactive()
        await self.verify_target(saved=archive_first)
        accepted = self.console.confirm("Compile all PLC software in this exact work copy?", f"COMPILE {self.policy.project_path}")
        self.audit.record("compile_approval", accepted=accepted)
        if not accepted:
            return {"status": "declined"}
        backup = await self.archive() if archive_first else None
        await self.verify_target()
        document = await self.call("compile_check", {})
        # Compiler errors can be MCP isError:false + document.success:false.
        envelope = document.get("result")
        report = envelope.get("value") if isinstance(envelope, dict) else None
        if (document.get("tool") != "compile_check" or document.get("contractVersion") != "1.0"
                or not isinstance(report, dict) or document.get("omission") or envelope.get("omission")
                or envelope.get("status") not in {"succeeded", "failed"}
                or type(report.get("totalErrorCount")) is not int or report["totalErrorCount"] < 0
                or type(report.get("totalWarningCount")) is not int or report["totalWarningCount"] < 0):
            raise EngineeringError("Compilation returned no complete diagnostic report.")
        if document.get("success") is True and (envelope["status"] != "succeeded" or envelope.get("failure")
                                               or document.get("error")):
            raise EngineeringError("Compilation returned contradictory diagnostic status.")
        plcs = report.get("plcs")
        if not isinstance(plcs, list) or (document.get("success") is True and not plcs):
            raise EngineeringError("Compilation returned no PLC diagnostics.")
        for plc in plcs:
            if (not isinstance(plc, dict) or type(plc.get("errorCount")) is not int or plc["errorCount"] < 0
                    or type(plc.get("warningCount")) is not int or plc["warningCount"] < 0
                    or not isinstance(plc.get("state"), str)):
                raise EngineeringError("Compilation returned invalid PLC diagnostic counters.")
        if (sum(plc["errorCount"] for plc in plcs) != report["totalErrorCount"]
                or sum(plc["warningCount"] for plc in plcs) != report["totalWarningCount"]
                or (document.get("success") is True and any(plc["state"] not in {"Success", "Warning"} for plc in plcs))):
            raise EngineeringError("Compilation returned contradictory PLC diagnostics.")
        passed = (document.get("success") is True and report.get("totalErrorCount") == 0
                  and report.get("overallState") in {"Success", "Warning"})
        result = {"status": "passed" if passed else "failed", "diagnostics": document, "backup": str(backup) if backup else None}
        self.console.show(json.dumps(result, ensure_ascii=False, indent=2))
        self.audit.record("compile_finished", result=result)
        return result


def configure(args: argparse.Namespace) -> None:
    location = canonical(args.config)
    if location.exists():
        raise EngineeringError("Configuration already exists; refusing to replace it.")
    policy = Policy(str(canonical(args.project, must_exist=True)), str(canonical(args.sandbox_root, must_exist=True)),
                    str(canonical(args.server, must_exist=True)), str(location.parent / "backups"), str(location.parent / "audit.jsonl"),
                    tia_version=args.tia_version)
    policy.validate()
    try:
        environment = server_environment(Path(policy.server_executable), policy.tia_version)
    except ValueError as exc:
        raise EngineeringError(str(exc)) from exc
    write_json(location, asdict(policy))
    server = {"command": policy.server_executable,
              "args": ["--access-mode", "read-only", "--project", policy.project_path], "env": environment}
    name = "tia-fat-" + policy.tia_version.lower() + "-readonly"
    claude_path = location.parent / f"claude.{policy.tia_version.lower()}.mcp.json"
    codex_path = location.parent / f"codex.{policy.tia_version.lower()}.mcp.toml"
    write_json(claude_path, {"mcpServers": {name: server}})
    toml = f'[mcp_servers.{name}]\ncommand = ' + json.dumps(server["command"]) + '\nargs = ' + json.dumps(server["args"]) + '\n'
    toml += f'\n[mcp_servers.{name}.env]\n' + ''.join(key + ' = ' + json.dumps(value) + '\n' for key, value in environment.items())
    codex_path.write_text(toml, encoding="utf-8", newline="\n")
    print(f"Configured {policy.tia_version} read-only work copy. Policy: {location}")
    print(f"Use a separate --config directory for each TIA version. MCP server name: {name}.")
    print(f"Claude fragment: {claude_path}\nCodex fragment: {codex_path}")
    print("Sources sent by your AI client may leave this PC when its model is hosted. Follow your organization's policy.")


async def run_command(args: argparse.Namespace) -> int:
    if args.command == "configure":
        configure(args)
        return 0
    policy = Policy.load(Path(args.config))
    audit = Audit(Path(policy.audit_path), policy.project_path, policy.tia_version)
    console = Console()
    if args.command in {"enable-write", "disable-write"}:
        enable = args.command == "enable-write"
        accepted = not enable or console.confirm(
            "Confirm this is a disposable development COPY, isolated from production. "
            "This enables only the interactive CLI; AI MCP configuration remains read-only.",
            f"SANDBOX {policy.project_path}",
        )
        audit.record("write_mode_request", enable=enable, accepted=accepted)
        if not accepted:
            return 2
        if enable:
            write_json(canonical(policy.sandbox_root) / ".fat-workcopy.json",
                       {"project_path": str(canonical(policy.project_path)), "tia_version": policy.tia_version,
                        "profile_id": profile(policy.tia_version).profile_id, "acknowledged_at": utc_now(), "user": getpass.getuser()})
        write_json(Path(args.config), {**asdict(policy), "allow_write": enable})
        print("Interactive engineering writes " + ("enabled." if enable else "disabled."))
        return 0
    if args.command == "diff":
        proposal, before, after, diff = load_proposal(Path(args.proposal))
        require_proposal_policy(proposal, policy)
        (Path(args.proposal) / "change.diff").write_text(diff, encoding="utf-8", newline="\n")
        console.show(diff or "No changes.")
        audit.record("diff_reviewed", proposal=str(args.proposal), before_sha256=digest(before), after_sha256=digest(after))
        return 0
    if args.command == "apply":
        proposal, _, _, _ = load_proposal(Path(args.proposal))
        require_proposal_policy(proposal, policy)
    writable = args.command in {"apply", "compile"}
    async with connect(policy, writable=writable, console=console, audit=audit) as transport:
        engineer = Engineering(policy, transport, audit, console)
        if args.command == "status":
            result = await engineer.verify_target()
        elif args.command == "tree":
            if args.cursor:
                raise EngineeringError("Tree cursors are process-local. Run tree without --cursor; it now reads every page in one session.")
            result = await engineer.tree()
        elif args.command == "tags":
            await engineer.verify_target()
            operation = {"operationId": "fat-tags", "operation": "list_tag_tables"}
            if args.plc:
                operation["plcName"] = args.plc
            result = await engineer.call("plc_read", {"operations": [operation]})
        elif args.command == "export":
            result = {"proposal": str(await engineer.export(args.block, args.format, Path(args.output)))}
        elif args.command == "apply":
            result = await engineer.apply(Path(args.proposal))
        else:
            result = await engineer.compile()
        console.show(json.dumps(result, ensure_ascii=False, indent=2))
        failed = (isinstance(result, dict) and (result.get("success") is False or result.get("status")
                  in {"failed", "imported_compile_failed", "imported_compile_declined", "inspect_before_retry"}))
        return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path.cwd() / ".local" / "tia" / "policy.json"))
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("configure", help="Create read-only policy and Claude/Codex configuration snippets.")
    setup.add_argument("--project", required=True)
    setup.add_argument("--sandbox-root", required=True)
    setup.add_argument("--server", required=True)
    setup.add_argument("--tia-version", choices=["V20", "V21"], default="V21")
    for name in ("status", "enable-write", "disable-write", "compile"):
        commands.add_parser(name)
    tree = commands.add_parser("tree")
    tree.add_argument("--cursor")
    tags = commands.add_parser("tags")
    tags.add_argument("--plc")
    export = commands.add_parser("export")
    export.add_argument("--block", required=True)
    export.add_argument("--format", choices=["source", "xml"], default="source")
    export.add_argument("--output", required=True)
    for name in ("diff", "apply"):
        sub = commands.add_parser(name)
        sub.add_argument("--proposal", required=True)
    try:
        return asyncio.run(run_command(parser.parse_args()))
    except (EngineeringError, OSError, ValueError) as exc:
        print(f"Engineering stopped: {exc}", file=sys.stderr)
        return 1
    except ExceptionGroup as exc:
        def leaves(group):
            for item in group.exceptions:
                if isinstance(item, ExceptionGroup):
                    yield from leaves(item)
                else:
                    yield str(item)
        print("Engineering transport stopped: " + "; ".join(leaves(exc)), file=sys.stderr)
        print("Inspect the audit and TIA state before retrying any interrupted write.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelled. Inspect TIA state before retrying any interrupted write.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
