"""Build a public, passive Siemens DB/OB1 example from the laboratory contract."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile

from fat_studio.demo_contract import DB_NAME, DEMO_TAGS, DEMO_VERSION, PUMPS, TANKS, VALVES


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def _literal(kind: str, value: object) -> str:
    if kind == "BOOL":
        return "TRUE" if value else "FALSE"
    if kind == "REAL":
        return f"REAL#{float(value):.8g}" if float(value) % 1 else f"REAL#{float(value):.1f}"
    return f"INT#{int(value)}"


def db_source() -> str:
    """The canonical example is disabled; no physical address is assigned."""
    lines = [
        "// SPDX-License-Identifier: MIT. Public passive laboratory example.",
        f'DATA_BLOCK "{DB_NAME}"',
        "{ S7_Optimized_Access := 'FALSE' }",
        "VERSION : 1.0",
        "VAR",
        "    EnableDemo { ExternalAccessible := 'False'; ExternalVisible := 'False'; "
        "ExternalWritable := 'False' } : Bool := FALSE; // isolated virtual copy only",
    ]
    for field, direction, kind, initial, _unit, _low, _high in DEMO_TAGS.values():
        writable = "True" if direction == "input" else "False"
        lines.append(
            f"    {field} {{ ExternalAccessible := 'True'; ExternalVisible := 'True'; "
            f"ExternalWritable := '{writable}' }} : {kind.title()} := {_literal(kind, initial)};"
        )
    return "\n".join([*lines, "END_VAR", "BEGIN", "END_DATA_BLOCK", ""])


def main_source() -> str:
    """Only gates, native LIMIT and native NORM_X/SCALE_X; no sequence or latch."""
    def member(field: str) -> str:
        return f'"{DB_NAME}".{field}'

    gate = f"{member('EnableDemo')} AND {member('StopHealthy')}"
    lines = [
        "// SPDX-License-Identifier: MIT. No equipment library or process sequence.",
        'ORGANIZATION_BLOCK "Main"',
        "{ S7_Optimized_Access := 'TRUE' }",
        "VERSION : 1.0",
        "BEGIN",
    ]
    for pump in PUMPS:
        prefix = pump["id"]
        command = member(prefix + "_RunCommand")
        speed = member(prefix + "_SpeedCommand")
        lines += [
            f"    {command} := {gate} AND {member(prefix + '_Request')};",
            f"    IF {command} THEN",
            f"        {speed} := LIMIT(MN := REAL#0.0, IN := {member(prefix + '_RequestedSpeed')}, "
            "MX := REAL#100.0);",
            "    ELSE",
            f"        {speed} := REAL#0.0;",
            "    END_IF;",
        ]
    for valve in VALVES:
        prefix = valve["id"]
        if prefix.startswith("FCV"):
            output = member(prefix + "_PositionCommand")
            lines += [
                f"    IF {gate} THEN",
                f"        {output} := LIMIT(MN := REAL#0.0, IN := {member(prefix + '_RequestedPosition')}, "
                "MX := REAL#100.0);",
                "    ELSE",
                f"        {output} := REAL#0.0;",
                "    END_IF;",
            ]
        else:
            lines.append(f"    {member(prefix + '_OpenCommand')} := {gate} AND {member(prefix + '_Request')};")
    for tank in TANKS:
        number = tank["id"][2:]
        lines += [
            f"    {member('LT' + number + '_Percent')} := SCALE_X(MIN := REAL#0.0,",
            f"        VALUE := NORM_X(MIN := INT#0, VALUE := {member('LT' + number + '_Raw')}, "
            "MAX := INT#27648), MAX := REAL#100.0);",
        ]
    return "\n".join([*lines, "END_ORGANIZATION_BLOCK", ""])


def _files() -> dict[str, bytes]:
    # Import only the public factory. No engineering/customer source is consulted.
    from fat_studio.demo_lab import demo_lab_project

    db, main = db_source(), main_source()
    table = io.StringIO(newline="")
    writer = csv.writer(table, lineterminator="\n")
    writer.writerow(["tag_id", "symbol", "direction", "plc_type", "wire_type", "unit", "minimum", "maximum",
                     "observed_address", "observed_node_id"])
    for tag_id, (field, direction, kind, _initial, unit, low, high) in DEMO_TAGS.items():
        writer.writerow([tag_id, f'"{DB_NAME}"."{field}"', direction, kind,
                         {"BOOL": "Boolean", "INT": "Int16", "REAL": "Float"}[kind], unit,
                         "" if low is None else low, "" if high is None else high, "", ""])
    readme = """# Public passive PLC laboratory

This bundle has one standard DB and OB1, 75 mapped primitive tags, and no FB,
UDT, customer library, state machine or equipment diagnostic logic. EnableDemo
defaults to FALSE. Only an explicitly isolated virtual copy may set it to TRUE.
Requests pass through EnableDemo and StopHealthy. Speeds/positions use native
LIMIT; three levels use native NORM_X/SCALE_X (0..27648 to 0..100).

