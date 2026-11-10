"""Build a fresh Windows x64 portable from official Python and locked wheels."""

from __future__ import annotations

import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import sysconfig
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from public_distribution import (  # noqa: E402
    ROOT, check_content, checked_file, file_manifest, portable_name, selected_files, validate_wheel,
)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def application_identity(root: Path, wheel: Path) -> dict:
    with zipfile.ZipFile(wheel) as archive:
        name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA") and len(name.split("/")) == 2)
        package = BytesParser().parsebytes(archive.read(name))
    result = {"application_version": package["Version"], "source_commit": "", "source_dirty": True}
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
        changed = subprocess.run(["git", "diff", "--name-only", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.splitlines()
        public = set(selected_files(root, "source"))
        untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=root, check=True,
                                   capture_output=True, text=True).stdout.splitlines()
        result.update(source_commit=revision, source_dirty=bool(public.intersection([*changed, *untracked])))
    except (OSError, subprocess.CalledProcessError):
        pass
    return result


def locked_wheels(directory: Path, lockfile: Path) -> list[Path]:
    expected = {}
    for line in lockfile.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        requirement = line.split(";", 1)[0].strip()
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)", requirement)
        if not match:
            raise ValueError("Unpinned portable dependency: " + line)
        expected[re.sub(r"[-_.]+", "-", match[1]).lower()] = match[2]
    result = []
    found = set()
    for wheel in sorted(directory.iterdir()):
        if not wheel.is_file() or wheel.suffix != ".whl" or wheel.is_symlink():
            raise ValueError("Unexpected wheelhouse entry: " + wheel.name)
        with zipfile.ZipFile(wheel) as archive:
            metadata = [name for name in archive.namelist() if len(name.split("/")) == 2
                        and name.endswith(".dist-info/METADATA")]
            if len(metadata) != 1:
                raise ValueError("Wheel metadata missing or ambiguous: " + wheel.name)
            package = BytesParser().parsebytes(archive.read(metadata[0]))
        name = re.sub(r"[-_.]+", "-", package["Name"]).lower()
        if name in found or expected.get(name) != package["Version"]:
            raise ValueError("Wheel outside runtime lock: " + wheel.name)
        found.add(name)
        result.append(wheel.resolve())
    if found != set(expected):
        raise ValueError("Missing locked wheels: " + ", ".join(sorted(set(expected) - found)))
    return result


def extract_python(archive_path: Path, destination: Path, lock: dict) -> None:
    if digest(archive_path) != lock["sha256"] or archive_path.stat().st_size != lock["size"]:
        raise ValueError("Official Python archive hash/size mismatch")
    with zipfile.ZipFile(archive_path) as archive:
        seen = set()
        for item in archive.infolist():
            name = portable_name(item.filename.rstrip("/"))
            if name.casefold() in seen or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Unexpected duplicate/link in Python archive")
            seen.add(name.casefold())
        if lock["license"] not in archive.namelist():
            raise ValueError("Official PSF licence missing")
        archive.extractall(destination)
    # _pth ignores registry, PYTHONPATH, user site and the current working directory.
    (destination / "python312._pth").write_text("python312.zip\n.\n../app\n", encoding="utf-8")


