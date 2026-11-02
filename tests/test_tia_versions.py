"""Installation identity checks with labelled test bytes, never Siemens binaries."""

import hashlib
import json
from pathlib import Path

import pytest

from integrations.tia_versions import (
    ASSEMBLY_NAMES, PROFILE_FILENAME, UPSTREAM_COMMIT, profile,
    server_environment, validate_server_profile, write_server_profile,
)


def fake_installation(directory, version):
    server = directory / "server" / "TiaMcpServer.exe"
    server.parent.mkdir(parents=True)
    server.write_bytes(b"TEST DOUBLE ONLY: not a runnable MCP server")
    worker = server.parent / "worker" / "TiaMcpServer.OpennessWorker.exe"
    worker.parent.mkdir()
    worker.write_bytes(b"TEST DOUBLE ONLY: not a runnable Siemens worker")
    (server.parent / "TiaMcpServer.deps.json").write_text('{"test_only":true}\n')
    assemblies = []
    for name in sorted(ASSEMBLY_NAMES):
        dll = directory / "test-only-openness" / (name + ".dll")
        dll.parent.mkdir(exist_ok=True)
        dll.write_bytes(f"TEST DOUBLE ONLY: {name} {version}".encode())
        assemblies.append({"name": name, "path": str(dll), "version": version[1:] + ".0.0.0"})
    changes = [{"path": "TestDouble.cs", "before_sha256": "a" * 64, "after_sha256": "b" * 64}]
    report = {"source_commit": UPSTREAM_COMMIT, "target_version": version, "no_stubs": True,
              "transformed_files": changes,
              "patch_sha256": hashlib.sha256(json.dumps(changes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    return {"server": server, "worker": worker, "assemblies": assemblies,
            "report": report if version == "V20" else None, "version": version}


@pytest.fixture(params=["V20", "V21"])
def installed_profile(tmp_path, request):
    installation = fake_installation(tmp_path, request.param)
    installation["manifest"] = write_server_profile(installation["server"], request.param,
                                                      installation["assemblies"], installation["report"])
    return installation


@pytest.mark.parametrize("version,project,archive", [("V20", ".ap20", ".zap20"), ("V21", ".ap21", ".zap21")])
def test_profiles_bind_project_archive_and_backend(version, project, archive):
    selected = profile(version)
    assert (selected.version, selected.project_suffix, selected.archive_suffix) == (version, project, archive)
    assert selected.profile_id == "czarnak-4.3.0-" + version.lower()
    assert selected.server_version == "4.3.0"


@pytest.mark.parametrize("version", ["V19", "V22", "20", "v20", "", None, [], {}])
def test_unsupported_version_is_refused(version):
    with pytest.raises(ValueError):
        profile(version)


@pytest.mark.parametrize("version", ["V20", "V21"])
def test_both_tia_versions_refuse_missing_installation_marker(tmp_path, version):
    server = tmp_path / "TiaMcpServer.exe"
    server.write_bytes(b"TEST DOUBLE ONLY: unmarked server")
    with pytest.raises(ValueError, match="installation profile"):
        validate_server_profile(server, version)


def test_removing_v20_marker_does_not_allow_relabelling_as_v21(tmp_path):
    item = fake_installation(tmp_path, "V20")
    write_server_profile(item["server"], "V20", item["assemblies"], item["report"])
    (item["server"].parent / PROFILE_FILENAME).unlink()
    with pytest.raises(ValueError, match="installation profile"):
        validate_server_profile(item["server"], "V21")


def test_installed_profile_roundtrip_identifies_all_files(installed_profile):
    item = installed_profile
    result = validate_server_profile(item["server"], item["version"])
    assert result == item["manifest"]
    assert set(result["files"]) == {"TiaMcpServer.exe", "TiaMcpServer.deps.json", "worker/TiaMcpServer.OpennessWorker.exe"}
    assert {assembly["name"] for assembly in result["openness_assemblies"]} == ASSEMBLY_NAMES
    assert result["upstream_commit"] == UPSTREAM_COMMIT
    assert result["source_patch_sha256"] == (item["report"]["patch_sha256"] if item["report"] else None)
    assert server_environment(item["server"], item["version"]) == {
        "TiaPortal" + item["version"] + "Dir": str(Path(item["assemblies"][0]["path"]).parent),
    }


def test_profile_from_another_tia_version_is_refused(installed_profile):
    item = installed_profile
    other = "V21" if item["version"] == "V20" else "V20"
    with pytest.raises(ValueError, match="does not match"):
        validate_server_profile(item["server"], other)


def test_malformed_assembly_name_is_refused(installed_profile):
    item = installed_profile
    marker = item["server"].parent / PROFILE_FILENAME
    document = json.loads(marker.read_text())
    document["openness_assemblies"][0]["name"] = []
    marker.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="assembly name"):
        validate_server_profile(item["server"], item["version"])


def test_dlls_from_different_api_directories_are_refused(installed_profile, tmp_path):
    item = installed_profile
    marker = item["server"].parent / PROFILE_FILENAME
    document = json.loads(marker.read_text())
    assembly = document["openness_assemblies"][0]
    original = Path(assembly["path"])
    different = tmp_path / "different-api-installation" / original.name
    different.parent.mkdir()
    different.write_bytes(original.read_bytes())
    assembly["path"] = str(different)
    marker.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="same selected API directory"):
        validate_server_profile(item["server"], item["version"])
    with pytest.raises(ValueError, match="same selected API directory"):
        server_environment(item["server"], item["version"])


@pytest.mark.parametrize("version", ["V20", "V21"])
def test_recording_dlls_from_different_api_directories_is_refused(tmp_path, version):
    item = fake_installation(tmp_path, version)
    assembly = item["assemblies"][0]
    original = Path(assembly["path"])
    different = tmp_path / "different-api-installation" / original.name
    different.parent.mkdir()
    different.write_bytes(original.read_bytes())
    assembly["path"] = str(different)
    with pytest.raises(ValueError, match="same selected API directory"):
        write_server_profile(item["server"], version, item["assemblies"], item["report"])
    assert not (item["server"].parent / PROFILE_FILENAME).exists()


@pytest.mark.parametrize("target", ["server", "worker", "dependency", "openness"])
def test_changed_binary_worker_dependency_or_dll_is_refused(installed_profile, target):
    item = installed_profile
    path = {"server": item["server"], "worker": item["worker"],
            "dependency": item["server"].parent / "TiaMcpServer.deps.json",
            "openness": Path(item["assemblies"][0]["path"])}[target]
    path.write_bytes(b"TEST DOUBLE ONLY: changed since installation")
    with pytest.raises(ValueError, match="changed"):
        validate_server_profile(item["server"], item["version"])


@pytest.mark.parametrize("damage", ["added_file", "missing_worker", "wrong_dll_major", "wrong_profile_id", "wrong_commit"])
def test_incomplete_or_crossed_installation_is_refused(installed_profile, damage):
    item = installed_profile
    marker = item["server"].parent / PROFILE_FILENAME
    document = json.loads(marker.read_text())
    if damage == "added_file":
        (item["server"].parent / "Unreviewed.dll").write_bytes(b"TEST DOUBLE ONLY: unexpected dependency")
    elif damage == "missing_worker":
        item["worker"].unlink()
    elif damage == "wrong_dll_major":
        document["openness_assemblies"][0]["version"] = "21.0.0.0" if item["version"] == "V20" else "20.0.0.0"
    elif damage == "wrong_profile_id":
        document["profile_id"] = profile("V21" if item["version"] == "V20" else "V20").profile_id
    else:
        document["upstream_commit"] = "0" * 40
    marker.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        validate_server_profile(item["server"], item["version"])


def test_existing_profile_is_preserved(installed_profile):
    item = installed_profile
    marker = item["server"].parent / PROFILE_FILENAME
    before = marker.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        write_server_profile(item["server"], item["version"], item["assemblies"], item["report"])
    assert marker.read_bytes() == before


@pytest.mark.parametrize("damage", ["missing", "stubs", "checksum", "different_commit"])
def test_v20_requires_intact_pinned_source_report(tmp_path, damage):
    item = fake_installation(tmp_path, "V20")
    report = item["report"]
    if damage == "missing":
        report = None
    elif damage == "stubs":
        report["no_stubs"] = False
    elif damage == "checksum":
        report["patch_sha256"] = "0" * 64
    else:
        report["source_commit"] = "0" * 40
    with pytest.raises(ValueError):
        write_server_profile(item["server"], "V20", item["assemblies"], report)
    assert not (item["server"].parent / PROFILE_FILENAME).exists()


def test_worker_is_required_when_recording_installation(tmp_path):
    item = fake_installation(tmp_path, "V20")
    item["worker"].unlink()
    with pytest.raises(ValueError, match="worker"):
        write_server_profile(item["server"], "V20", item["assemblies"], item["report"])
    assert not (item["server"].parent / PROFILE_FILENAME).exists()