Vanguard FAT Studio supplies simulated requests and feedbacks. The PLC owns all command
outputs. This example is not a production control or safety program.

Import plc/Program_All.scl into a NEW TIA V21 simulation project. Configure an
isolated PLCSIM Advanced CPU and OPC UA server separately. Compile, review and
load with the authorized human engineering workflow. Never import it into an
existing plant project. See docs/DEMO_PLC.md in the source distribution.

tags.csv intentionally leaves addresses and NodeIds empty. Export the compiled
standard DB with Openness WithReadOnly for actual bit offsets; browse the real
OPC UA server, verify its certificate and ApplicationUri, and record each actual
NodeId/type/access. Set a separate local machine target policy before connecting.
demo-lab.json uses Vanguard FAT Studio's Python demo controller until explicitly remapped.

Verify this bundle with: python -m integrations.demo_plc verify PATH_TO_BUNDLE
No secret, private key or native CPU command is included. No human FAT verdict
is supplied by this example.
"""
    project = demo_lab_project()
    project_data = project.model_dump(mode="json")
    return {name: value.encode("utf-8") for name, value in {
        "plc/DB_FAT_Demo.scl": db,
        "plc/Main.scl": main,
        "plc/Program_All.scl": db + "\n" + main,
        "tags.csv": table.getvalue(),
        "demo-lab.json": _json(project_data),
        "README.md": readme,
    }.items()}


def _reject_links(path: Path) -> None:
    for candidate in (path, *path.parents):
        # is_symlink covers POSIX and Windows symlinks; is_junction covers NTFS junctions.
        if candidate.is_symlink() or (hasattr(candidate, "is_junction") and candidate.is_junction()):
            raise ValueError(f"Link/reparse path refused: {candidate}")


def build(destination: Path) -> dict:
    destination = Path(destination).absolute()
    _reject_links(destination)
    if destination.exists():
        raise FileExistsError(f"A new bundle directory is required: {destination}")
    files = _files()
    manifest = {
        "format": "fat-studio-public-demo-plc-v1", "demo_version": DEMO_VERSION,
        "db_name": DB_NAME, "mapped_tags": len(DEMO_TAGS), "plc_blocks": [DB_NAME, "Main"],
        "canonical_enable_demo": False,
        "files": [{"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                  for name, data in sorted(files.items())],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    _reject_links(destination.parent)
    temporary = Path(tempfile.mkdtemp(prefix=".public-demo-", dir=destination.parent))
    try:
        for name, data in files.items():
            target = temporary / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (temporary / "manifest.json").write_text(_json(manifest), encoding="utf-8")
        # Windows/POSIX rename refuses an existing nonempty directory; a second check
        # also refuses an empty directory created after the first check.
        if destination.exists():
            raise FileExistsError(f"Bundle destination appeared during build: {destination}")
        temporary.rename(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return verify(destination)


def verify(directory: Path) -> dict:
    directory = Path(directory).absolute()
    _reject_links(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != "fat-studio-public-demo-plc-v1":
        raise ValueError("Unsupported public demo manifest")
    if (manifest.get("mapped_tags") != 75 or manifest.get("canonical_enable_demo") is not False
            or manifest.get("db_name") != DB_NAME or manifest.get("plc_blocks") != [DB_NAME, "Main"]):
        raise ValueError("Unexpected public demo contract metadata")
    entries = manifest.get("files")
    if not isinstance(entries, list) or len(entries) != 6:
        raise ValueError("Expected the six public payload files")
    expected = {"manifest.json"}
    for entry in entries:
        name = entry["path"]
        path = Path(name)
        if path.anchor or ".." in path.parts or "\\" in name or ":" in name or name in expected:
            raise ValueError("Unsafe or duplicate manifest path")
        expected.add(name)
        target = directory / path
        _reject_links(target)
        data = target.read_bytes()
        if len(data) != entry["size"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"Integrity mismatch: {name}")
    actual = set()
    for path in directory.rglob("*"):
        _reject_links(path)
        if path.is_file():
            actual.add(path.relative_to(directory).as_posix())
    if actual != expected:
        raise ValueError("Unexpected or missing bundle files")
    if expected != {"manifest.json", "plc/DB_FAT_Demo.scl", "plc/Main.scl", "plc/Program_All.scl",
                    "tags.csv", "demo-lab.json", "README.md"}:
        raise ValueError("Unexpected public payload paths")
    return {"verified": True, "files": len(actual), "mapped_tags": manifest["mapped_tags"],
            "canonical_enable_demo": manifest["canonical_enable_demo"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "verify"])
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        result = build(args.directory) if args.action == "build" else verify(args.directory)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"{error}\n")
    print(_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
