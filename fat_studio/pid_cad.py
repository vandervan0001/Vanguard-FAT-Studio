"""Optional, local LibreDWG command-line boundary. No document selects a tool."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
import re
import subprocess
import tempfile

MAX_CAD_BYTES = 20 * 1024 * 1024
CAD_TIMEOUT_S = 30
LIBREDWG_VERSION = "0.14"
LIBREDWG_COMMIT = "d9468ae948b8f07a08efa756c19f8916052358c0"


def _tool_directory() -> Path:
    configured = os.environ.get("FAT_STUDIO_PID_CAD_DIR", "")
    if configured:
        directory = Path(configured)
        if not directory.is_absolute():
            raise ValueError("FAT_STUDIO_PID_CAD_DIR doit être un dossier absolu du poste.")
        return directory.resolve()
    return Path(__file__).resolve().parent.parent / ".tools" / "pid-cad" / "libredwg-0.14-win64"


def _tool(name: str) -> Path:
    directory = _tool_directory()
    executable = directory / (name + (".exe" if os.name == "nt" else ""))
    if not executable.is_file():
        raise ValueError("LibreDWG local absent : exécutez scripts/setup-pid-cad.ps1 ou configurez FAT_STUDIO_PID_CAD_DIR sur le poste.")
    return executable


@lru_cache(maxsize=8)
def _probe_tool(path: str, size: int, modified: int, name: str) -> str:
    """Probe a workstation-selected executable once per file version."""
    try:
        result = subprocess.run(
            [path, "--version"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=3, shell=False, check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    banner = result.stdout[:200].decode("ascii", errors="replace").strip().splitlines()
    if result.returncode != 0 or not banner or not banner[0].startswith(name + " "):
        return ""
    return banner[0]


def cad_capabilities() -> dict:
    """Report installation, with separate read/write limits and no network call."""
    tools = {}
    versions = {}
    for name in ("dwg2dxf", "dxf2dwg"):
        try:
            executable = _tool(name)
            stat = executable.stat()
            versions[name] = _probe_tool(str(executable), stat.st_size, stat.st_mtime_ns, name)
            tools[name] = bool(versions[name])
        except (ValueError, OSError):
            tools[name] = False
    return {
        "engine": "GNU LibreDWG", "license": "GPL-3.0-or-later",
        "dwg_import": tools["dwg2dxf"], "dwg_export": tools["dxf2dwg"],
        "read_available": tools["dwg2dxf"], "write_available": tools["dxf2dwg"],
        "available": all(tools.values()), "configured_version": LIBREDWG_VERSION,
        "versions": versions,
        "write_version": "r2000", "experimental_write": True,
        "message": (
            "LibreDWG local disponible. Export DWG R2000 expérimental ; vérifier dans le logiciel CAO destinataire."
            if all(tools.values()) else
            "DWG nécessite LibreDWG gratuit installé sur ce poste (scripts/setup-pid-cad.ps1). DXF reste disponible."
        ),
        "read_versions": "R13–R2018 selon les classes prises en charge par LibreDWG",
        "max_bytes": MAX_CAD_BYTES,
    }


def _check_input(data: bytes, kind: str) -> None:
    if not isinstance(data, bytes) or not data or len(data) > MAX_CAD_BYTES:
        raise ValueError("Le fichier CAO doit contenir entre 1 octet et 20 Mio.")
    if kind == "dwg" and not re.match(rb"AC10\d\d", data[:6]):
        raise ValueError("Signature DWG absente ou version non prise en charge.")
    if kind == "dxf" and not (data.startswith(b"AutoCAD Binary DXF") or (b"SECTION" in data[:2048] and b"\x00" not in data[:2048])):
        raise ValueError("Signature DXF absente.")


def _normalize_libredwg_dxf(data: bytes) -> bytes:
    """Remove two invalid, empty records emitted by LibreDWG 0.14.

    Its DXF writer can emit an empty binary preview (310) and a null ENDBLK
    handle (5/105). Neither carries drawing data. Assign a fresh handle above
    every emitted handle; all geometry and XRECORD data stay intact.
    This applies only to output of the locally configured converter.
    """
    lines = data.splitlines()
    if len(lines) % 2:
        raise ValueError("LibreDWG a produit un DXF incomplet.")
    handles = [int(lines[index + 1].strip(), 16) for index in range(0, len(lines), 2)
               if lines[index].strip() in (b"5", b"105") and re.fullmatch(rb"[0-9a-fA-F]+", lines[index + 1].strip())]
    next_handle = max(handles, default=0) + 1
    result = []
    for index in range(0, len(lines), 2):
        code, value = lines[index:index + 2]
        if code.strip() == b"310" and not value.strip():
            continue
        if code.strip() in (b"5", b"105") and value.strip() == b"0":
            value = f"{next_handle:X}".encode("ascii")
            next_handle += 1
        result.extend((code, value))
    return b"\n".join(result) + b"\n"


def _convert(data: bytes, source_kind: str) -> bytes:
    _check_input(data, source_kind)
    target_kind = "dxf" if source_kind == "dwg" else "dwg"
    executable = _tool("dwg2dxf" if source_kind == "dwg" else "dxf2dwg")
    # All filenames and arguments are generated here, never obtained from the drawing.
    with tempfile.TemporaryDirectory(prefix="fat-pid-cad-") as temporary:
        directory = Path(temporary)
        source = directory / ("input." + source_kind)
        target = directory / ("output." + target_kind)
        source.write_bytes(data)
        arguments = [str(executable), "-v0", "--as", "r2000", "-o", str(target), str(source)]
        try:
            completed = subprocess.run(
                arguments, cwd=directory, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT, timeout=CAD_TIMEOUT_S, check=False,
                shell=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Conversion LibreDWG interrompue après 30 secondes.") from exc
        except OSError as exc:
            raise ValueError("Impossible de lancer le convertisseur LibreDWG local.") from exc
        # Do not expose converter output (it may contain untrusted document text).
        if completed.returncode != 0 or not target.is_file():
            raise ValueError("LibreDWG a refusé cette conversion. Utilisez DXF ou un export CAO simplifié.")
        if not 0 < target.stat().st_size <= MAX_CAD_BYTES:
            raise ValueError("La conversion CAO dépasse la limite de 20 Mio ou produit un fichier vide.")
        result = target.read_bytes()
        _check_input(result, target_kind)
        if target_kind == "dxf":
            result = _normalize_libredwg_dxf(result)
        return result


def dwg_to_dxf(data: bytes) -> bytes:
    return _convert(data, "dwg")


def dxf_to_dwg(data: bytes) -> bytes:
    return _convert(data, "dxf")
