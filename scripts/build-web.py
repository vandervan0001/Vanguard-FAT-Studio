#!/usr/bin/env python3
"""Copy the Vite production output into the Python package, without a CDN."""

from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[1]
source = root / "frontend" / "dist"
destination = root / "fat_studio" / "web"
build_cache = root / "build" / "lib" / "fat_studio" / "web"
if not (source / "index.html").is_file():
    print("Interface absente. Exécuter npm ci puis npm run build dans frontend/.", file=sys.stderr)
    raise SystemExit(1)
for output in (destination, build_cache):
    current = root
    for part in output.relative_to(root).parts:
        current = current / part
        if current.is_symlink() or current.is_junction() or not current.resolve().is_relative_to(root):
            raise SystemExit(f"Refus de remplacer un lien ou un chemin sortant du dépôt : {current}")
        if current.exists() and not current.is_dir():
            raise SystemExit(f"Refus de remplacer une sortie qui n’est pas un dossier : {current}")
if build_cache.exists():
    shutil.rmtree(build_cache)
if destination.exists():
    shutil.rmtree(destination)
shutil.copytree(source, destination)
print(f"Interface locale intégrée : {destination}")
