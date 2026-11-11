"""Context-bound, loopback-only FAT client for a user's local coding assistant."""

from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .security import atomic_json


def local_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        host = ipaddress.ip_address(parsed.hostname or "")
        if (parsed.scheme != "http" or not host.is_loopback or parsed.username is not None
                or parsed.password is not None or parsed.path not in ("", "/") or parsed.query
                or parsed.fragment or not parsed.port):
            raise ValueError
        return value.rstrip("/")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Utiliser http://127.0.0.1:PORT ou http://[::1]:PORT, sans chemin ni identifiant.") from exc


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirection HTTP refusée ; vérifier l'URL du service FAT local.")


class LocalClient:
    def __init__(self, url: str, context_path: Path):
        self.url = local_url(url)
        self.context_path = context_path
        # A local exchange must not go through an environment-configured proxy.
        self.opener = build_opener(ProxyHandler({}), NoRedirects())

    def request(self, path: str, method="GET", body=None, headers=None, *, binary=False):
        if not path.startswith("/api/") or "\r" in path or "\n" in path:
            raise ValueError("Chemin de l'API locale invalide.")
        payload = body if isinstance(body, bytes) else None if body is None else json.dumps(body, allow_nan=False, ensure_ascii=False).encode("utf-8")
        request = Request(self.url + path, data=payload, method=method,
                          headers={**({"Content-Type": ("application/octet-stream" if path.startswith("/api/pid/inspect") else "application/zip") if isinstance(body, bytes) else "application/json"} if payload is not None else {}), **(headers or {})})
        try:
            with self.opener.open(request, timeout=120 if path.startswith("/api/pid/inspect") else 40) as response:
                data = response.read()
                return (data if binary else json.loads(data)), response.headers
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(detail).get("detail", detail)
            except (ValueError, AttributeError):
                pass
            raise ValueError(f"HTTP {error.code} : {detail}. Aucune commande n'est réessayée.") from None
        except URLError as error:
            raise ValueError(f"Service FAT local indisponible : {error.reason}. Aucune reconnexion automatique.") from None

    def baseline(self) -> dict:
        project, headers = self.request("/api/project")
        state, _ = self.request("/api/state")
        revision = headers.get("X-FAT-Project-Revision", "")
        if project["id"] != state.get("project_id") or not revision or revision != state.get("project_revision"):
            raise ValueError("Le projet a changé pendant la lecture ; relire son état avant une nouvelle action.")
        return dict(version=1, url=self.url, project_id=project["id"], project_revision=revision, run_id=state.get("run_id"))

    def capture(self) -> dict:
        baseline = self.baseline()
        atomic_json(self.context_path, baseline)
        return baseline

    def expected_headers(self) -> dict:
        if not self.context_path.is_file():
            raise ValueError("Capturer d'abord le contexte avec la commande context.")
        expected = json.loads(self.context_path.read_text(encoding="utf-8"))
        if expected != self.baseline():
            raise ValueError("Contexte périmé ; relire avant une nouvelle capture explicite.")
        return {"X-FAT-Project-ID": expected["project_id"], "X-FAT-Project-Revision": expected["project_revision"],
                "X-FAT-Run-ID": expected["run_id"] or ""}

    def mutate(self, path: str, method="POST", body=None) -> dict:
        if not self.context_path.is_file():
            raise ValueError("Capturer d'abord le contexte avec la commande context.")
        expected = json.loads(self.context_path.read_text(encoding="utf-8"))
        actual = self.baseline()
        if expected != actual:
            raise ValueError("Contexte périmé : projet, révision, essai ou URL a changé. Relire l'état puis capturer context explicitement.")
        session, _ = self.request("/api/session")
        result, response_headers = self.request(path, method, body, headers={
            "X-FAT-Token": session["token"], "X-FAT-Project-ID": expected["project_id"],
            "X-FAT-Project-Revision": expected["project_revision"], "X-FAT-Run-ID": expected["run_id"] or "",
        })
        # The successful response itself is the new baseline. Polls never replace it.
        if "project_id" in result:
            updated = dict(version=1, url=self.url, project_id=result["project_id"],
                           project_revision=result["project_revision"], run_id=result.get("run_id"))
        elif "equipment" in result and "id" in result:
            revision = response_headers.get("X-FAT-Project-Revision", "")
            if not revision:
                raise ValueError("Commande appliquée mais réponse sans révision ; relire avant toute autre action.")
            updated = dict(version=1, url=self.url, project_id=result["id"], project_revision=revision,
                           run_id=response_headers.get("X-FAT-Run-ID") or None)
        else:
            # Marker/result endpoints may return a full snapshot too; unknown responses are not adopted.
            raise ValueError("Commande appliquée mais format de contexte inattendu ; relire explicitement.")
        atomic_json(self.context_path, updated)
        return result

    def prepare(self, path: str, body) -> dict:
        """Authenticated passive operation; keep the captured context byte-for-byte."""
        expected = self.expected_headers()
        session, _ = self.request("/api/session")
        result, _ = self.request(path, "POST", body, headers={**expected, "X-FAT-Token": session["token"]})
        return result


