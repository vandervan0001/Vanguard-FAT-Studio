"""Double-click entry point for the self-contained Vanguard FAT Studio runtime."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import runpy
import sys
import webbrowser


def main() -> int:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--gui", action="store_true", help="Show the native Windows launcher")
    parser.add_argument("--quit", action="store_true", help="Stop the verified instance for this portable and data directory")
    parser.add_argument("--status", action="store_true", help="Print the verified running instance")
    parser.add_argument("--check", action="store_true", help="Verify files and exit without starting a server")
    args = parser.parse_args()
    try:
        if not 1 <= args.port <= 65535:
            raise ValueError("Le port doit être compris entre 1 et 65535.")
        verifier = runpy.run_path(str(root / "scripts" / "check-portable.py"))
        count = verifier["validate_portable"](root)
        if args.check:
            print(f"Portable verified: {count} files")
            return 0
        from fat_studio.cli import default_data_dir

        sys.path.insert(0, str(root / "scripts"))
        from portable_host import InstanceLease, PortableService, build_identity, existing_instance, owned_request

        data = (args.data_dir or default_data_dir()).expanduser().resolve()
        if data.is_relative_to(root):
            raise ValueError("Choose a data directory outside the portable runtime")
        identity = build_identity(root, data, args.port)
        lease = InstanceLease(data)
        if not lease.acquire():
            record = existing_instance(lease, identity)
            if args.quit:
                owned_request(record, "stop")
            elif args.status:
                print(json.dumps(owned_request(record)))
            elif not args.no_browser:
                webbrowser.open(f"http://127.0.0.1:{record['port']}")
            return 0
        if args.quit or args.status:
            lease.close()
            raise ValueError("Aucune instance de ce portable n’est ouverte pour ce dossier.")
        service = PortableService(root, data, args.port, lease, identity)
        if args.gui:
            if os.name != "nt":
                lease.close()
                raise ValueError("La fenêtre native est disponible sous Windows.")
            log = (data / "portable-launcher.log").open("a", encoding="utf-8", buffering=1)
            sys.stdout = sys.stderr = log
            from portable_window import show
            try:
                return show(service, verifier["validate_portable"], not args.no_browser)
            finally:
                service.stop()
                if service.thread:
                    service.thread.join(timeout=30)
                else:
                    lease.close()
        service.start()
        try:
            if not service.wait_ready():
                raise ValueError(service.error)
            print(f"Vanguard FAT Studio : {service.url}\nDonnées : {data}\nArrêt : Ctrl+C ou launch.py --quit")
            if not args.no_browser:
                webbrowser.open(service.url)
            while not service.finished.wait(.2):
                pass
        except KeyboardInterrupt:
            service.stop()
        finally:
            service.stop()
            service.thread.join(timeout=30)
        if service.error:
            raise ValueError(service.error)
        return 0
    except (ValueError, OSError) as exc:
        if args.gui and os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(exc), "Vanguard FAT Studio", 0x10)
        if sys.stderr:
            print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
