#!/usr/bin/env python3
"""Validate the interpreter and an optional offline kit before pip is invoked.

Only the standard library is used, so this also works in a brand-new venv.
The manifest detects damaged files, not the authenticity of its publisher.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import struct
import sys
import sysconfig


def platform_name() -> str:
    if sys.platform == "win32":
        # platform.machine() can describe an ARM host while this Python is
        # AMD64 under emulation. Wheel compatibility follows the interpreter.
        architecture = {"win-amd64": "x64", "win-arm64": "arm64", "win32": "x86"}.get(
            sysconfig.get_platform().lower(), sysconfig.get_platform().lower())
        return f"Windows-{architecture}"
    machine = platform.machine().lower()
    architecture = "x64" if machine in {"amd64", "x86_64"} else machine
    system = {"linux": "Linux", "darwin": "macOS"}.get(sys.platform, sys.platform)
    return f"{system}-{architecture}"


def validate_kit(root: Path, target: str, *, engineering: bool = False) -> int:
    root = root.resolve(strict=True)
    manifest_path = root / "offline-manifest.json"
    wheelhouse = root / "wheelhouse"
    if not manifest_path.exists() and not wheelhouse.exists():
        return 0
    if not manifest_path.is_file() or not wheelhouse.is_dir():
        raise ValueError("Kit incomplet : wheelhouse/ et offline-manifest.json doivent être présents ensemble.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (not isinstance(manifest, dict) or type(manifest.get("schema")) is not int
            or manifest["schema"] != 1 or manifest.get("python") != "3.12"):
        raise ValueError("Format de kit hors ligne incompatible.")
    if manifest.get("platform") != target:
        raise ValueError(f"Ce kit cible {manifest.get('platform')!r}, mais l'interpréteur utilise {target}. "
                         "Utiliser un clone source sans wheelhouse ou préparer les wheels de cette plateforme.")
    if engineering and manifest.get("engineering") is not True:
        raise ValueError("Ce kit contient seulement le runtime. Préparer un kit avec -Engineering pour cette option.")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("La liste de fichiers du kit est absente ou vide.")
    known: set[str] = set()
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("Entrée de manifeste invalide.")
        relative = item["path"]
        # Manifest paths are portable POSIX relative paths, never Windows drive/UNC paths.
        if (not relative or relative.startswith("/") or "\\" in relative or ":" in relative
                or any(part in {"", ".", ".."} for part in relative.split("/"))):
            raise ValueError("Chemin invalide dans le manifeste.")
        key = relative.casefold() if target.startswith("Windows-") else relative
        if key in known:
            raise ValueError("Chemin dupliqué dans le manifeste : " + relative)
        known.add(key)
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Fichier absent ou chemin sortant du kit : " + relative)
        expected = item.get("sha256")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Empreinte SHA-256 invalide : " + relative)
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError("Empreinte incorrecte : " + relative)
    wheels = 0
    for path in wheelhouse.iterdir():
        relative = path.relative_to(root).as_posix()
        key = relative.casefold() if target.startswith("Windows-") else relative
        if not path.is_file() or path.suffix.lower() != ".whl" or key not in known:
            raise ValueError("Fichier wheelhouse non répertorié ou invalide : " + path.name)
        wheels += 1
    if not wheels:
        raise ValueError("Le kit ne contient aucune wheel.")
    return wheels


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--engineering", action="store_true")
    args = parser.parse_args()
    try:
        target = platform_name()
        if sys.version_info[:2] != (3, 12) or struct.calcsize("P") != 8:
            raise ValueError("Les lanceurs exigent Python 3.12 64 bits. Choisir cet interpréteur puis recréer .venv si nécessaire.")
        if sys.platform == "win32" and target != "Windows-x64":
            raise ValueError("Le lanceur Windows exige Python 3.12 x64 (AMD64), y compris sur Windows ARM.")
        count = validate_kit(args.root, target, engineering=args.engineering)
        print(f"Python 3.12 · {target} · " + (f"kit vérifié : {count} wheels" if count else "installation depuis les versions verrouillées"))
        return 0
    except (OSError, ValueError) as exc:
        print("Installation arrêtée : " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
