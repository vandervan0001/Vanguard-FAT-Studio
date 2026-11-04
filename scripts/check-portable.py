"""Verify a portable runtime before importing any application dependency (stdlib)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


def validate_portable(root: Path) -> int:
    root = root.resolve(strict=True)
    manifest = json.loads((root / "portable-manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("schema") != 1 or manifest.get("platform") != "Windows-x64"
            or manifest.get("python") != "3.12.10"):
        raise ValueError("Portable manifest incompatible")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Portable file list missing")
    seen = set()
    for item in entries:
        name = item.get("path") if isinstance(item, dict) else None
        if (not isinstance(name, str) or not name or name.startswith("/") or "\\" in name or ":" in name
                or any(part in {"", ".", ".."} for part in name.split("/"))):
            raise ValueError("Invalid portable path")
        if name.casefold() in seen:
            raise ValueError("Duplicate portable path: " + name)
        seen.add(name.casefold())
        path = root / name
        for part in (path, *path.parents):
            if part == root:
                break
            if part.is_symlink() or part.is_junction():
                raise ValueError("Linked portable path: " + name)
        if not path.resolve(strict=True).is_relative_to(root) or not path.is_file():
            raise ValueError("Missing portable file: " + name)
        digest = item.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Invalid portable digest: " + name)
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != digest or path.stat().st_size != item.get("size"):
            raise ValueError("Portable file modified: " + name)
    for path in root.rglob("*"):
        if path.is_file() and path.name != "portable-manifest.json":
            if path.relative_to(root).as_posix().casefold() not in seen:
                raise ValueError("Unlisted portable file: " + path.relative_to(root).as_posix())
    return len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        print(json.dumps({"verified_files": validate_portable(args.root)}))
        return 0
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
