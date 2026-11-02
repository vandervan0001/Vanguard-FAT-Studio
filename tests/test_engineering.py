"""Safety and contract tests for the separate TIA engineering workflow.

These do not establish compatibility with installed Siemens software.
"""

import asyncio
import argparse
from contextlib import asynccontextmanager
from dataclasses import replace
import json
from pathlib import Path
import sys

import pytest

from integrations.tia_engineering import (
    Audit, Console, Engineering, EngineeringError, Policy, SdkTransport,
    digest, load_proposal, write_json,
)
import integrations.tia_engineering as engineering_module


def standalone(tool, value, *, success=True, phase=None):
    result = {"tool": tool, "contractVersion": "1.0", "success": success,
              "result": {"status": "succeeded" if success else "failed", "value": value, "omission": None}}
    if phase:
        result["phase"] = phase
    return result


class FakeConsole(Console):
    def __init__(self, approvals=(), interactive=True):
        self.approvals = list(approvals)
        self.interactive = interactive
        self.shown = []

    def show(self, text):
        self.shown.append(text)

    def require_interactive(self):
        if not self.interactive:
            raise EngineeringError("Interactive terminal required.")

    def confirm(self, message, phrase):
        self.require_interactive()
        self.shown.append((message, phrase))
        return self.approvals.pop(0) if self.approvals else False


class FakeTransport:
    def __init__(self, policy):
        self.policy = policy
        self.content = "FUNCTION Test : Void\nBEGIN\n    #value := 1;\nEND_FUNCTION\n"
        self.modified = False
        self.calls = []
        self.target = policy.project_path
        self.fail_compile = False
        self.create_archive = True
        self.drift_after_archive = False

    async def call(self, tool, arguments):
        self.calls.append((tool, arguments))
        if tool == "bind_project":
            return standalone(tool, {"binding": {"state": "verified", "projectPath": self.target}})
        if tool == "get_project_status":
            return standalone(tool, {"isOpen": True, "path": self.target, "isModified": self.modified})
        if tool == "plc_read":
            operation = arguments["operations"][0]
            format = operation.get("format", "source")
            return {"tool": tool, "contractVersion": "1.0", "success": True, "batch": {"operations": [{
                "status": "succeeded", "result": {"format": format, "content": self.content,
                "contentHash": format + ":sha256:" + digest(self.content)}, "omission": None,
            }]}}
        if tool == "archive_project":
            if not arguments["dryRun"]:
                if self.create_archive:
                    target = Path(arguments["archiveDirectory"]) / (arguments["archiveName"] + ".zap21")
                    target.write_bytes(b"fake TIA archive for workflow test only")
                if self.drift_after_archive:
                    self.content += "// another engineer saved a change\n"
            return standalone(tool, {"archivePath": arguments["archiveDirectory"]},
                              phase="preview" if arguments["dryRun"] else "applied")
        if tool == "plc_write":
            if not arguments["dryRun"]:
                operation = arguments["operations"][0]
                assert operation["expectedContentHash"] == operation["format"] + ":sha256:" + digest(self.content)
                self.content = operation["content"]
                self.modified = True
            return {"tool": tool, "contractVersion": "2.0", "success": True,
                    "phase": "preview" if arguments["dryRun"] else "applied", "guards": [],
                    "verification": {"success": True}}
        if tool == "compile_check":
            return standalone(tool, {"totalErrorCount": int(self.fail_compile), "totalWarningCount": 0,
                              "overallState": "Error" if self.fail_compile else "Success", "plcs": [{
                                  "plcName": "PLC_1", "deviceName": None,
                                  "state": "Error" if self.fail_compile else "Success",
                                  "errorCount": int(self.fail_compile), "warningCount": 0,
                                  "messages": [], "diagnosticNotes": []}]},
                              success=not self.fail_compile)
        if tool == "save_project":
            self.modified = False
            return standalone(tool, {"saved": True}, phase="applied")
        raise AssertionError("Unexpected tool: " + tool)


