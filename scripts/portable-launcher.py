"""Double-click entry point for the self-contained Vanguard FAT Studio runtime."""

from __future__ import annotations

import argparse
from pathlib import Path
import runpy
import sys


def main() -> int:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--check", action="store_true", help="Verify files and exit without starting a server")
    args = parser.parse_args()
    try:
        verifier = runpy.run_path(str(root / "scripts" / "check-portable.py"))
        count = verifier["validate_portable"](root)
        if args.check:
            print(f"Portable verified: {count} files")
            return 0
        from fat_studio.cli import default_data_dir, main as fat_main

        data = (args.data_dir or default_data_dir()).expanduser().resolve()
        if data.is_relative_to(root):
            raise ValueError("Choose a data directory outside the portable runtime")
        arguments = ["serve", "--host", "127.0.0.1", "--port", str(args.port), "--data-dir", str(data)]
        if args.no_browser:
            arguments.append("--no-browser")
        return fat_main(arguments)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
