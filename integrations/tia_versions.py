"""Version-bound installation profiles for the pinned TIA engineering bridge.

Checksums bind a local installation to its recorded build. They are not a
publisher signature or proof of native Siemens qualification.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import uuid


SERVER_VERSION = "4.3.0"
UPSTREAM_COMMIT = "10c5de2eb44c0362792cd141370b3f42f92f6ecd"
PROFILE_FILENAME = "fat-tia-profile.json"
ASSEMBLY_NAMES = frozenset({
    "Siemens.Engineering.Base", "Siemens.Engineering.Step7", "Siemens.Engineering.WinCCUnified",
})
_HASH = re.compile(r"[0-9a-f]{64}")
_RUNTIME_SUFFIXES = frozenset({".exe", ".dll", ".json", ".config"})


@dataclass(frozen=True)
class TiaProfile:
    version: str
    project_suffix: str
    archive_suffix: str
    profile_id: str
    server_version: str = SERVER_VERSION


def profile(tia_version: str) -> TiaProfile:
    if not isinstance(tia_version, str) or tia_version not in {"V20", "V21"}:
        raise ValueError("Select TIA Portal V20 or V21.")
    major = tia_version[1:]
    return TiaProfile(tia_version, ".ap" + major, ".zap" + major,
                      "czarnak-" + SERVER_VERSION + "-v" + major)


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _runtime_files(directory: Path) -> dict[str, Path]:
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.name == PROFILE_FILENAME or path.suffix.lower() not in _RUNTIME_SUFFIXES or not path.is_file():
            continue
        if not path.resolve(strict=True).is_relative_to(directory):
            raise ValueError("Runtime file resolves outside the server installation.")
        if path.name.startswith("Siemens.Engineering.") and path.suffix.lower() == ".dll":
            raise ValueError("Siemens DLLs must stay in the local TIA installation, outside the distributed server.")
        files[path.relative_to(directory).as_posix()] = path
    return files


def _assemblies(records: object, selected: TiaProfile, directory: Path, *, require_hash: bool = False) -> list[dict]:
    if not isinstance(records, list) or len(records) != len(ASSEMBLY_NAMES):
        raise ValueError("Record the three real Siemens Openness assemblies checked by the Windows installer.")
    names = set()
    directories = set()
    result = []
    for item in records:
        if (not isinstance(item, dict) or not isinstance(item.get("name"), str)
                or item["name"] not in ASSEMBLY_NAMES or item["name"] in names):
            raise ValueError("Invalid or duplicate Openness assembly name.")
        version = item.get("version")
        if not isinstance(version, str) or not re.fullmatch(selected.version[1:] + r"\.\d+\.\d+\.\d+", version):
            raise ValueError("Recorded Openness assembly version differs from the selected TIA version.")
        raw = item.get("path")
        if not isinstance(raw, str) or not Path(raw).is_absolute():
            raise ValueError("Openness assembly paths must be absolute.")
        path = Path(raw).resolve(strict=True)
        if not path.is_file() or path.name != item["name"] + ".dll" or path.is_relative_to(directory):
            raise ValueError("Openness assemblies must come from the separate Siemens installation.")
        actual = _sha256(path)
        if require_hash and (not isinstance(item.get("sha256"), str) or not _HASH.fullmatch(item["sha256"])):
            raise ValueError("Recorded Openness assembly checksum is missing or invalid.")
        if "sha256" in item and item["sha256"] != actual:
            raise ValueError("Openness assembly changed after installation; rebuild and check the selected profile.")
        names.add(item["name"])
        directories.add(path.parent)
        result.append({"name": item["name"], "path": str(path), "version": version, "sha256": actual})
    if names != ASSEMBLY_NAMES:
        raise ValueError("Missing Openness assembly.")
    if len(directories) != 1:
        raise ValueError("All three Openness assemblies must belong to the same selected API directory.")
    return result


def _source_patch(report: object, selected: TiaProfile) -> str | None:
    if selected.version == "V21":
        if report is not None:
            raise ValueError("The V21 profile uses the unmodified pinned NuGet package.")
        return None
    if (not isinstance(report, dict) or report.get("source_commit") != UPSTREAM_COMMIT
            or report.get("target_version") != selected.version or report.get("no_stubs") is not True):
        raise ValueError("V20 requires the pinned source retarget report, built against real V20 DLLs.")
    changes = report.get("transformed_files")
    if not isinstance(changes, list) or not changes:
        raise ValueError("V20 source report has no transformed files.")
    paths = set()
    for item in changes:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("Invalid V20 source transformation record.")
        path = PurePosixPath(item["path"])
        if (path.is_absolute() or ".." in path.parts or not path.parts or item["path"] in paths
                or path.parts[0] in {"ref", "reference-stubs"}
                or any(not isinstance(item.get(key), str) or not _HASH.fullmatch(item[key])
                       for key in ("before_sha256", "after_sha256"))):
            raise ValueError("Invalid V20 source transformation path or checksum.")
        paths.add(item["path"])
    actual = hashlib.sha256(json.dumps(changes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if report.get("patch_sha256") != actual:
        raise ValueError("V20 source transformation report checksum differs.")
    return actual


def write_server_profile(server: Path, tia_version: str, openness_assemblies: list[dict],
                         source_report: dict | None = None) -> dict:
    """Record an installation after native build/version/doctor checks succeed.

    The PowerShell installer checks AssemblyName.Version.Major on the actual
    Windows DLLs before calling this function. Python records that evidence and
    checks the DLL hashes again; it does not execute or emulate the Siemens API.
    """
    selected = profile(tia_version)
    server = server.absolute()
    if not server.is_file():
        raise ValueError("Server executable is missing.")
    directory = server.parent.resolve(strict=True)
    marker = directory / PROFILE_FILENAME
    if marker.exists():
        raise ValueError("Installation profile already exists; refusing to replace it.")
    assemblies = _assemblies(openness_assemblies, selected, directory)
    patch = _source_patch(source_report, selected)
    runtime = _runtime_files(directory)
    server_relative = server.relative_to(server.parent).as_posix()
    if server_relative not in runtime or not any(Path(name).name == "TiaMcpServer.OpennessWorker.exe" for name in runtime):
        raise ValueError("A complete host and Openness worker installation is required.")
    document = {
        "schema_version": 1, "tia_version": selected.version, "profile_id": selected.profile_id,
        "server_version": SERVER_VERSION, "upstream_commit": UPSTREAM_COMMIT,
        "build_source": "pinned-source" if selected.version == "V20" else "nuget",
        "source_patch_sha256": patch, "source_report": source_report,
        "server_path": server_relative, "openness_assemblies": assemblies,
        "files": {name: _sha256(path) for name, path in runtime.items()},
        "qualification": "Local installation checks only; perform native TIA acceptance on an authorized work copy.",
    }
    temporary = marker.with_name(marker.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic creation without replacing an installation being prepared elsewhere.
        os.link(temporary, marker)
    finally:
        temporary.unlink(missing_ok=True)
    return validate_server_profile(server, selected.version)


def validate_server_profile(server: Path, tia_version: str) -> dict:
    selected = profile(tia_version)
    server = server.absolute()
    if not server.is_file():
        raise ValueError("Server executable is missing.")
    directory = server.parent.resolve(strict=True)
    marker = directory / PROFILE_FILENAME
    if not marker.exists():
        raise ValueError(selected.version + " requires its own verified installation profile; run "
                         "install-tia-mcp.ps1 -TiaVersion " + selected.version + ".")
    if marker.is_symlink() or marker.stat().st_size > 2_000_000:
        raise ValueError("Invalid local installation profile file.")
    document = json.loads(marker.read_text(encoding="utf-8-sig"))
    if (not isinstance(document, dict) or type(document.get("schema_version")) is not int
            or document["schema_version"] != 1 or document.get("tia_version") != selected.version
            or document.get("profile_id") != selected.profile_id or document.get("server_version") != SERVER_VERSION
            or document.get("upstream_commit") != UPSTREAM_COMMIT
            or document.get("build_source") != ("pinned-source" if selected.version == "V20" else "nuget")
            or document.get("server_path") != server.name):
        raise ValueError("Installed MCP profile does not match the selected TIA version and pinned server.")
    patch = _source_patch(document.get("source_report"), selected)
    if patch != document.get("source_patch_sha256"):
        raise ValueError("Installed V20 source patch identity differs.")
    _assemblies(document.get("openness_assemblies"), selected, directory, require_hash=True)
    runtime = _runtime_files(directory)
    recorded = document.get("files")
    if not isinstance(recorded, dict) or not recorded or set(recorded) != set(runtime) or server.name not in runtime:
        raise ValueError("MCP installation files changed or are incomplete.")
    if not any(Path(name).name == "TiaMcpServer.OpennessWorker.exe" for name in runtime):
        raise ValueError("Openness worker is missing from the installation profile.")
    for name, path in runtime.items():
        if not isinstance(recorded[name], str) or not _HASH.fullmatch(recorded[name]) or _sha256(path) != recorded[name]:
            raise ValueError("MCP host, worker or dependency changed after installation: " + name)
    return document


def server_environment(server: Path, tia_version: str) -> dict[str, str]:
    """Preserve the verified native API path for the host and its worker."""
    document = validate_server_profile(server, tia_version)
    directory = str(Path(document["openness_assemblies"][0]["path"]).parent)
    return {"TiaPortal" + profile(tia_version).version + "Dir": directory}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("write-profile", "check-profile"):
        command = commands.add_parser(name)
        command.add_argument("--server", required=True, type=Path)
        command.add_argument("--tia-version", choices=("V20", "V21"), required=True)
        if name == "write-profile":
            command.add_argument("--openness-record", required=True, type=Path)
            command.add_argument("--source-report", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "write-profile":
            records = json.loads(args.openness_record.read_text(encoding="utf-8-sig"))
            report = json.loads(args.source_report.read_text(encoding="utf-8-sig")) if args.source_report else None
            write_server_profile(args.server, args.tia_version, records, report)
        else:
            validate_server_profile(args.server, args.tia_version)
        print(json.dumps({"tia_version": args.tia_version, "status": "verified",
                          "profile_id": profile(args.tia_version).profile_id}, ensure_ascii=False))
        return 0
    except (ValueError, OSError) as exc:
        print("TIA installation profile rejected: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
