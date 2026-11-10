"""Operator entry points. Authorization is a local, explicit operator action."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import re
import tempfile
import uuid
import sys
import threading
import time
import webbrowser
from pathlib import Path

from . import __version__
from .branding import APP_NAME
from .models import PLCConfig
from .security import MachinePolicy, TargetDenied, validate_endpoint


def _new_directory(destination: Path, build) -> dict:
    destination = destination.expanduser().absolute()
    if destination.exists() or destination.is_symlink() or destination.is_junction():
        raise ValueError("Choisir un nouveau dossier ; aucun projet existant n'est écrasé.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    expected = destination.resolve()
    with tempfile.TemporaryDirectory(prefix=".fat-project-stage-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "project"
        assert staged.resolve().is_relative_to(Path(temporary).resolve())
        result = build(staged)
        if destination.exists() or destination.resolve() != expected:
            raise ValueError("La destination du projet a changé pendant la préparation.")
        staged.rename(destination)
    return {**result, "path": str(destination)}


def _new_project(args) -> int:
    from .demo_lab import demo_lab_project
    from .models import Project
    from .storage import Store

    project = demo_lab_project() if args.demo else Project(id="p-" + uuid.uuid4().hex[:16], name=args.name)
    project.name = args.name
    def build(path):
        store = Store(path)
        try:
            store.save_project(project)
        finally:
            store.close()
        return dict(status="created", project_id=project.id, demo=args.demo, connected=False)
    print(json.dumps(_new_directory(args.directory, build), ensure_ascii=False, indent=2))
    return 0


def _archive_create(args) -> int:
    from .archive import export_archive
    from .storage import Store
    from .workspaces import active_workspace, workspace_path

    if args.output.exists():
        raise ValueError("Choisir un nouveau fichier d'archive.")
    root = _data_dir(args)
    store = Store(workspace_path(root, active_workspace(root)))
    try:
        project = store.last_project()
        if project is None:
            raise ValueError("Aucun projet dans ce dossier.")
        data = export_archive(store, project)
    finally:
        store.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(data)
    print(json.dumps(dict(output=str(args.output), bytes=len(data), project_id=project.id), indent=2))
    return 0


def _archive_restore(args) -> int:
    from .archive import prepare_archive, restore_archive
    from .storage import Store

    plan = prepare_archive(args.file.read_bytes())
    def build(path):
        store = Store(path)
        try:
            project = restore_archive(store, plan)
        finally:
            store.close()
        return dict(status="restored", project_id=project.id, archived_runs=plan.run_count, connected=False,
                    archive_sha256=plan.archive_sha256)
    print(json.dumps(_new_directory(args.output, build), ensure_ascii=False, indent=2))
    return 0


def default_data_dir() -> Path:
    configured = os.environ.get("FAT_STUDIO_DATA")
    if configured:
        return Path(configured).expanduser().resolve()
    if sys.platform == "win32":
        return (Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "FATStudio").resolve()
    return (Path.home() / ".fat-studio").resolve()


def _data_dir(args) -> Path:
    return Path(args.data_dir).expanduser().resolve() if args.data_dir else default_data_dir()


def _port(value: str) -> int:
    result = int(value)
    if not 1 <= result <= 65535:
        raise argparse.ArgumentTypeError("Le port doit être compris entre 1 et 65535.")
    return result


def _doctor(args) -> int:
    packages = {}
    missing = []
    for name in ("fastapi", "uvicorn", "pydantic", "asyncua"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
    web = Path(__file__).resolve().parent / "web"
    directory = _data_dir(args)
    policy_error = None
    try:
        policy = MachinePolicy(directory / "machine-policy.json").entries()
    except (ValueError, OSError) as exc:
        policy, policy_error = [], str(exc)
    result = {
        "application": APP_NAME, "version": __version__, "python": platform.python_version(),
        "platform": platform.platform(), "dependencies": packages, "missing_dependencies": missing,
        "web_ready": (web / "index.html").is_file(), "web_path": str(web), "data_dir": str(directory),
        "authorized_target_count": len(policy), "policy_error": policy_error,
        "siemens_validation": "Non vérifiée par doctor : effectuer la qualification sur le poste cible.",
    }
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"{APP_NAME} {__version__} · Python {result['python']} · {result['platform']}")
        print(f"Interface compilée : {'OK' if result['web_ready'] else 'ABSENTE'}")
        print(f"Données : {directory}")
        print(f"Cibles autorisées sur ce poste : {len(policy)}")
        for name, version in packages.items():
            print(f"  {name} {version}")
        if missing:
            print("Dépendances absentes : " + ", ".join(missing))
        if policy_error:
            print("Politique locale invalide : " + policy_error)
        print(result["siemens_validation"])
    return 0 if result["web_ready"] and not missing and not policy_error else 1


def _authorize_target(args) -> int:
    validate_endpoint(args.endpoint)
    if not args.isolated_virtual_adapter:
        raise TargetDenied("Confirmez d'abord l'adaptateur PLCSIM local isolé, puis fournissez --isolated-virtual-adapter.")
    name = args.name.strip()
    application_uri = args.application_uri.strip()
    if not name or not application_uri:
        raise TargetDenied("Le nom de l'instance et son ApplicationUri observée sont obligatoires.")
    fingerprint = args.server_certificate_sha256.lower().replace(":", "")
    if fingerprint and not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise TargetDenied("Empreinte SHA-256 invalide : 64 caractères hexadécimaux attendus.")
    if not args.allow_insecure and not fingerprint:
        raise TargetDenied("Fournissez l'empreinte serveur pour SignAndEncrypt, ou autorisez explicitement None avec --allow-insecure sur le réseau virtuel isolé.")
    if (args.username_env or args.password_env) and args.allow_insecure:
        raise TargetDenied("Les identifiants utilisateur exigent SignAndEncrypt ; retirer --allow-insecure.")
    certificate = str(Path(args.client_certificate).expanduser().resolve()) if args.client_certificate else ""
    private_key = str(Path(args.client_private_key).expanduser().resolve()) if args.client_private_key else ""
    if bool(certificate) != bool(private_key):
        raise TargetDenied("Le certificat client et sa clé privée doivent être fournis ensemble.")
    if not args.allow_insecure and not certificate:
        raise TargetDenied("SignAndEncrypt exige aussi --client-certificate et --client-private-key.")
    if bool(args.username_env) != bool(args.password_env):
        raise TargetDenied("Les noms des variables username/password doivent être fournis ensemble.")
    for filename in (certificate, private_key):
        if filename and not Path(filename).is_file():
            raise TargetDenied("Fichier du certificat client ou de la clé privée introuvable.")
    # Reuse the public schema, including environment-name validation.
    plc = PLCConfig(mode="opcua", endpoint=args.endpoint, expected_application_uri=application_uri,
                    approved_virtual_target=name, server_certificate_sha256=fingerprint,
                    security_policy="None" if args.allow_insecure else "Basic256Sha256",
                    username_env=args.username_env, password_env=args.password_env,
                    client_certificate=certificate, client_private_key=private_key)
    confirmation = f"{name} @ {args.endpoint}"
    print("Autorisation d'une cible FAT locale")
    print(f"Cible : {confirmation}\nApplicationUri : {application_uri}")
    print("Vérifiez que cette adresse appartient à l'instance PLCSIM Advanced locale et à son adaptateur isolé.")
    print("Cette commande ne teste pas la topologie réseau et ne contacte pas le PLC.")
    if args.allow_insecure:
        print("Politique OPC UA None autorisée explicitement pour cette cible ; aucun identifiant utilisateur ne sera transmis.")
    typed = input(f"Saisissez exactement « {confirmation} » pour enregistrer : ")
    if typed != confirmation:
        raise TargetDenied("Confirmation différente : aucune cible n'a été enregistrée.")
    entry = {key: getattr(plc, key) for key in (
        "endpoint", "expected_application_uri", "approved_virtual_target", "server_certificate_sha256",
        "username_env", "password_env", "client_certificate", "client_private_key",
    )}
    entry.update(isolated_virtual_adapter_confirmed=True, allow_insecure=args.allow_insecure)
    policy_path = _data_dir(args) / "machine-policy.json"
    MachinePolicy(policy_path).add(entry)
    print(f"Cible enregistrée dans {policy_path}. Dans Connexion, utilisez « Mes cibles sur ce poste » pour préparer le projet FAT.")
    return 0


def _serve(args) -> int:
    from .app import create_app
    import uvicorn

    directory = _data_dir(args)
    directory.mkdir(parents=True, exist_ok=True)
    app = create_app(data_dir=directory)
    config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info", access_log=False)
    server = uvicorn.Server(config)
    url_host = f"[{args.host}]" if ":" in args.host else args.host
    url = f"http://{url_host}:{args.port}"
    if not args.no_browser:
        def open_when_ready():
            deadline = time.monotonic() + 20
            while not server.started and not server.should_exit and time.monotonic() < deadline:
                time.sleep(0.1)
            if server.started and not server.should_exit:
                webbrowser.open(url)
        threading.Thread(target=open_when_ready, name="fat-browser", daemon=True).start()
    print(f"{APP_NAME} : {url}\nDonnées : {directory}\nArrêt du service : Ctrl+C")
    server.run()
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="vanguard-fat-studio", description=f"{APP_NAME}, banc FAT local : démonstration et simulation pour essais PLCSIM Advanced.")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command")
    serve = commands.add_parser("serve", help="Démarrer l'interface locale")
    serve.add_argument("--host", choices=("127.0.0.1", "localhost", "::1"), default="127.0.0.1")
    serve.add_argument("--port", type=_port, default=8765)
    serve.add_argument("--data-dir", type=Path)
    serve.add_argument("--no-browser", action="store_true")
    serve.set_defaults(handler=_serve)
    doctor = commands.add_parser("doctor", help="Vérifier l'installation, sans contacter Siemens")
    doctor.add_argument("--data-dir", type=Path)
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(handler=_doctor)
    create = commands.add_parser("new-project", help="Créer un dossier de projet FAT local neuf")
    create.add_argument("directory", type=Path)
    create.add_argument("--name", required=True)
    create.add_argument("--demo", action="store_true")
    create.set_defaults(handler=_new_project)
    archive_create = commands.add_parser("archive-create", help="Archiver un dossier fermé ; pour un banc actif utiliser le client IA archive-export")
    archive_create.add_argument("--data-dir", type=Path, required=True)
    archive_create.add_argument("--output", type=Path, required=True)
    archive_create.set_defaults(handler=_archive_create)
    archive_restore = commands.add_parser("archive-restore", help="Restaurer une archive dans un nouveau dossier, au repos")
    archive_restore.add_argument("file", type=Path)
    archive_restore.add_argument("--output", type=Path, required=True)
    archive_restore.set_defaults(handler=_archive_restore)
    authorize = commands.add_parser("authorize-target", help="Autoriser une cible virtuelle dans la politique du poste")
    authorize.add_argument("--endpoint", required=True)
    authorize.add_argument("--application-uri", required=True)
    authorize.add_argument("--name", required=True)
    authorize.add_argument("--server-certificate-sha256", default="")
    authorize.add_argument("--client-certificate", default="")
    authorize.add_argument("--client-private-key", default="")
    authorize.add_argument("--username-env", default="")
    authorize.add_argument("--password-env", default="")
    authorize.add_argument("--isolated-virtual-adapter", action="store_true")
    authorize.add_argument("--allow-insecure", action="store_true")
    authorize.add_argument("--data-dir", type=Path)
    authorize.set_defaults(handler=_authorize_target)
    return root


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    arguments = sys.argv[1:] if argv is None else argv
    args = parser().parse_args(arguments if arguments else ["serve"])
    try:
        return args.handler(args)
    except (ValueError, OSError, EOFError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