def json_value(value: str):
    try:
        return json.loads(value, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Valeur JSON finie attendue, par exemple true, false ou 12.") from exc


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--url", type=local_url, default="http://127.0.0.1:8765")
    result.add_argument("--context", type=Path, default=Path(".local/ai-context.json"))
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("context", "health", "state", "project", "catalog", "schema", "validate", "runs", "workspaces", "workspace", "demo", "pilot", "pause", "resume", "stop", "reset"):
        commands.add_parser(name)
    commands.add_parser("pid-capabilities")
    commands.add_parser("pid-catalog")
    pid_inspect = commands.add_parser("pid-inspect")
    pid_inspect.add_argument("file", type=Path)
    pid_inspect.add_argument("--pages", default="")
    pid_inspect.add_argument("--no-ocr", action="store_true")
    pid_inspect.add_argument("--output", type=Path, required=True)
    pid_prepare = commands.add_parser("pid-prepare")
    pid_prepare.add_argument("file", type=Path)
    pid_prepare.add_argument("--select", action="append", required=True)
    pid_prepare.add_argument("--types", type=Path)
    pid_prepare.add_argument("--name", default="P&ID importé")
    pid_prepare.add_argument("--output", type=Path, required=True)
    pid_export = commands.add_parser("pid-export")
    pid_export.add_argument("--format", choices=("svg", "pdf", "png", "dxf", "dwg", "json", "graph", "graphml", "csv", "drawio"), required=True)
    pid_export.add_argument("--output", type=Path, required=True)
    for name in ("project-export", "scenarios-export", "archive-export"):
        export_file = commands.add_parser(name)
        export_file.add_argument("--output", type=Path, required=True)
        if name == "scenarios-export":
            export_file.add_argument("--scenario")
    import_scenarios = commands.add_parser("scenarios-import")
    import_scenarios.add_argument("file", type=Path)
    import_scenarios.add_argument("--mode", choices=("merge", "replace"), default="merge")
    import_archive = commands.add_parser("archive-import")
    import_archive.add_argument("file", type=Path)
    workspace_open = commands.add_parser("workspace-open")
    workspace_open.add_argument("id")
    load = commands.add_parser("load-project")
    load.add_argument("file", type=Path)
    start = commands.add_parser("start")
    start.add_argument("--scenario")
    start.add_argument("--target-confirmation", default="")
    for name in ("force", "pulse", "stimulus", "release"):
        action = commands.add_parser(name)
        action.add_argument("--tag", required=True)
        if name != "release":
            action.add_argument("--value", required=True, type=json_value)
        if name == "pulse":
            action.add_argument("--duration-ms", type=int, default=300)
        if name == "stimulus":
            action.add_argument("--unit", choices=("native", "mA", "V", "engineering", "percent"), default="native")
            action.add_argument("--diagnostic", action="store_true")
    execute = commands.add_parser("step-execute")
    execute.add_argument("id")
    observe = commands.add_parser("step-observe")
    observe.add_argument("id")
    observe.add_argument("--verdict", required=True, choices=("pass", "fail"))
    observe.add_argument("--observation", default="")
    marker = commands.add_parser("marker")
    marker.add_argument("text")
    export = commands.add_parser("export")
    export.add_argument("--run", required=True)
    export.add_argument("--kind", choices=("json", "csv", "report"), required=True)
    export.add_argument("--output", type=Path, required=True)
    return result


def main(argv=None) -> int:
    # Windows redirected terminals may default to CP1252; keep JSON valid for every project name.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = parser().parse_args(argv)
    client = LocalClient(args.url, args.context)
    try:
        command = args.command
        if command == "context":
            data = client.capture()
        elif command in ("pid-capabilities", "pid-catalog"):
            data, _ = client.request("/api/pid/" + command.removeprefix("pid-"))
        elif command in ("pid-inspect", "pid-prepare", "pid-export"):
            if args.output.exists():
                raise ValueError("Choisir un nouveau fichier de sortie ; aucun export n'est écrasé.")
            warnings = []
            if command == "pid-export":
                content, _ = client.request("/api/pid/export/" + args.format, headers=client.expected_headers(), binary=True)
            else:
                if args.file.stat().st_size > 20 * 1024 * 1024:
                    raise ValueError("Le fichier P&ID dépasse 20 Mo.")
                if command == "pid-inspect":
                    path = "/api/pid/inspect?filename=" + quote(args.file.name, safe="") + "&pages=" + quote(args.pages, safe="")
                    path += "&ocr=" + ("false" if args.no_ocr else "true")
                    result = client.prepare(path, args.file.read_bytes())
                else:
                    types = json.loads(args.types.read_text(encoding="utf-8-sig")) if args.types else {}
                    prepared = client.prepare("/api/pid/prepare", {
                        "document": json.loads(args.file.read_text(encoding="utf-8-sig")),
                        "selected_ids": args.select, "types": types, "name": args.name,
                    })
                    result = {"format": "fat-studio/project", "version": "1.0", "project": prepared["project"]}
                    warnings = prepared["warnings"]
                content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("xb") as stream:
                stream.write(content)
            data = dict(output=str(args.output), bytes=len(content), warnings=warnings)
        elif command in ("health", "state", "project", "catalog", "schema", "validate", "runs", "workspaces", "workspace"):
            data, _ = client.request("/api/" + command)
        elif command in ("project-export", "scenarios-export", "archive-export"):
            if args.output.exists():
                raise ValueError("Choisir un nouveau fichier de sortie ; aucun export n'est écrasé.")
            path = {"project-export": "/api/project/download", "scenarios-export": "/api/scenarios/export", "archive-export": "/api/project/archive"}[command]
            if command == "scenarios-export" and args.scenario:
                path = "/api/scenarios/" + quote(args.scenario, safe="") + "/export"
            content, _ = client.request(path, headers=client.expected_headers(), binary=True)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("xb") as stream:
                stream.write(content)
            data = dict(output=str(args.output), bytes=len(content))
        elif command == "scenarios-import":
            data = client.mutate("/api/scenarios/import", body=dict(package=json.loads(args.file.read_text(encoding="utf-8-sig")), mode=args.mode))
        elif command == "archive-import":
            data = client.mutate("/api/project/archive/import", body=args.file.read_bytes())
        elif command == "workspace-open":
            data = client.mutate("/api/workspaces/" + quote(args.id, safe="") + "/open", body={})
        elif command == "export":
            if args.output.exists():
                raise ValueError("Choisir un nouveau fichier de sortie ; aucun export existant n'est écrasé.")
            data, _ = client.request(f"/api/runs/{quote(args.run, safe='')}/{args.kind}", headers=client.expected_headers(), binary=True)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("xb") as stream:
                stream.write(data)
            data = dict(output=str(args.output), bytes=len(data), run_id=args.run, kind=args.kind)
        elif command in ("demo", "pilot"):
            data = client.mutate(f"/api/{command}/load", body={})
        elif command == "load-project":
            data = client.mutate("/api/project/import", body=json.loads(args.file.read_text(encoding="utf-8-sig")))
        elif command == "start":
            data = client.mutate("/api/run/start", body={"scenario_id": args.scenario, "target_confirmation": args.target_confirmation})
        elif command in ("pause", "resume", "stop", "reset"):
            data = client.mutate("/api/run/" + command, body={})
        elif command in ("force", "pulse", "stimulus"):
            body = dict(tag_id=args.tag, value=args.value)
            if command == "pulse":
                body["duration_ms"] = args.duration_ms
            if command == "stimulus":
                body.update(unit=args.unit, diagnostic=args.diagnostic)
            data = client.mutate("/api/force" + ("/" + command if command != "force" else ""), body=body)
        elif command == "release":
            data = client.mutate("/api/force/" + quote(args.tag, safe=""), "DELETE")
        elif command == "step-execute":
            data = client.mutate("/api/run/steps/" + quote(args.id, safe="") + "/execute", body={})
        elif command == "step-observe":
            data = client.mutate("/api/run/steps/" + quote(args.id, safe="") + "/observe",
                                 body=dict(verdict=args.verdict, observation=args.observation))
        elif command == "marker":
            data = client.mutate("/api/markers", body=dict(message=args.text))
        else:
            raise ValueError("Commande locale inconnue.")
        print(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
