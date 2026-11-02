"""Same-origin local HTTP service. The browser never connects directly to a PLC."""

from __future__ import annotations

import asyncio
import json
import math
import os
import secrets
import sqlite3
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import __version__
from .catalog import CATALOG
from .demo import demo_project
from .mapping import export_mapping, import_mapping
from .models import Project, validate_project
from .reporting import csv_stream, html_report, json_stream
from .runtime import RunConflict, Runtime
from .security import MachinePolicy, TargetDenied
from .storage import Store


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class NewProject(Payload):
    name: str = Field(min_length=1, max_length=200)


class StartRequest(Payload):
    scenario_id: str | None = None
    target_confirmation: str = Field(default="", max_length=1100)


class ForceRequest(Payload):
    tag_id: str = Field(min_length=1, max_length=80)
    value: Any


class FaultRequest(Payload):
    equipment_id: str = Field(min_length=1, max_length=80)
    kind: str = Field(min_length=1, max_length=80)
    value: Any = None


class MarkerRequest(Payload):
    message: str = Field(min_length=1, max_length=4000)


class ResultRequest(Payload):
    verdict: Literal["pass", "fail", "not_evaluated"]
    comment: str = Field(default="", max_length=10000)


class MappingRequest(Payload):
    csv: str = Field(max_length=2_000_000)


def default_data_dir() -> Path:
    if os.environ.get("FAT_STUDIO_DATA"):
        return Path(os.environ["FAT_STUDIO_DATA"]).expanduser()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "FATStudio"
    return Path.home() / ".fat-studio"


