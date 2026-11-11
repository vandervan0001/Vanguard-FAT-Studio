"""P&ID routes: passive inspection, draft preparation and snapshot exports."""

from __future__ import annotations

import asyncio
import importlib.util
import io
from pathlib import Path, PurePosixPath
import zipfile

from fastapi import HTTPException, Query, Request
from fastapi.responses import Response

from .pid_catalog import public_catalog
from .pid_conventions import conventions_catalog
from .pid_exchange import PidPrepareRequest, prepare_pid
from .pid_process import inspect_isolated
from .pid_symbols import PID_SYMBOLS
from .pid_titleblock import PidDrawingSettings


def capabilities() -> dict:
    from .pid_cad import cad_capabilities
    cad = cad_capabilities()
    # The adapter also reports its exact version/limitations for the UI and CLI.
    dwg_import = bool(cad.get("read_available", cad.get("import", cad.get("available", False))))
    dwg_export = bool(cad.get("write_available", cad.get("export", cad.get("available", False))))
    native = [("pdf", "PDF numérique ou scanné"), ("png", "PNG, JPEG, TIFF, BMP, WebP"),
              ("svg", "SVG"), ("dxf", "DXF"), ("json", "Document P&ID JSON / graphe de connaissances"),
              ("graphml", "GraphML"), ("xml", "DEXPI / Proteus XML (sous-ensemble)"), ("csv", "CSV / TSV équipements"),
              ("drawio", "draw.io natif FAT"), ("zip", "Archive CSV native FAT")]
    exports = [("svg", "SVG vectoriel"), ("pdf", "PDF vectoriel"), ("png", "PNG"), ("dxf", "DXF"),
               ("json", "P&ID JSON restaurable"), ("graph", "Graphe de connaissances JSON"),
               ("graphml", "GraphML"), ("csv", "CSV équipements et liaisons"), ("drawio", "Diagramme draw.io")]
    return {
        "imports": [{"format": kind, "label": label, "available": True,
                     "detail": "Traitement local ; objets et liaisons à revoir."} for kind, label in native]
                   + [{"format": "dwg", "label": "DWG via LibreDWG", "available": dwg_import,
                       "detail": "Conversion locale gratuite ; installer LibreDWG si indisponible."}],
        "exports": [{"format": kind, "label": label, "available": True, "detail": "Schéma du projet enregistré."}
                    for kind, label in exports]
                   + [{"format": "dwg", "label": "DWG R2000 via LibreDWG", "available": dwg_export,
                       "detail": "Conversion expérimentale, interopérabilité à vérifier dans le logiciel destinataire."}],
        "limits": {"upload_mb": 20, "max_equipment": 50, "max_connections": 200, "max_pages": 20},
        "local_only": True, "ocr_available": importlib.util.find_spec("rapidocr_onnxruntime") is not None,
        "cad": cad,
    }


def install_pid_routes(app, context_conflict):
    imports = asyncio.Semaphore(1)
    exports = asyncio.Semaphore(1)

    @app.get("/api/pid/capabilities")
    async def pid_capabilities():
        return await asyncio.to_thread(capabilities)

    @app.get("/api/pid/catalog")
    async def pid_catalog():
        return public_catalog()

    @app.get("/api/pid/conventions")
    async def pid_conventions():
        return conventions_catalog()

    @app.get("/api/pid/cad-fonts")
    async def pid_cad_fonts():
        # Fixed packaged resources only; no font installation or caller paths.
        folder = Path(__file__).parent / "web" / "brand"
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in ("Geist-Regular.ttf", "Geist-Bold.ttf", "OFL.txt"):
                archive.writestr(name, (folder / name).read_bytes())
            archive.writestr("README.txt", "Vanguard FAT Studio - Polices CAO\n\n"
                             "Installer ces polices dans la CAO destinataire pour conserver les métriques du PDF.\n"
                             "Les DWG/DXF contiennent du texte éditable et référencent ces fichiers ; ils ne les incorporent pas.\n"
                             "Geist est fourni sous licence SIL Open Font License 1.1, jointe dans OFL.txt.\n")
        return Response(output.getvalue(), media_type="application/zip",
                        headers={"Content-Disposition": 'attachment; filename="Vanguard-PID-CAD-fonts.zip"'})

    @app.get("/api/pid/symbols")
    async def pid_symbols():
        return {"version": "1.0", "symbols": PID_SYMBOLS, "simulation": False}

    @app.post("/api/pid/inspect")
    async def inspect(request: Request, filename: str = Query(max_length=240),
                      pages: str = Query(default="", max_length=200), ocr: bool = True):
        name = PurePosixPath(filename.replace("\\", "/")).name
        if not name or any(ord(char) < 32 for char in name):
            raise ValueError("Nom de fichier P&ID invalide.")
        data = await request.body()
        if not data or len(data) > 20 * 1024 * 1024:
            raise ValueError("Choisir un fichier P&ID non vide de 20 Mo au maximum.")
        async def parse():
            async with imports:
                try:
                    return await inspect_isolated(data, name, pages, ocr)
                except OSError as exc:
                    raise HTTPException(503, "Le lecteur local P&ID ne peut pas démarrer.") from exc

        async def disconnected():
            while not await request.is_disconnected():
                await asyncio.sleep(.2)

        reader = asyncio.create_task(parse())
        monitor = asyncio.create_task(disconnected())
        try:
            finished, _ = await asyncio.wait((reader, monitor), return_when=asyncio.FIRST_COMPLETED)
            if reader in finished:
                return await reader
            raise HTTPException(499, "Lecture P&ID annulée par le client.")
        finally:
            for task in (reader, monitor):
                if not task.done():
                    task.cancel()
            await asyncio.gather(reader, monitor, return_exceptions=True)

    @app.post("/api/pid/prepare")
    async def prepare(body: PidPrepareRequest):
        return prepare_pid(body)

    @app.get("/api/pid/export/{kind}")
    async def export(request: Request, kind: str):
        from .pid_export import export_pid
        async with app.state.mutations:
            conflict = context_conflict(request)
            if conflict is not None:
                return conflict
            project = app.state.runtime.project.model_copy(deep=True)
            revision = app.state.runtime.project_revision
        async with exports:
            try:
                data, media_type, extension = await asyncio.to_thread(export_pid, project, kind)
            except OSError as exc:
                raise HTTPException(503, "L'export P&ID local est indisponible.") from exc
        return Response(data, media_type=media_type, headers={
            "Content-Disposition": f'attachment; filename="{project.id}.pid.{extension.lstrip(chr(46))}"',
            "X-FAT-Project-Revision": revision,
        })

    @app.post("/api/pid/preview")
    async def preview(request: Request, body: PidDrawingSettings):
        from .pid_export import export_pid_preview

        # A preview combines the saved geometry with the submitted layout only.
        # It neither applies a draft nor holds the operational lock while rendering.
        async with app.state.mutations:
            conflict = context_conflict(request)
            if conflict is not None:
                return conflict
            project = app.state.runtime.project.model_copy(deep=True)
            revision = app.state.runtime.project_revision
        project.pid_drawing = body.model_copy(deep=True)
        async with exports:
            try:
                result = await asyncio.to_thread(export_pid_preview, project)
            except OSError as exc:
                raise HTTPException(503, "L'aperçu du plan est indisponible sur ce poste.") from exc
        return {**result, "project_id": project.id, "project_revision": revision, "saved_geometry": True}