@pytest.fixture
def policy(tmp_path):
    sandbox = tmp_path / "sandbox"
    project_directory = sandbox / "UnitCopy"
    project_directory.mkdir(parents=True)
    project = project_directory / "UnitCopy.ap21"
    project.write_bytes(b"fake TIA project for workflow test only")
    server = tmp_path / "tia-mcp.exe"
    server.write_bytes(b"not executed in unit tests")
    policy = Policy(str(project), str(sandbox), str(server), str(tmp_path / "backups"), str(tmp_path / "audit.jsonl"))
    policy.validate()
    return policy


def writable(policy):
    write_json(Path(policy.sandbox_root) / ".fat-workcopy.json", {"project_path": policy.project_path})
    return replace(policy, allow_write=True)


def engine(policy, console=None):
    fake = FakeTransport(policy)
    engineer = Engineering(policy, fake, Audit(Path(policy.audit_path), policy.project_path), console or FakeConsole())
    return engineer, fake


async def proposal(engineer, tmp_path):
    directory = tmp_path / "proposal"
    await engineer.export("PLC_1/Test", "source", directory)
    after = directory / "after.scl"
    after.write_text(after.read_text().replace(":= 1", ":= 2"), encoding="utf-8")
    return directory


def actual_writes(fake):
    return [(tool, args) for tool, args in fake.calls if tool in {"archive_project", "plc_write", "save_project"}
            and args.get("dryRun") is not True]


def test_read_only_default_refuses_before_contact(policy, tmp_path):
    engineer, fake = engine(policy)
    with pytest.raises(EngineeringError, match="disabled"):
        asyncio.run(engineer.apply(tmp_path))
    assert fake.calls == []


def test_sandbox_and_archive_paths_cannot_escape(policy, tmp_path):
    (tmp_path / "backups").mkdir()
    with pytest.raises(EngineeringError, match="inside"):
        replace(policy, sandbox_root=str(tmp_path / "backups")).validate()


def test_backup_cannot_be_inside_tia_project(policy):
    with pytest.raises(EngineeringError, match="outside"):
        replace(policy, backup_root=str(Path(policy.project_path).parent / "backups")).validate()


def test_export_proposal_preserves_server_hash_and_diff(policy, tmp_path):
    engineer, fake = engine(policy)
    directory = asyncio.run(proposal(engineer, tmp_path))
    manifest, before, after, difference = load_proposal(directory)
    assert manifest.expected_content_hash == "source:sha256:" + digest(before)
    assert "-    #value := 1" in difference and "+    #value := 2" in difference
    assert actual_writes(fake) == []


def test_changed_baseline_is_rejected(policy, tmp_path):
    engineer, _ = engine(policy)
    directory = asyncio.run(proposal(engineer, tmp_path))
    (directory / "before.scl").write_text("tampered", encoding="utf-8")
    with pytest.raises(EngineeringError, match="Baseline was modified"):
        load_proposal(directory)


def test_deny_confirmation_leaves_tia_untouched(policy, tmp_path):
    engineer, fake = engine(writable(policy), FakeConsole([False]))
    directory = asyncio.run(proposal(engineer, tmp_path))
    original = fake.content
    result = asyncio.run(engineer.apply(directory))
    assert result["status"] == "rejected" and fake.content == original
    assert actual_writes(fake) == []


def test_success_archives_before_import_compiles_and_saves(policy, tmp_path):
    engineer, fake = engine(writable(policy), FakeConsole([True, True, True]))
    directory = asyncio.run(proposal(engineer, tmp_path))
    result = asyncio.run(engineer.apply(directory))
    writes = actual_writes(fake)
    assert [tool for tool, _ in writes] == ["archive_project", "plc_write", "save_project"]
    assert writes[0][1]["saveBeforeArchive"] is False
    assert result["status"] == "saved_and_compiled"
    assert Path(result["backup"]).stat().st_size > 0
    assert "#value := 2" in fake.content
    assert json.loads((directory / "receipt.json").read_text())["compile"]["status"] == "passed"
    audit = [json.loads(line) for line in Path(policy.audit_path).read_text().splitlines()]
    assert any(row["event"] == "backup_verified" and len(row["sha256"]) == 64 for row in audit)
    assert all(tool in {"bind_project", "get_project_status", "plc_read", "plc_write", "archive_project", "compile_check", "save_project"}
               for tool, _ in fake.calls)


