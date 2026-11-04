"""Explicit public payload selection shared by builds and installers (stdlib only)."""

from __future__ import annotations

import argparse
from fnmatch import fnmatchcase
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import zipfile


ROOT = Path(__file__).resolve().parent
POLICY = "public-distribution.json"


def load_policy(root: Path = ROOT) -> dict:
    policy = json.loads((root / POLICY).read_text(encoding="utf-8"))
    if policy.get("schema") != 1 or not policy.get("wheel_files") or not policy.get("source_files"):
        raise ValueError("Invalid public distribution policy")
    return policy


def portable_name(name: str) -> str:
    if (not name or name.startswith("/") or "\\" in name or ":" in name
            or any(part in {"", ".", ".."} for part in name.split("/"))):
        raise ValueError("Invalid public payload path: " + name)
    return name


def is_allowed(name: str, files: list[str], patterns: list[str]) -> bool:
    portable_name(name)
    parts = name.split("/")
    return name in files or any(
        len(parts) == len(pattern.split("/"))
        and all(fnmatchcase(part, item) for part, item in zip(parts, pattern.split("/")))
        for pattern in patterns)


def checked_file(root: Path, name: str) -> Path:
    portable_name(name)
    root = root.resolve(strict=True)
    path = root / name
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink() or part.is_junction():
            raise ValueError("Linked public payload refused: " + name)
    if not path.resolve(strict=True).is_relative_to(root) or not path.is_file():
        raise ValueError("Public payload outside source: " + name)
    return path


def check_content(name: str, content: bytes) -> None:
    # Keep private identifiers out of this public tool's own literal payload.
    # The public Vanguard brand is allowed; private PLC identifiers are not.
    forbidden = (b"nouvelle" + b"-caledonie", b"nouvelle" + b" caledonie",
                 b"nouvelle" + b"-cal\xc3\xa9donie", b"nouvelle" + b" cal\xc3\xa9donie",
                 b"db_" + b"pilot_io", b"fb_" + b"vg_",
                 b"db_" + b"vg_", b"fc_" + b"vg_", b"udt_" + b"vg_",
                 b"standard_" + b"objects_v1", b"vanguard-" + b"pilot-v1",
                 b"cycle" + b"engineering.exe", b"cycle" + b"online.exe")
    lowered = content.decode("utf-8", errors="ignore").casefold().encode("utf-8")
    if any(word in lowered for word in forbidden):
        raise ValueError("Private engineering content refused: " + name)
    # A codec's quoted header constant is not key material. A PEM document, or
    # an embedded PEM body, is refused without printing any part of its value.
    if (re.search(rb"(?m)^[ \t]*-----BEGIN (?:[A-Z0-9 ]* )?PRIVATE KEY-----", content)
            or re.search(rb"-----BEGIN (?:[A-Z0-9 ]* )?PRIVATE KEY-----\r?\n"
                         rb"(?:[A-Za-z0-9+/=]+\r?\n){2,}", content)
            or re.search(rb"-----BEGIN (?:[A-Z0-9 ]* )?PRIVATE KEY-----(?:\r?\n|\\n|\\r\\n)"
                         rb"(?:[A-Za-z0-9+/=]{32,}(?:\r?\n|\\n|\\r\\n))+"
                         rb"-----END (?:[A-Z0-9 ]* )?PRIVATE KEY-----", content)):
        raise ValueError("Private key refused: " + name)
    if PurePosixPath(name).suffix.lower() in {".key", ".pfx", ".p12", ".dpapi"}:
        raise ValueError("Private credential payload refused: " + name)


def selected_files(root: Path, section: str, *, strict_packages: bool = True) -> list[str]:
    policy = load_policy(root)
    files = set(policy[section + "_files"])
    patterns = policy.get(section + "_patterns", [])
    for pattern in patterns:
        files.update(path.relative_to(root).as_posix() for path in root.glob(pattern) if path.is_file())
    if strict_packages:
        for package in ("fat_studio", "integrations"):
            for path in (root / package).rglob("*"):
                if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                    continue
                name = path.relative_to(root).as_posix()
                if not is_allowed(name, policy["wheel_files"], policy.get("wheel_patterns", [])):
                    raise ValueError("Unexpected file in public package: " + name)
    if len(files) != len({name.casefold() for name in files}):
        raise ValueError("Case-colliding public filenames")
    for name in sorted(files):
        content = checked_file(root, name).read_bytes()
        check_content(name, content)
    return sorted(files)


def validate_wheel(wheel: Path, *, policy_root: Path = ROOT) -> int:
    policy = load_policy(policy_root)
    count = 0
    seen: set[str] = set()
    metadata_root: str | None = None
    with zipfile.ZipFile(wheel) as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue
            name = portable_name(item.filename)
            if name.casefold() in seen or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Duplicate or linked wheel entry: " + name)
            seen.add(name.casefold())
            if ".dist-info/" in name:
                folder, relative = name.split("/", 1)
                if not re.fullmatch(r"vanguard_fat_studio-[0-9][A-Za-z0-9_.]*\.dist-info", folder):
                    raise ValueError("Unexpected wheel metadata: " + name)
                if metadata_root is not None and metadata_root != folder:
                    raise ValueError("Multiple application metadata directories")
                metadata_root = folder
                if relative not in {"METADATA", "WHEEL", "RECORD", "entry_points.txt", "top_level.txt",
                                     "licenses/LICENSE", "licenses/THIRD_PARTY_NOTICES.md"}:
                    raise ValueError("Unexpected wheel metadata entry: " + name)
            elif not is_allowed(name, policy["wheel_files"], policy.get("wheel_patterns", [])):
                raise ValueError("Non-public wheel entry: " + name)
            check_content(name, archive.read(item))
            count += 1
    if metadata_root is None or "fat_studio/__init__.py" not in seen:
        raise ValueError("Application wheel payload missing")
    return count


def copy_source(root: Path, destination: Path) -> int:
    root = root.resolve(strict=True)
    names = selected_files(root, "source")
    destination = destination.resolve()
    if destination.exists() or destination.is_relative_to(root):
        raise ValueError("Choose a new destination outside the source tree")
    destination.mkdir(parents=True)
    for name in names:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(checked_file(root, name), target)
    return len(names)


def file_manifest(root: Path) -> list[dict]:
    entries = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        checked_file(root, name)
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        entries.append({"path": name, "size": path.stat().st_size, "sha256": digest})
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    copy = sub.add_parser("copy-source")
    copy.add_argument("destination", type=Path)
    wheel = sub.add_parser("check-wheel")
    wheel.add_argument("wheel", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "check":
            result = len(selected_files(args.root, "source"))
        elif args.command == "copy-source":
            result = copy_source(args.root, args.destination)
        else:
            result = validate_wheel(args.wheel, policy_root=args.root)
        print(json.dumps({"public_files": result}))
        return 0
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