def create_app(data_dir: Path | None = None, *, adapter_factory=None) -> FastAPI:
    folder = (data_dir or default_data_dir()).resolve()
    token = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        store = Store(folder)
        runtime = None
        try:
            startup_error = None
            try:
                project = store.last_project()
            except (ValueError, OSError, KeyError) as exc:
                project = demo_project()
                project.id = "recovery-" + uuid.uuid4().hex[:12]
                project.name = "Récupération — " + project.name
                startup_error = "Le dernier projet est illisible et a été conservé intact. " + str(exc)
            needs_save = project is None or startup_error is not None
            if project is None:
                project = demo_project()
            policy = MachinePolicy(folder / "machine-policy.json")
            runtime = Runtime(store, project, policy, adapter_factory)
            # Opening an existing project is not a save: retain its previous revision.
            if needs_save:
                store.save_project(project)
            if startup_error:
                runtime.error = startup_error
                runtime.event("project_recovery", startup_error)
            application.state.store = store
            application.state.runtime = runtime
            application.state.policy = policy
            application.state.mutations = asyncio.Lock()
            yield
        finally:
            try:
                if runtime:
                    await runtime.close()
            finally:
                store.close()

    app = FastAPI(title="FAT Studio local API", version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url="/api/openapi.json")

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        host = request.headers.get("host", "")
        try:
            hostname = urlsplit("http://" + host).hostname
        except ValueError:
            hostname = None
        if hostname not in ("127.0.0.1", "localhost", "::1"):
            return JSONResponse({"detail": "Host refusé : FAT Studio est réservé au poste local."}, status_code=403)
        origin = request.headers.get("origin")
        allowed_origins = {f"http://{host}", f"https://{host}"}
        development_origin = os.environ.get("FAT_STUDIO_DEV_ORIGIN", "")
        if development_origin and urlsplit(development_origin).hostname in ("127.0.0.1", "localhost", "::1"):
            allowed_origins.add(development_origin)
        if origin and origin not in allowed_origins:
            return JSONResponse({"detail": "Origine externe refusée."}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Requête cross-site refusée."}, status_code=403)
        mutation = request.method not in ("GET", "HEAD", "OPTIONS")
        if mutation:
            supplied = request.headers.get("x-fat-token", "")
            if not supplied.isascii() or not secrets.compare_digest(supplied, token):
                return JSONResponse({"detail": "Session locale expirée ou jeton absent ; recharger l'interface."}, status_code=403)
            # Bounded body read also handles chunked input without trusting Content-Length.
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 5 * 1024 * 1024:
                    return JSONResponse({"detail": "La requête dépasse 5 Mo."}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        guarded_read = request.method == "GET" and request.url.path == "/api/mapping"
        if mutation or guarded_read:
            async with app.state.mutations:
                project_id = request.headers.get("x-fat-project-id")
                run_action = request.url.path.startswith(("/api/run/", "/api/force", "/api/fault", "/api/markers", "/api/result"))
                guarded = guarded_read or run_action or (request.method == "PUT" and request.url.path == "/api/project") or (
                    request.method == "POST" and request.url.path == "/api/mapping")
                if guarded and project_id and project_id != app.state.runtime.project.id:
                    return JSONResponse({"detail": "Le projet actif a changé dans un autre onglet ; recharger avant d'agir."}, status_code=409)
                revision = request.headers.get("x-fat-project-revision")
                if guarded and revision and revision != app.state.runtime.project_revision:
                    return JSONResponse({"detail": "Le projet a été modifié dans un autre onglet ; conserver le brouillon et recharger avant d'agir."}, status_code=409)
                run_id = request.headers.get("x-fat-run-id")
                if run_action and run_id is not None and run_id != (app.state.runtime.run_id or ""):
                    return JSONResponse({"detail": "L'essai actif a changé dans un autre onglet ; recharger avant d'agir."}, status_code=409)
                response = await call_next(request)
        else:
            response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RunConflict)
    async def conflict_handler(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(TargetDenied)
    async def target_handler(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def validation_handler(request, exc):
        # Do not echo a whole imported project per error, or let a rejected NaN/
        # Infinity in Pydantic's input field break JSONResponse serialization.
        details = [{key: value for key, value in error.items() if key != "input"} for error in exc.errors()]
        return JSONResponse({"detail": jsonable_encoder(details, custom_encoder={
            ValueError: str, float: lambda value: value if math.isfinite(value) else str(value),
        })}, status_code=422)

    @app.exception_handler(OSError)
    @app.exception_handler(sqlite3.Error)
    async def storage_handler(request, exc):
        await app.state.runtime.storage_failed(exc)
        return JSONResponse({"detail": "Accès aux fichiers ou à l'historique impossible ; "
                             "l'essai actif est interrompu pour conserver la traçabilité. " + str(exc)}, status_code=503)

    @app.exception_handler(ValueError)
    async def value_handler(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(KeyError)
    async def key_handler(request, exc):
        return JSONResponse({"detail": f"Objet introuvable : {exc}"}, status_code=404)

    @app.exception_handler(FileNotFoundError)
    async def file_handler(request, exc):
        return JSONResponse({"detail": "Fichier de projet introuvable."}, status_code=404)

    @app.get("/api/session")
    async def session():
        return {"token": token}

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": __version__, "mode": "local-fat", "schema_version": "1.0"}

    @app.get("/api/catalog")
    async def catalog():
        return CATALOG

    @app.get("/api/schema")
    async def schema():
        return Project.model_json_schema()

    @app.get("/api/project")
    async def current_project(response: Response):
        response.headers["X-FAT-Project-Revision"] = app.state.runtime.project_revision
        return app.state.runtime.project

    async def replace_project(project: Project, response: Response) -> Project:
        runtime = app.state.runtime
        async with runtime.lock:
            runtime.ensure_editable()
            # Validate structure now; semantic errors stay visible and block Run, not drawing.
            if runtime.adapter:
                await runtime.adapter.disconnect()
            app.state.store.save_project(project)
            runtime.set_project(project)
            runtime.adapter = None
            response.headers["X-FAT-Project-Revision"] = runtime.project_revision
            return runtime.project

    @app.put("/api/project")
    async def save_project(project: Project, response: Response):
        return await replace_project(project, response)

    @app.post("/api/project/import")
    async def import_project(project: Project, response: Response):
        return await replace_project(project, response)

    @app.get("/api/project/download")
    async def download_project():
        project = app.state.runtime.project
        return Response(project.model_dump_json(indent=2), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{project.id}.json"'})

    @app.get("/api/projects")
    async def projects():
        return app.state.store.list_projects()

    @app.post("/api/projects")
    async def new_project(body: NewProject, response: Response):
        project = Project(id="p-" + uuid.uuid4().hex[:16], name=body.name)
        return await replace_project(project, response)

    @app.post("/api/projects/{project_id}/load")
    async def load_project(project_id: str, response: Response):
        return await replace_project(app.state.store.load_project(project_id), response)

    @app.post("/api/demo/load")
    async def load_demo(response: Response):
        return await replace_project(demo_project(), response)

    @app.get("/api/validate")
    async def validate():
        result = validate_project(app.state.runtime.project)
        if app.state.runtime.project.plc.mode == "opcua":
            try:
                app.state.policy.authorize(app.state.runtime.project.plc)
            except ValueError as exc:
                result["errors"].append({"path": "plc", "message": str(exc)})
                result["valid"] = False
            result["warnings"].append({"path": "plc", "message": "L'existence, les types et les droits des NodeIds seront vérifiés en ligne au démarrage, avant écriture."})
        return result

    @app.get("/api/mapping")
    async def mapping_export():
        return Response(export_mapping(app.state.runtime.project), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="fat-mapping.csv"',
                                 "X-FAT-Project-Revision": app.state.runtime.project_revision})

    @app.post("/api/mapping")
    async def mapping_import(body: MappingRequest, response: Response):
        return await replace_project(import_mapping(app.state.runtime.project, body.csv), response)

    @app.get("/api/state")
    async def state():
        async with app.state.runtime.lock:
            return app.state.runtime.snapshot()

    @app.post("/api/run/start")
    async def start(body: StartRequest):
        return await app.state.runtime.start(body.scenario_id, body.target_confirmation)

    @app.post("/api/run/pause")
    async def pause():
        return await app.state.runtime.pause()

    @app.post("/api/run/resume")
    async def resume():
        return await app.state.runtime.resume()

    @app.post("/api/run/stop")
    async def stop():
        return await app.state.runtime.stop()

    @app.post("/api/run/reset")
    async def reset():
        return await app.state.runtime.reset()

    @app.post("/api/force")
    async def force(body: ForceRequest):
        return await app.state.runtime.force(body.tag_id, body.value)

    @app.delete("/api/force/{tag_id}")
    async def release(tag_id: str):
        return await app.state.runtime.release(tag_id)

    @app.post("/api/fault")
    async def fault(body: FaultRequest):
        return await app.state.runtime.fault(body.equipment_id, body.kind, body.value)

    @app.delete("/api/fault/{equipment_id}")
    async def clear_fault(equipment_id: str):
        return await app.state.runtime.clear_fault(equipment_id)

    @app.post("/api/markers")
    async def marker(body: MarkerRequest):
        return await app.state.runtime.marker(body.message)

    @app.post("/api/result")
    async def result(body: ResultRequest):
        return await app.state.runtime.set_result(body.verdict, body.comment)

    @app.get("/api/runs")
    async def runs():
        result = app.state.store.runs()
        for item in result:
            item.update(json.loads(item.pop("result_json")))
        return result

    def export(run_id: str | None, kind: str):
        if run_id is None:
            raise HTTPException(400, "Aucun essai à exporter.")
        store = app.state.store
        run = store.run(run_id)  # Capture one finite evidence snapshot before response headers.
        disposition = {"Content-Disposition": f'attachment; filename="{run_id}.{kind if kind != "report" else "html"}"'}
        if kind == "csv":
            return StreamingResponse(csv_stream(store, run_id, run=run), media_type="text/csv", headers=disposition)
        if kind == "json":
            return StreamingResponse(json_stream(store, run_id, run=run), media_type="application/json", headers=disposition)
        if kind == "report":
            return HTMLResponse(html_report(store, run_id, run=run), headers=disposition)
        raise HTTPException(404, "Format inconnu.")

    @app.get("/api/export/{kind}")
    async def current_export(kind: str):
        return export(app.state.runtime.run_id, kind)

    @app.get("/api/runs/{run_id}/{kind}")
    async def archived_export(run_id: str, kind: str):
        return export(run_id, kind)

    @app.get("/api/connection/policy")
    async def connection_policy():
        return {"targets": [{"endpoint": entry.get("endpoint"), "name": entry.get("approved_virtual_target")}
                             for entry in app.state.policy.entries()], "editable_from_browser": False}

    web_dir = Path(__file__).parent / "web"
    if (web_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=web_dir / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    async def index():
        if (web_dir / "index.html").exists():
            return FileResponse(web_dir / "index.html", headers={"Cache-Control": "no-cache"})
        return HTMLResponse("<h1>FAT Studio</h1><p>Interface absente. Exécuter npm ci, npm run build dans frontend, puis python scripts/build-web.py.</p>", status_code=503)

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon():
        if (web_dir / "favicon.svg").is_file():
            return FileResponse(web_dir / "favicon.svg", media_type="image/svg+xml")
        return Response(status_code=204)

    return app
