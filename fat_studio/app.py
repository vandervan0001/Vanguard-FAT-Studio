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
from .branding import APP_NAME
from .catalog import CATALOG
from .demo import demo_project
from .demo_lab import demo_lab_project
from .exchange import ProjectPackage, ScenarioPackage, import_scenarios, project_package, read_project, scenarios_package
from .archive import capture_archive, export_archive, prepare_archive
from .mapping import export_mapping, import_mapping, preview_mapping
from .models import PreparedAction, Project, validate_project
from .opcua_browser import browse_metadata
from .reporting import csv_stream, html_report, json_stream
from .runtime import RunConflict, Runtime
from .security import MachinePolicy, TargetDenied
from .storage import Store
from .workspaces import active_workspace, list_workspaces, restore_workspace, select_workspace, workspace_path, workspace_summary


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


class PulseRequest(Payload):
    tag_id: str = Field(min_length=1, max_length=80)
    value: bool
    duration_ms: int = Field(default=300, ge=100, le=2000)


class StepObservationRequest(Payload):
    verdict: Literal["pass", "fail"]
    observation: str = Field(default="", max_length=4000)


class StimulusRequest(Payload):
    tag_id: str = Field(min_length=1, max_length=80)
    value: Any
    unit: Literal["native", "mA", "V", "engineering", "percent"] = "native"
    diagnostic: bool = False


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


class MappingPreviewRequest(MappingRequest):
    project: Project
    mode: Literal["merge", "replace"] = "merge"


class BrowseRequest(Payload):
    project: Project
    node_id: str = Field(default="i=85", min_length=1, max_length=1000)
    offset: int = Field(default=0, ge=0, le=1900)
    confirmation: str = Field(min_length=1, max_length=1100)


