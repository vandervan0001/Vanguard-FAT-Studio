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
import tomllib
from types import SimpleNamespace

import pytest

from integrations.tia_engineering import (
    Audit, Console, Engineering, EngineeringError, Policy, SdkTransport,
    digest, load_proposal, write_json,
)
import integrations.tia_engineering as engineering_module
from integrations.tia_versions import PROFILE_FILENAME, UPSTREAM_COMMIT, profile, write_server_profile


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
        self.archive_suffix = profile(policy.tia_version).archive_suffix
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
                    target = Path(arguments["archiveDirectory"]) / (arguments["archiveName"] + self.archive_suffix)
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


def mark_test_server(server, tia_version, tmp_path):
    """Manifest fixture only: these bytes are neither Siemens DLLs nor an executable server."""
    (server.parent / "TiaMcpServer.OpennessWorker.exe").write_bytes(b"TEST DOUBLE ONLY: not an Openness worker")
    assemblies = []
    for name in ("Siemens.Engineering.Base", "Siemens.Engineering.Step7", "Siemens.Engineering.WinCCUnified"):
        dll = tmp_path / "test-only-openness" / f"{name}.dll"
        dll.parent.mkdir(parents=True, exist_ok=True)
        dll.write_bytes(f"TEST DOUBLE ONLY: {name} {tia_version}".encode())
        assemblies.append({"name": name, "path": str(dll), "version": tia_version[1:] + ".0.0.0"})
    source_report = {"source_commit": UPSTREAM_COMMIT, "target_version": tia_version, "no_stubs": True,
                     "transformed_files": [{"path": "TestDouble.cs", "before_sha256": digest("fake before"),
                                            "after_sha256": digest("fake after")}],
                     "patch_sha256": ""}
    source_report["patch_sha256"] = digest(json.dumps(source_report["transformed_files"], sort_keys=True, separators=(",", ":")))
    write_server_profile(server, tia_version, assemblies, source_report=source_report if tia_version == "V20" else None)


@pytest.fixture(params=["V20", "V21"])
def policy(tmp_path, request):
    selected = profile(request.param)
    sandbox = tmp_path / "sandbox"
    project_directory = sandbox / "UnitCopy"
    project_directory.mkdir(parents=True)
    project = project_directory / ("UnitCopy" + selected.project_suffix)
    project.write_bytes(b"fake TIA project for workflow test only")
    server = tmp_path / "server" / "tia-mcp.exe"
    server.parent.mkdir()
    server.write_bytes(b"not executed in unit tests")
    mark_test_server(server, request.param, tmp_path)
    policy = Policy(str(project), str(sandbox), str(server), str(tmp_path / "backups"), str(tmp_path / "audit.jsonl"),
                    tia_version=request.param)
    policy.validate()
    return policy


def writable(policy):
    write_json(Path(policy.sandbox_root) / ".fat-workcopy.json",
               {"project_path": policy.project_path, "tia_version": policy.tia_version,
                "profile_id": profile(policy.tia_version).profile_id})
    return replace(policy, allow_write=True)


def engine(policy, console=None):
    fake = FakeTransport(policy)
    engineer = Engineering(policy, fake, Audit(Path(policy.audit_path), policy.project_path, policy.tia_version), console or FakeConsole())
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
    assert manifest.tia_version == policy.tia_version
    assert manifest.profile_id == profile(policy.tia_version).profile_id
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
    assert Path(result["backup"]).suffix == profile(policy.tia_version).archive_suffix
    assert result["tia_version"] == policy.tia_version
    assert result["profile_id"] == profile(policy.tia_version).profile_id
    assert "#value := 2" in fake.content
    assert json.loads((directory / "receipt.json").read_text())["compile"]["status"] == "passed"
    audit = [json.loads(line) for line in Path(policy.audit_path).read_text().splitlines()]
    assert any(row["event"] == "backup_verified" and len(row["sha256"]) == 64 for row in audit)
    assert all(row["tia_version"] == policy.tia_version and row["profile_id"] == profile(policy.tia_version).profile_id for row in audit)
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