@pytest.mark.parametrize("after_archive", [False, True])
def test_stale_source_never_imports(policy, tmp_path, after_archive):
    engineer, fake = engine(writable(policy), FakeConsole([True]))
    directory = asyncio.run(proposal(engineer, tmp_path))
    if after_archive:
        fake.drift_after_archive = True
    else:
        fake.content += "// saved elsewhere\n"
    with pytest.raises(EngineeringError, match="changed"):
        asyncio.run(engineer.apply(directory))
    assert all(tool != "plc_write" for tool, _ in actual_writes(fake))


def test_missing_archive_stops_import(policy, tmp_path):
    engineer, fake = engine(writable(policy), FakeConsole([True]))
    directory = asyncio.run(proposal(engineer, tmp_path))
    fake.create_archive = False
    with pytest.raises(EngineeringError, match="archive"):
        asyncio.run(engineer.apply(directory))
    assert all(tool != "plc_write" for tool, _ in actual_writes(fake))


def test_compile_errors_preserved_and_never_saved(policy, tmp_path):
    engineer, fake = engine(writable(policy), FakeConsole([True, True, True]))
    directory = asyncio.run(proposal(engineer, tmp_path))
    fake.fail_compile = True
    result = asyncio.run(engineer.apply(directory))
    assert result["status"] == "imported_compile_failed"
    assert result["compile"]["diagnostics"]["result"]["value"]["totalErrorCount"] == 1
    assert all(tool != "save_project" for tool, _ in fake.calls)


def test_noninteractive_write_refused(policy, tmp_path):
    engineer, fake = engine(writable(policy), FakeConsole(interactive=False))
    with pytest.raises(EngineeringError, match="Interactive"):
        asyncio.run(engineer.apply(tmp_path))
    assert fake.calls == []


def test_wrong_target_refused_without_write(policy, tmp_path):
    engineer, fake = engine(writable(policy), FakeConsole([True]))
    directory = asyncio.run(proposal(engineer, tmp_path))
    fake.target = str(tmp_path / "Original.ap21")
    with pytest.raises(EngineeringError, match="exact work copy"):
        asyncio.run(engineer.apply(directory))
    assert actual_writes(fake) == []


def test_unsaved_workcopy_refused(policy, tmp_path):
    engineer, fake = engine(writable(policy), FakeConsole([True]))
    directory = asyncio.run(proposal(engineer, tmp_path))
    fake.modified = True
    with pytest.raises(EngineeringError, match="Save the work copy"):
        asyncio.run(engineer.apply(directory))
    assert actual_writes(fake) == []


def test_sdk_transport_blocks_cpu_and_readonly_write():
    transport = SdkTransport(None, writable=False)
    for tool in ("download", "run_cpu", "stop_cpu", "network_write", "plc_write"):
        with pytest.raises(EngineeringError, match="allowlist"):
            asyncio.run(transport.call(tool, {}))


def test_real_official_sdk_stdio_roundtrip(tmp_path):
    """A real stdio subprocess, using SDK on both ends; the server is a test double."""
    pytest.importorskip("mcp", reason="Install engineering extra to exercise official MCP stdio transport")
    from mcp.client import Client
    from mcp.client.stdio import StdioServerParameters
    script = tmp_path / "fake_server.py"
    script.write_text('''from mcp.server.mcpserver import MCPServer
server = MCPServer("TIA-contract-test-double", version="4.3.0")
@server.tool()
def get_project_status() -> dict:
    return {"tool": "get_project_status", "contractVersion": "1.0", "success": True,
            "result": {"status": "succeeded", "value": {"isOpen": True, "path": "test-only.ap21"}}}
server.run()
''', encoding="utf-8")

    async def exercise():
        # Carry only PYTHONPATH for the temporary SDK install used during development.
        import os
        env = {"PYTHONPATH": os.environ.get("PYTHONPATH", "")}
        async with Client(StdioServerParameters(command=sys.executable, args=[str(script)], env=env),
                          mode="legacy", read_timeout_seconds=10) as client:
            assert client.server_info.version == "4.3.0"
            transport = SdkTransport(client, writable=False)
            result = await transport.call("get_project_status", {})
            assert result["success"] is True and result["result"]["value"]["isOpen"] is True
    asyncio.run(exercise())


