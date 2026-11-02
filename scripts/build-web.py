#!/usr/bin/env python3
"""Copy the Vite production output into the Python package, without a CDN."""

from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[1]
source = root / "frontend" / "dist"
destination = root / "fat_studio" / "web"
if not (source / "index.html").is_file():
    print("Interface absente. Exécuter npm ci puis npm run build dans frontend/.", file=sys.stderr)
    raise SystemExit(1)
if destination.is_symlink():
    raise SystemExit("Refus de remplacer un lien symbolique fat_studio/web.")
if destination.exists():
    shutil.rmtree(destination)
shutil.copytree(source, destination)
print(f"Interface locale intégrée : {destination}")