def test_archive_from_wrong_tia_version_stops_import(policy, tmp_path):
    engineer, fake = engine(writable(policy), FakeConsole([True]))
    directory = asyncio.run(proposal(engineer, tmp_path))
    fake.archive_suffix = profile("V21" if policy.tia_version == "V20" else "V20").archive_suffix
    with pytest.raises(EngineeringError, match="archive"):
        asyncio.run(engineer.apply(directory))
    assert [tool for tool, _ in actual_writes(fake)] == ["archive_project"]


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
    fake.target = str(tmp_path / ("Original" + profile(policy.tia_version).project_suffix))
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


def mocked_sdk_client(monkeypatch, reported="4.3.0"):
    client_module = pytest.importorskip("mcp.client")
    launches = []

    class Client:
        def __init__(self, params, **options):
            self.server_info = SimpleNamespace(version=reported,
                                               model_dump=lambda **kwargs: {"name": "TEST DOUBLE ONLY", "version": reported})
            self.observation = {"params": params, "options": options, "closed": False}
            launches.append(self.observation)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            self.observation["closed"] = True

    monkeypatch.setattr(client_module, "Client", Client)
    return launches


@pytest.mark.parametrize("writable_mode", [False, True])
def test_connect_uses_validated_version_profile_and_explicit_access_mode(policy, monkeypatch, writable_mode):
    candidate = writable(policy) if writable_mode else policy
    key = "TiaPortal" + candidate.tia_version + "Dir"
    monkeypatch.setenv(key, "UNREVIEWED inherited API directory")
    monkeypatch.setenv("TiaPortalLocation", "UNREVIEWED inherited TIA installation")
    launches = mocked_sdk_client(monkeypatch)
    audit = Audit(Path(candidate.audit_path), candidate.project_path, candidate.tia_version)

    async def exercise():
        async with engineering_module.connect(candidate, writable=writable_mode, console=FakeConsole(), audit=audit) as transport:
            assert transport.writable is writable_mode

    asyncio.run(exercise())
    assert len(launches) == 1 and launches[0]["closed"] is True
    parameters = launches[0]["params"]
    assert parameters.command == candidate.server_executable
    assert parameters.args == ["--access-mode", "read-write" if writable_mode else "read-only", "--project", candidate.project_path]
    assert parameters.env == {key: str(Path(candidate.server_executable).parent.parent / "test-only-openness")}
    rows = [json.loads(line) for line in Path(candidate.audit_path).read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["event"] == "connected"
    assert rows[0]["tia_version"] == candidate.tia_version
    assert rows[0]["profile_id"] == profile(candidate.tia_version).profile_id


def test_connect_refuses_wrong_installation_profile_before_launch(policy, tmp_path, monkeypatch):
    marker = Path(policy.server_executable).parent / PROFILE_FILENAME
    document = json.loads(marker.read_text())
    document["tia_version"] = "V21" if policy.tia_version == "V20" else "V20"
    write_json(marker, document)
    launches = mocked_sdk_client(monkeypatch)
    audit = Audit(Path(policy.audit_path), policy.project_path, policy.tia_version)

    async def exercise():
        async with engineering_module.connect(policy, writable=False, console=FakeConsole(), audit=audit):
            pytest.fail("Mismatched installation must never connect")

    with pytest.raises(EngineeringError, match="does not match"):
        asyncio.run(exercise())
    assert launches == []
    assert not Path(policy.audit_path).exists()


def test_connect_refuses_missing_installation_marker_before_launch(policy, monkeypatch):
    marker = Path(policy.server_executable).parent / PROFILE_FILENAME
    marker.unlink()
    launches = mocked_sdk_client(monkeypatch)
    audit = Audit(Path(policy.audit_path), policy.project_path, policy.tia_version)

    async def exercise():
        async with engineering_module.connect(policy, writable=False, console=FakeConsole(), audit=audit):
            pytest.fail("An unmarked installation must never connect")

    with pytest.raises(EngineeringError, match="installation profile"):
        asyncio.run(exercise())
    assert launches == []
    assert not Path(policy.audit_path).exists()


def test_connect_refuses_unexpected_mcp_version(policy, monkeypatch):
    launches = mocked_sdk_client(monkeypatch, "4.2.0")
    audit = Audit(Path(policy.audit_path), policy.project_path, policy.tia_version)

    async def exercise():
        async with engineering_module.connect(policy, writable=False, console=FakeConsole(), audit=audit):
            pytest.fail("Mismatched server version must never yield a transport")

    with pytest.raises(EngineeringError, match="Unexpected server version"):
        asyncio.run(exercise())
    assert len(launches) == 1 and launches[0]["closed"] is True
    assert not Path(policy.audit_path).exists()


def test_readonly_policy_cannot_append_audit_into_tia_project(policy):
    """Even a status request records an audit row; its path must not corrupt TIA files."""
    with pytest.raises(EngineeringError, match="audit|Audit"):
        replace(policy, audit_path=policy.project_path).validate()


def test_policy_refuses_project_extension_from_another_tia_version(policy):
    other = profile("V21" if policy.tia_version == "V20" else "V20")
    target = Path(policy.project_path).with_suffix(other.project_suffix)
    target.write_bytes(b"TEST DOUBLE ONLY: wrong project version")
    with pytest.raises(EngineeringError, match="work copy is required"):
        replace(policy, project_path=str(target)).validate()


def test_both_tia_versions_require_marked_backend(policy, tmp_path):
    server = tmp_path / "unmarked" / "tia-mcp.exe"
    server.parent.mkdir()
    server.write_bytes(b"TEST DOUBLE ONLY: unmarked server")
    candidate = replace(policy, server_executable=str(server))
    with pytest.raises(EngineeringError, match="installation profile"):
        candidate.validate()


def test_marked_backend_changed_since_install_is_refused(policy, tmp_path):
    server = Path(policy.server_executable)
    server.write_bytes(b"TEST DOUBLE ONLY: replaced server binary")
    with pytest.raises(EngineeringError):
        policy.validate()


def test_legacy_policy_is_v21_only(policy, tmp_path):
    config = tmp_path / "legacy-policy.json"
    value = policy.__dict__.copy()
    value.pop("tia_version")
    write_json(config, value)
    if policy.tia_version == "V21":
        assert Policy.load(config).tia_version == "V21"
    else:
        with pytest.raises(EngineeringError, match=".ap21"):
            Policy.load(config)


@pytest.mark.parametrize("damage", ["version", "profile"])
def test_proposal_version_and_profile_mismatch_refused_before_calls(policy, tmp_path, damage):
    engineer, fake = engine(writable(policy), FakeConsole([True, True, True]))
    directory = asyncio.run(proposal(engineer, tmp_path))
    manifest_path = directory / "proposal.json"
    manifest = json.loads(manifest_path.read_text())
    other = profile("V21" if policy.tia_version == "V20" else "V20")
    if damage == "version":
        manifest.update(tia_version=other.version, profile_id=other.profile_id)
    else:
        manifest["profile_id"] = other.profile_id
    write_json(manifest_path, manifest)
    fake.calls.clear()
    with pytest.raises(EngineeringError, match="TIA version and server profile"):
        asyncio.run(engineer.apply(directory))
    assert fake.calls == []


def test_legacy_proposal_remains_v21_only(policy, tmp_path):
    engineer, _ = engine(policy)
    directory = asyncio.run(proposal(engineer, tmp_path))
    manifest_path = directory / "proposal.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("tia_version")
    manifest.pop("profile_id")
    write_json(manifest_path, manifest)
    if policy.tia_version == "V21":
        assert load_proposal(directory)[0].tia_version == "V21"
    else:
        with pytest.raises(EngineeringError, match="TIA version and server profile"):
            load_proposal(directory)


def test_cross_version_workcopy_acknowledgment_refused(policy):
    candidate = writable(policy)
    other = profile("V21" if policy.tia_version == "V20" else "V20")
    write_json(Path(policy.sandbox_root) / ".fat-workcopy.json",
               {"project_path": policy.project_path, "tia_version": other.version, "profile_id": other.profile_id})
    with pytest.raises(EngineeringError, match="acknowledgment.*TIA version"):
        candidate.require_write()


def test_legacy_workcopy_acknowledgment_is_v21_only(policy):
    candidate = writable(policy)
    write_json(Path(policy.sandbox_root) / ".fat-workcopy.json", {"project_path": policy.project_path})
    if policy.tia_version == "V21":
        candidate.require_write()
    else:
        with pytest.raises(EngineeringError, match="acknowledgment.*TIA version"):
            candidate.require_write()


def test_audit_from_another_profile_refused(policy):
    other = "V21" if policy.tia_version == "V20" else "V20"
    fake = FakeTransport(policy)
    audit = Audit(Path(policy.audit_path), policy.project_path, other)
    with pytest.raises(EngineeringError, match="Audit context"):
        Engineering(policy, fake, audit, FakeConsole())
    assert fake.calls == []


def test_configure_generates_versioned_readonly_fragments(policy, tmp_path, monkeypatch):
    key = "TiaPortal" + policy.tia_version + "Dir"
    monkeypatch.setenv(key, "UNREVIEWED inherited API directory")
    config = tmp_path / "config" / policy.tia_version.lower() / "policy.json"
    config.parent.mkdir(parents=True)
    legacy_claude = config.parent / "claude.mcp.json"
    legacy_codex = config.parent / "codex.mcp.toml"
    legacy_claude.write_text("Existing user configuration\n")
    legacy_codex.write_text("Existing user configuration\n")
    engineering_module.configure(argparse.Namespace(config=str(config), project=policy.project_path,
                                                    sandbox_root=policy.sandbox_root, server=policy.server_executable,
                                                    tia_version=policy.tia_version))
    selected = policy.tia_version.lower()
    name = f"tia-fat-{selected}-readonly"
    claude = json.loads((config.parent / f"claude.{selected}.mcp.json").read_text())["mcpServers"]
    codex = tomllib.loads((config.parent / f"codex.{selected}.mcp.toml").read_text())["mcp_servers"]
    expected = {"command": policy.server_executable,
                "args": ["--access-mode", "read-only", "--project", policy.project_path],
                "env": {key: str(tmp_path / "test-only-openness")}}
    assert claude == codex == {name: expected}
    assert Policy.load(config).tia_version == policy.tia_version
    assert legacy_claude.read_text() == legacy_codex.read_text() == "Existing user configuration\n"


def test_apply_rejects_profile_before_opening_transport(policy, tmp_path, monkeypatch):
    engineer, fake = engine(writable(policy))
    directory = asyncio.run(proposal(engineer, tmp_path))
    manifest_path = directory / "proposal.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["profile_id"] = profile("V21" if policy.tia_version == "V20" else "V20").profile_id
    write_json(manifest_path, manifest)
    config = tmp_path / "policy.json"
    write_json(config, policy.__dict__)
    contacted = []

    @asynccontextmanager
    async def connection(*args, **kwargs):
        contacted.append(True)
        yield fake

    monkeypatch.setattr(engineering_module, "connect", connection)
    with pytest.raises(EngineeringError, match="TIA version and server profile"):
        asyncio.run(engineering_module.run_command(argparse.Namespace(config=str(config), command="apply", proposal=str(directory))))
    assert contacted == []


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