def test_readonly_policy_cannot_append_audit_into_tia_project(policy):
    """Even a status request records an audit row; its path must not corrupt TIA files."""
    with pytest.raises(EngineeringError, match="audit|Audit"):
        replace(policy, audit_path=policy.project_path).validate()


def test_tree_collects_pages_within_one_server_session(policy, tmp_path, monkeypatch):
    """Czarnak v4.3.0 tree cursors are process-local, so separate CLI calls cannot resume them."""
    config = tmp_path / "policy.json"
    write_json(config, policy.__dict__)
    console = FakeConsole()
    transports = []

    class TreeTransport(FakeTransport):
        async def call(self, tool, arguments):
            if tool != "browse_project_tree":
                return await super().call(tool, arguments)
            self.calls.append((tool, arguments))
            offset = 1 if arguments.get("cursor") == "same-process-page-2" else 0
            return {
                "contractVersion": "3.0", "status": "succeeded", "failure": None, "warnings": [],
                "result": {
                    "snapshot": {"snapshotId": "one-snapshot", "totalNodes": 2},
                    "query": {"projectPath": policy.project_path},
                    "pagination": {"offset": offset, "requestedPageSize": 100, "returnedCount": 1,
                                   "nextCursor": "same-process-page-2" if offset == 0 else None},
                    "nodes": [{"nodeId": f"n{offset}", "parentNodeId": None if offset == 0 else "n0",
                               "sequence": offset, "name": "PLC_1" if offset == 0 else "Main"}],
                },
            }

    @asynccontextmanager
    async def connection(*args, **kwargs):
        transport = TreeTransport(policy)
        transports.append(transport)
        yield transport

    monkeypatch.setattr(engineering_module, "connect", connection)
    monkeypatch.setattr(engineering_module, "Console", lambda: console)
    code = asyncio.run(engineering_module.run_command(argparse.Namespace(config=str(config), command="tree", cursor=None)))
    assert code == 0 and len(transports) == 1
    result = json.loads(console.shown[-1])
    assert [node["name"] for node in result["nodes"]] == ["PLC_1", "Main"]
    assert result["pages"] == 2
    tree_calls = [args for tool, args in transports[0].calls if tool == "browse_project_tree"]
    assert tree_calls == [{"pageSize": 100}, {"cursor": "same-process-page-2"}]


def test_tree_v3_failure_is_not_a_successful_cli_exit(policy, tmp_path, monkeypatch):
    config = tmp_path / "policy.json"
    write_json(config, policy.__dict__)

    class BrokenTree(FakeTransport):
        async def call(self, tool, arguments):
            if tool == "browse_project_tree":
                return {"contractVersion": "3.0", "status": "failed", "result": None,
                        "failure": {"category": "snapshot_unavailable", "message": "Snapshot expired"}, "warnings": []}
            return await super().call(tool, arguments)

    @asynccontextmanager
    async def connection(*args, **kwargs):
        yield BrokenTree(policy)

    monkeypatch.setattr(engineering_module, "connect", connection)
    monkeypatch.setattr(engineering_module, "Console", FakeConsole)
    monkeypatch.setattr(sys, "argv", ["fat-tia", "--config", str(config), "tree"])
    assert engineering_module.main() == 1


@pytest.mark.parametrize("damage", ["omitted", "wrong_status", "boolean_count", "hidden_plc_error", "empty_plcs"])
def test_compile_incomplete_or_malformed_result_is_not_passed(policy, damage):
    engineer, fake = engine(writable(policy), FakeConsole([True]))
    original_call = fake.call

    async def call(tool, arguments):
        result = await original_call(tool, arguments)
        if tool == "compile_check":
            if damage == "omitted":
                result["result"]["omission"] = {"reason": "responseExceededDocumentCharLimit"}
            elif damage == "wrong_status":
                result["result"]["status"] = "failed"
            elif damage == "boolean_count":
                result["result"]["value"]["totalErrorCount"] = False
            elif damage == "hidden_plc_error":
                result["result"]["value"]["plcs"][0].update(state="Error", errorCount=3)
            else:
                result["result"]["value"]["plcs"] = []
        return result

    fake.call = call
    with pytest.raises(EngineeringError, match="[Cc]ompil|diagnostic"):
        asyncio.run(engineer.compile(archive_first=False))