class ScenarioImportRequest(Payload):
    package: ScenarioPackage
    mode: Literal["merge", "replace"] = "merge"


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
        workspace_id = active_workspace(folder)
        store = Store(workspace_path(folder, workspace_id))
        runtime = None
        try:
            startup_error = None
            try:
                project = store.last_project()
            except (ValueError, OSError, KeyError) as exc:
                project = demo_lab_project()
                project.id = "recovery-" + uuid.uuid4().hex[:12]
                project.name = "Récupération — " + project.name
                startup_error = "Le dernier projet est illisible et a été conservé intact. " + str(exc)
            needs_save = project is None or startup_error is not None
            if project is None:
                project = demo_lab_project()
            policy = MachinePolicy(folder / "machine-policy.json")
            runtime = Runtime(store, project, policy, adapter_factory, context_scope=str(store.root))
            # Opening an existing project is not a save: retain its previous revision.
            if needs_save:
                store.save_project(project)
            if startup_error:
                runtime.error = startup_error
                runtime.event("project_recovery", startup_error)
            application.state.store = store
            application.state.runtime = runtime
            application.state.policy = policy
            application.state.workspace_id = workspace_id
            application.state.mutations = asyncio.Lock()
            yield
        finally:
            try:
                current_runtime = getattr(application.state, "runtime", runtime)
                if current_runtime:
                    await current_runtime.close()
            finally:
                getattr(application.state, "store", store).close()

    app = FastAPI(title=f"{APP_NAME} local API", version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url="/api/openapi.json")

    def context_conflict(request: Request):
        runtime = app.state.runtime
        project_id = request.headers.get("x-fat-project-id")
        if project_id is not None and project_id != runtime.project.id:
            return JSONResponse({"detail": "Le projet actif a changé dans un autre onglet ; recharger avant d'agir."}, status_code=409)
        revision = request.headers.get("x-fat-project-revision")
        if revision is not None and revision != runtime.project_revision:
            return JSONResponse({"detail": "Le projet a été modifié dans un autre onglet ; conserver le brouillon et recharger avant d'agir."}, status_code=409)
        run_id = request.headers.get("x-fat-run-id")
        if run_id is not None and run_id != (runtime.run_id or ""):
            return JSONResponse({"detail": "L'essai actif a changé dans un autre onglet ; recharger avant d'agir."}, status_code=409)
        return None

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        host = request.headers.get("host", "")
        try:
            hostname = urlsplit("http://" + host).hostname
        except ValueError:
            hostname = None
        if hostname not in ("127.0.0.1", "localhost", "::1"):
            return JSONResponse({"detail": f"Host refusé : {APP_NAME} est réservé au poste local."}, status_code=403)
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
                limit = (100 if request.url.path == "/api/project/archive/import" else 5) * 1024 * 1024
                if size > limit:
                    return JSONResponse({"detail": f"La requête dépasse {limit // (1024 * 1024)} Mo."}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        guarded_read = request.method == "GET" and (request.url.path in ("/api/mapping", "/api/project/download", "/api/project/archive", "/api/scenarios/export")
                         or (request.url.path.startswith("/api/scenarios/") and request.url.path.endswith("/export"))
                         or request.url.path.startswith("/api/export/")
                         or (request.url.path.startswith("/api/runs/") and request.url.path.rsplit("/", 1)[-1] in ("json", "csv", "report")))
        # Archive export pins its read-only snapshot under this same lock in
        # the route, then releases it before compression. Stop remains usable.
        if (mutation or guarded_read) and request.url.path != "/api/project/archive":
            async with app.state.mutations:
                # Imports and project switches can race another client just like
                # run commands. Check the captured context while holding the
                # mutation lock, including replacements that would drop a run.
                conflict = context_conflict(request)
                if conflict is not None:
                    return conflict
                response = await call_next(request)
        else:
            response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; font-src 'self' data:; object-src 'none'; "
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
        await runtime.replace_project(project)
        response.headers["X-FAT-Project-Revision"] = runtime.project_revision
        return runtime.project

    @app.put("/api/project")
    async def save_project(project: Project, response: Response):
        return await replace_project(project, response)

    @app.post("/api/project/import")
    async def import_project(payload: dict, response: Response):
        return await replace_project(read_project(payload), response)

    @app.get("/api/project/download")
    async def download_project():
        project = app.state.runtime.project
        return Response(project_package(project).model_dump_json(indent=2), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{project.id}.fat.json"',
                                 "X-FAT-Project-Revision": app.state.runtime.project_revision})

    @app.get("/api/schemas/{kind}")
    async def exchange_schema(kind: str):
        schemas = {"project": ProjectPackage, "scenarios": ScenarioPackage}
        if kind not in schemas:
            raise HTTPException(404, "Schéma inconnu.")
        return schemas[kind].model_json_schema()

    @app.get("/api/scenarios/export")
    @app.get("/api/scenarios/{scenario_id}/export")
    async def export_scenarios(scenario_id: str | None = None):
        package = scenarios_package(app.state.runtime.project, scenario_id)
        return Response(package.model_dump_json(indent=2), media_type="application/json", headers={
            "Content-Disposition": 'attachment; filename="scenarios.fat.json"',
            "X-FAT-Project-Revision": app.state.runtime.project_revision})

    @app.post("/api/scenarios/import")
    async def load_scenarios(body: ScenarioImportRequest, response: Response):
        project = import_scenarios(app.state.runtime.project, body.package, body.mode)
        return await replace_project(project, response)

    @app.get("/api/project/archive")
    async def archive_project(request: Request):
        async with app.state.mutations:
            conflict = context_conflict(request)
            if conflict is not None:
                return conflict
            snapshot = capture_archive(app.state.store, app.state.runtime.project)
            revision = app.state.runtime.project_revision
        def build():
            try:
                return export_archive(snapshot, snapshot.project)
            finally:
                snapshot.close()
        task = asyncio.create_task(asyncio.to_thread(build))
        try:
            payload = await asyncio.shield(task)
        except asyncio.CancelledError:
            # The worker owns its reader until completion, including when a
            # browser cancels. Never close a connection underneath that worker.
            try:
                await task
            except Exception:
                pass
            raise
        return Response(payload, media_type="application/zip", headers={
            "Content-Disposition": f'attachment; filename="{snapshot.project.id}.fat.zip"',
            "X-FAT-Project-Revision": revision})

    async def open_workspace(id: str, response: Response):
        old = app.state.runtime
        old_store = app.state.store
        async with old.lock:
            if old.status == "running":
                raise RunConflict("Mettre l'essai en pause avant de changer de dossier.")
            if id == app.state.workspace_id:
                response.headers["X-FAT-Project-Revision"] = old.project_revision
                response.headers["X-FAT-Run-ID"] = old.run_id or ""
                return old.project
            path = workspace_path(folder, id)
            if not path.is_dir():
                raise ValueError("Espace local absent.")
            new_store = Store(path)
            try:
                project = new_store.last_project()
                if project is None:
                    raise ValueError("Le dossier ne contient pas de projet.")
                new_runtime = Runtime(new_store, project, app.state.policy, adapter_factory, context_scope=str(path.resolve()))
                if old.status == "paused":
                    old.event("workspace_change", "Essai conservé avant ouverture d'un autre dossier local.")
                    if old.run_id and not old._run_finished:
                        old.store.set_status(old.run_id, "stopped", ended=True)
                        old._run_finished = True
                if old.adapter:
                    await old.adapter.disconnect()
                await old._cancel_loop()
                select_workspace(folder, id)
            except asyncio.CancelledError:
                await old._fail(RuntimeError("Changement de dossier annulé ; reprise explicite requise."))
                new_store.close()
                raise
            except BaseException:
                new_store.close()
                raise
            old.status = "stopped"
            app.state.runtime = new_runtime
            app.state.store = new_store
            app.state.workspace_id = id
            old_store.close()
            response.headers["X-FAT-Project-Revision"] = new_runtime.project_revision
            response.headers["X-FAT-Run-ID"] = ""
            return project

    @app.post("/api/project/archive/import")
    async def restore_project_archive(request: Request, response: Response):
        if app.state.runtime.status == "running":
            raise RunConflict("Mettre l'essai en pause avant de restaurer une archive.")
        plan = prepare_archive(await request.body())
        id, _ = restore_workspace(folder, plan)
        return await open_workspace(id, response)

    @app.get("/api/workspaces")
    async def workspaces():
        return list_workspaces(folder, app.state.workspace_id)

    @app.get("/api/workspace")
    async def workspace():
        return workspace_summary(folder, app.state.workspace_id, app.state.workspace_id)

    @app.post("/api/workspaces/{id}/open")
    async def load_workspace(id: str, response: Response):
        return await open_workspace(id, response)

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

    @app.post("/api/pilot/load")
    async def load_pilot(response: Response):
        from .demo_lab import demo_lab_project
        return await replace_project(demo_lab_project(), response)

    @app.get("/api/validate")
    async def validate():
        return validate_draft(app.state.runtime.project)

    def validate_draft(project: Project):
        result = validate_project(project)
        if project.plc.mode == "opcua":
            try:
                app.state.policy.authorize(project.plc)
            except ValueError as exc:
                result["errors"].append({"path": "plc", "message": str(exc)})
                result["valid"] = False
            result["warnings"].append({"path": "plc", "message": "L'existence, les types et les droits des NodeIds seront vérifiés en ligne au démarrage, avant écriture."})
        return result

    def guard_preview(request: Request, project: Project, *, idle: bool = False):
        # New preview routes require an explicit baseline even though they do not save.
        for header in ("x-fat-project-id", "x-fat-project-revision", "x-fat-run-id"):
            if header not in request.headers:
                raise HTTPException(409, "Contexte projet/révision/essai requis. Conservez le brouillon et relisez le projet.")
        if project.id != app.state.runtime.project.id:
            raise HTTPException(409, "Le brouillon ne correspond pas au projet actif.")
        if idle and app.state.runtime.status in ("running", "paused"):
            raise HTTPException(409, "Arrêtez l'essai avant cet aperçu ; aucune reprise automatique ne sera effectuée.")

    @app.post("/api/validate/preview")
    async def validate_preview(project: Project, request: Request):
        guard_preview(request, project)
        return {**validate_draft(project), "project": project.model_dump(mode="json")}

    @app.post("/api/mapping/preview")
    async def mapping_preview(body: MappingPreviewRequest, request: Request):
        guard_preview(request, body.project, idle=True)
        return preview_mapping(body.project, body.csv, body.mode)

    @app.post("/api/opcua/browse")
    async def opcua_browse(body: BrowseRequest, request: Request):
        guard_preview(request, body.project, idle=True)
        try:
            return await browse_metadata(body.project, app.state.policy, body.confirmation, body.node_id, body.offset)
        except (TimeoutError, OSError, ConnectionError) as exc:
            raise HTTPException(400, "Exploration OPC UA interrompue. Vérifiez la cible et relancez volontairement la lecture.") from exc

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

    @app.post("/api/force/pulse")
    async def pulse(body: PulseRequest):
        return await app.state.runtime.pulse(body.tag_id, body.value, body.duration_ms)

    @app.post("/api/force/stimulus")
    async def stimulus(body: StimulusRequest):
        return await app.state.runtime.stimulus(body.tag_id, PreparedAction(target=body.tag_id, value=body.value,
                                                                         unit=body.unit, diagnostic=body.diagnostic))

    @app.post("/api/run/steps/{step_id}/execute")
    async def execute_fat_step(step_id: str):
        return await app.state.runtime.execute_fat_step(step_id)

    @app.post("/api/run/steps/{step_id}/observe")
    async def observe_fat_step(step_id: str, body: StepObservationRequest):
        return await app.state.runtime.observe_fat_step(step_id, body.verdict, body.observation)

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
    if (web_dir / "brand").is_dir():
        app.mount("/brand", StaticFiles(directory=web_dir / "brand"), name="brand")

    @app.get("/", include_in_schema=False)
    async def index():
        if (web_dir / "index.html").exists():
            return FileResponse(web_dir / "index.html", headers={"Cache-Control": "no-cache"})
        return HTMLResponse(f"<h1>{APP_NAME}</h1><p>Interface absente. Exécuter npm ci, npm run build dans frontend, puis python scripts/build-web.py.</p>", status_code=503)

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon():
        if (web_dir / "favicon.svg").is_file():
            return FileResponse(web_dir / "favicon.svg", media_type="image/svg+xml")
        return Response(status_code=204)

    return app