def build(args) -> Path:
    if sys.version_info[:2] != (3, 12) or struct.calcsize("P") != 8 or sysconfig.get_platform() != "win-amd64":
        raise ValueError("Build the portable with Windows x64 Python 3.12")
    root = args.root.resolve(strict=True)
    validate_wheel(args.wheel, policy_root=root)
    names = selected_files(root, "portable")
    wheels = locked_wheels(args.wheelhouse, root / "requirements.lock")
    lock = json.loads((root / "portable-python.lock.json").read_text(encoding="utf-8"))
    if (lock.get("version") != "3.12.10" or lock.get("platform") != "Windows-x64"
            or lock.get("url") != "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"):
        raise ValueError("Unsupported portable Python lock")
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(root):
        raise ValueError("Choose a new portable directory outside the source tree")
    cache = args.python_archive
    if cache is None:
        cache = args.wheelhouse.parent / "python-3.12.10-embed-amd64.zip"
        if not cache.exists():
            with urllib.request.urlopen(lock["url"], timeout=60) as response:
                cache.write_bytes(response.read())
    # Check every input before creating a distributable destination.
    if digest(cache) != lock["sha256"] or cache.stat().st_size != lock["size"]:
        raise ValueError("Python archive hash/size mismatch")
    output.mkdir(parents=True)
    runtime = output / "runtime"
    runtime.mkdir()
    extract_python(cache, runtime, lock)
    app = output / "app"
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-index",
                    "--no-deps", "--no-compile", "--target", str(app), *map(str, wheels),
                    str(args.wheel.resolve())], check=True)
    # pip's direct_url.json contains local build paths, not part of the application.
    for path in app.glob("*.dist-info/direct_url.json"):
        path.unlink()
    for name in names:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(checked_file(root, name), target)
    (output / "scripts").mkdir(exist_ok=True)
    shutil.copyfile(root / "scripts/portable-launcher.py", output / "launch.py")
    shutil.copyfile(root / "scripts/check-portable.py", output / "scripts/check-portable.py")
    for name in ("portable_host.py", "portable_window.py", "portable_update.py"):
        shutil.copyfile(checked_file(root, "scripts/" + name), output / "scripts" / name)
    # Windows accepts PNG-compressed ICO entries; the original brand bitmap is unchanged.
    icon = (root / "fat_studio/web/brand/logo_vanguard.png").read_bytes()
    width, height = struct.unpack(">II", icon[16:24])
    if not 0 < width <= 256 or not 0 < height <= 256:
        raise ValueError("Portable icon must fit a 256 px ICO entry")
    (output / "vanguard.ico").write_bytes(struct.pack("<HHHBBBBHHII", 0, 1, 1, width % 256, height % 256,
                                                     0, 0, 1, 32, len(icon), 22) + icon)
    (output / "Start-FAT.cmd").write_text(
        '@echo off\r\nsetlocal\r\nif "%~1"=="" (\r\n'
        '  start "" "%~dp0runtime\\pythonw.exe" -B -X utf8 "%~dp0launch.py" --gui\r\n'
        '  exit /b 0\r\n)\r\n"%~dp0runtime\\python.exe" -B -X utf8 "%~dp0launch.py" %*\r\n'
        'if errorlevel 1 (\r\n  echo.\r\n  echo Voir le diagnostic et docs\\INSTALLATION.md.\r\n  pause\r\n)\r\nendlocal\r\n',
        encoding="ascii", newline="")
    (output / "Vanguard-FAT-Studio.cmd").write_text(
        '@echo off\r\ncall "%~dp0Start-FAT.cmd" %*\r\n', encoding="ascii", newline="")
    # Retain original wheels and their licences, so dependencies remain replaceable.
    distribution_wheels = output / "wheels"
    distribution_wheels.mkdir()
    for wheel in [*wheels, args.wheel.resolve()]:
        shutil.copyfile(wheel, distribution_wheels / wheel.name)
    shutil.copyfile(root / "requirements.lock", output / "requirements.lock")
    for path in output.rglob("*"):
        if path.is_file() and path.suffix.lower() not in {".zip", ".whl", ".dll", ".pyd", ".exe"}:
            check_content(path.relative_to(output).as_posix(), path.read_bytes())
    manifest = {"schema": 1, "platform": "Windows-x64", "python": lock["version"],
                "python_archive_sha256": lock["sha256"], "application_wheel_sha256": digest(args.wheel),
                **application_identity(root, args.wheel),
                "files": file_manifest(output)}
    (output / "portable-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    subprocess.run([str(runtime / "python.exe"), "-B", "-X", "utf8", str(output / "launch.py"), "--check"],
                   check=True, cwd=output.parent)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--wheel", type=Path, required=True, help="New, reviewed public application wheel")
    parser.add_argument("--wheelhouse", type=Path, required=True, help="Exactly the requirements.lock wheels")
    parser.add_argument("--python-archive", type=Path, help="Already downloaded official pinned embed ZIP")
    parser.add_argument("--output", type=Path, required=True, help="New directory outside the source tree")
    args = parser.parse_args()
    try:
        print(json.dumps({"portable": str(build(args))}))
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
