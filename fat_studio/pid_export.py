"""Local P&ID drawing and graph exports, without PLC configuration or evidence."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
import math
import re
import threading
from xml.etree import ElementTree as ET
from urllib.parse import quote
import zipfile

from .models import Project
from .pid_cad import dxf_to_dwg
from .pid_models import PidConnection, PidDocument, PidEquipment, PidPosition
from .pid_symbols import PID_SYMBOLS_BY_ID, resolve_symbol
from .pid_ports import SIMULATED_PID_SYMBOLS, port_point, rotate_point
from .pid_conventions import service_definition

EXPORT_FORMATS = ("json", "graph-json", "svg", "pdf", "png", "dxf", "dwg", "graphml", "csv", "drawio")
_INK = "#23465c"
_BLUE = "#0055dd"
_LIGHT = "#eef5fb"
_PDF_RENDER_LOCK = threading.Lock()


def _xml_text(value: str) -> str:
    return re.sub(r"[^\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]", "\ufffd", value)


def project_document(project: Project) -> PidDocument:
    """Export the current drawing; keep document provenance, never PLC authority."""
    source = getattr(project, "pid_document", None)
    previous = {item.id: item for item in source.equipment} if source else {}
    previous_connections = {item.id: item for item in source.connections} if source else {}
    equipment = []
    for item in project.equipment:
        prior = previous.get(item.id)
        drawing_type = item.symbol_kind if item.type == "pid_symbol" else SIMULATED_PID_SYMBOLS.get(item.type, item.type)
        equipment.append(PidEquipment(
            id=item.id, name=item.name, type=drawing_type,
            source_tag=prior.source_tag if prior else (item.name.split(" · ")[0] if re.fullmatch(r"[A-Za-z]{1,8}-?\d+[A-Za-z0-9]*", item.name.split(" · ")[0]) else ""),
            position=PidPosition(x=item.position.x, y=item.position.y),
            page=prior.page if prior else 1, confidence=prior.confidence if prior else 1,
            provenance=prior.provenance if prior else "Vanguard FAT Studio : dessin du projet",
            review_required=prior.review_required if prior else False,
            source_kind=item.source_kind or (prior.source_kind if prior else "") or (item.type if item.type in SIMULATED_PID_SYMBOLS else ""),
            rotation=item.rotation,
            documentary=item.type == "pid_symbol" or item.type in SIMULATED_PID_SYMBOLS,
        ))
    connections = []
    for item in project.connections:
        prior = previous_connections.get(item.id)
        connections.append(PidConnection(
            id=item.id, source=item.source, target=item.target, label=item.label,
            directed=item.directed, inferred=prior.inferred if prior else False,
            confidence=prior.confidence if prior else 1,
            source_port=item.source_port, target_port=item.target_port,
            service=item.service,
        ))
    metadata = dict(source.metadata) if source else {}
    for key, value in {
        "project_id": project.id,
        "scope": "Dessin documentaire ; paramètres de simulation, associations PLC et verdicts FAT exclus.",
    }.items():
        if key in metadata or len(metadata) < 40:
            metadata[key] = value
    warnings = list(source.warnings) if source else []
    physical_warning = "Dessin exporté depuis un modèle thermique ou trois voies : paramètres et associations PLC exclus ; réimport documentaire, choix de simulation explicite requis."
    if any(item.type in SIMULATED_PID_SYMBOLS for item in project.equipment) and physical_warning not in warnings and len(warnings) < 300:
        warnings.append(physical_warning)
    return PidDocument(
        title=project.name, source_name=source.source_name if source else "",
        source_format=source.source_format if source else "fat-studio/project",
        source_sha256=source.source_sha256 if source else "", equipment=equipment,
        connections=connections, warnings=warnings,
        metadata=metadata,
        drawing=project.pid_drawing.model_copy(deep=True),
    )


def _native(document: PidDocument) -> str:
    return document.model_dump_json()


def _graph(document: PidDocument) -> dict:
    """ScottDuncanAI KnowledgeGraph 1.0 compatible node-link structure."""
    return {
        "schema_version": "1.0", "generator": "Vanguard FAT Studio",
        "fat_studio_drawing": document.drawing.model_dump(mode="json"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plant": {"id": document.metadata.get("project_id", "pid"), "name": document.title,
                  "source_file": document.source_name or None,
                  "sheets": sorted({str(item.page) for item in document.equipment})},
        "nodes": [{
            "id": item.id, "type": "instrument" if item.type in ("analog_sensor", "digital_sensor", "indicator") else "component" if item.type.startswith("valve") else "equipment",
            "label": item.name, "name": item.name, "tag": item.source_tag or None,
            "kind": item.type, "sheets": [str(item.page)], "confidence": item.confidence,
            "attributes": {"fat_studio_type": item.type, "position": item.position.model_dump(),
                           "review_required": item.review_required, "source_provenance": item.provenance,
                           "source_kind": item.source_kind, "rotation": item.rotation, "documentary": item.documentary},
            "provenance": [{"sheet": str(item.page), "page": item.page,
                            "source": "fat-studio/project", "local_id": item.id}],
        } for item in document.equipment],
        "edges": [{
            "id": item.id, "source": item.source, "target": item.target,
            "type": "connected_to", "confidence": item.confidence, "derived": item.inferred,
            "attributes": {"label": item.label, "directed": item.directed,
                           "source_port": item.source_port, "target_port": item.target_port,
                           "service": item.service},
        } for item in document.connections],
        "stats": {"nodes": len(document.equipment), "edges": len(document.connections)},
        "issues": [{"message": warning} for warning in document.warnings],
    }


def _scene(document: PidDocument) -> tuple[float, float, list[dict]]:
    """One shared vector scene keeps PDF, SVG, PNG and CAD geometry consistent."""
    equipment = document.equipment
    left = min((item.position.x for item in equipment), default=0) - 60
    top = min((item.position.y for item in equipment), default=0) - 110
    width = max(700, max((item.position.x - left + 210 for item in equipment), default=700))
    height = max(430, max((item.position.y - top + 200 for item in equipment), default=430))
    shapes: list[dict] = []

    def add(kind, **attributes):
        shapes.append({"kind": kind, **attributes})

    def line(points, **attributes):
        add("polyline", points=points, **{"stroke": _INK, **attributes})

    def text(x, y, value, size=12, color=_INK, anchor="middle", **metadata):
        # Drawing text is inert in every output. XML escaping is handled by ET.
        value = _xml_text(" ".join(str(value).split()))
        add("text", x=x, y=y, text=value, size=size, fill=color, anchor=anchor, **metadata)

    text(28, 34, document.title, 21, _BLUE, "start")
    text(28, 56, "P&ID · Vanguard FAT Studio · dessin documentaire", 11, _INK, "start")
    positions = {item.id: (item.position.x - left + 60, item.position.y - top + 48) for item in equipment}
    by_id = {item.id: item for item in equipment}
    for connection in document.connections:
        if connection.source not in positions or connection.target not in positions:
            continue
        sx, sy = positions[connection.source]
        tx, ty = positions[connection.target]
        dx, dy = tx - sx, ty - sy
        if abs(dx) >= abs(dy):
            direction = 1 if dx >= 0 else -1
            start, end = (sx + direction * 50, sy), (tx - direction * 50, ty)
            mid = (start[0] + end[0]) / 2
            points = [start, (mid, sy), (mid, ty), end]
        else:
            direction = 1 if dy >= 0 else -1
            start, end = (sx, sy + direction * 45), (tx, ty - direction * 45)
            mid = (start[1] + end[1]) / 2
            points = [start, (sx, mid), (tx, mid), end]
        source_item, target_item = by_id[connection.source], by_id[connection.target]
        source_point = port_point(source_item.type, connection.source_port, source_item.rotation) if connection.source_port else None
        target_point = port_point(target_item.type, connection.target_port, target_item.rotation) if connection.target_port else None
        if source_point or target_point:
            start = (sx + source_point[0] - 50, sy + source_point[1] - 50) if source_point else start
            end = (tx + target_point[0] - 50, ty + target_point[1] - 50) if target_point else end
            def exit_point(point, terminal):
                if terminal is None:
                    return point
                px, py = terminal
                vx, vy = (-1, 0) if px <= 0 else (1, 0) if px >= 100 else (0, -1) if py <= 0 else (0, 1) if py >= 100 else (0, 0)
                return point[0] + vx * 22, point[1] + vy * 22
            leaving = exit_point(start, source_point)
            entering = exit_point(end, target_point)
            mid = (leaving[0] + entering[0]) / 2
            points = [start, leaving, (mid, leaving[1]), (mid, entering[1]), entering, end]
        service = service_definition(connection.service)
        colour = service["color"] if connection.service != "unspecified" and document.drawing.color_mode == "service" else _INK
        service_meta = {"service": connection.service, "service_code": service["code"]}
        line(points, dash=connection.inferred, width=1.6, layer="PID_PIPES", stroke=colour, **service_meta)
        if connection.directed:
            before = next((point for point in reversed(points[:-1]) if point != end), start)
            angle = math.atan2(end[1] - before[1], end[0] - before[0])
            arrow = [end, (end[0] - 9 * math.cos(angle - .5), end[1] - 9 * math.sin(angle - .5)),
                     (end[0] - 9 * math.cos(angle + .5), end[1] - 9 * math.sin(angle + .5))]
            add("polygon", points=arrow, stroke=colour, fill=colour, layer="PID_PIPES", service_arrow=True, **service_meta)
        label = " | ".join(value for value in (service["code"] if connection.service != "unspecified" else "", connection.label) if value)
        if label:
            text((sx + tx) / 2, (sy + ty) / 2 - 9, label[:90], 10, colour,
                 role="connection_label", full_text=label, route_points=points, **service_meta)

    for item in equipment:
        x, y = positions[item.id]
        text(x, y - (70 if item.documentary else 53), item.name[:55], 12, _BLUE)
        kind = item.type
        symbol_id = resolve_symbol(kind)
        if symbol_id and (item.documentary or kind not in ("tank", "pump", "pump_vfd", "valve_onoff", "valve_control", "digital_input", "analog_sensor", "digital_sensor", "indicator")):
            for primitive in PID_SYMBOLS_BY_ID[symbol_id]["shapes"]:
                shape = dict(primitive)
                primitive_kind = shape.pop("kind")
                def place(px, py):
                    rx, ry = rotate_point(px, py, item.rotation)
                    return x + rx - 50, y + ry - 50
                if primitive_kind in ("polyline", "polygon"):
                    shape["points"] = [place(px, py) for px, py in shape["points"]]
                elif primitive_kind == "rect":
                    x0, y0 = shape["x"], shape["y"]
                    corners = [place(px, py) for px, py in ((x0,y0),(x0+shape["width"],y0),(x0+shape["width"],y0+shape["height"]),(x0,y0+shape["height"]))]
                    shape["x"], shape["y"] = min(px for px, _ in corners), min(py for _, py in corners)
                    shape["width"], shape["height"] = max(px for px, _ in corners)-shape["x"], max(py for _, py in corners)-shape["y"]
                else:
                    shape["x"], shape["y"] = place(shape["x"], shape["y"])
                    if primitive_kind == "ellipse" and item.rotation in (90,270):
                        shape["rx"], shape["ry"] = shape["ry"], shape["rx"]
                add(primitive_kind, **shape)
            instrument_code = PID_SYMBOLS_BY_ID[symbol_id].get("instrument_code")
            if instrument_code:
                text(x, y + 4, instrument_code, 12)
            for port in PID_SYMBOLS_BY_ID[symbol_id]["ports"]:
                px, py = place(port["x"], port["y"])
                text(px, py - 4, port["id"], 6)
        elif kind == "tank":
            add("rect", x=x - 30, y=y - 34, width=60, height=68, stroke=_INK, fill=_LIGHT)
            add("ellipse", x=x, y=y - 34, rx=30, ry=8, stroke=_INK, fill=_LIGHT)
            add("ellipse", x=x, y=y + 34, rx=30, ry=8, stroke=_INK, fill=_LIGHT)
            line([(x - 50, y), (x - 30, y)])
            line([(x + 30, y), (x + 50, y)])
            line([(x - 20, y + 42), (x - 20, y + 49), (x - 30, y + 49)])
            line([(x + 20, y + 42), (x + 20, y + 49), (x + 30, y + 49)])
        elif kind in ("pump", "pump_vfd"):
            line([(x - 50, y), (x + 50, y)])
            add("circle", x=x, y=y, radius=29, stroke=_INK, fill=_LIGHT)
            add("polygon", points=[(x - 13, y - 18), (x + 22, y), (x - 13, y + 18)], stroke=_INK, fill="#ffffff")
            line([(x - 20, y + 22), (x - 30, y + 37), (x + 30, y + 37), (x + 20, y + 22)])
            if kind == "pump_vfd":
                text(x, y + 51, "VFD", 9)
        elif kind in ("valve_onoff", "valve_control"):
            line([(x - 50, y), (x + 50, y)])
            add("polygon", points=[(x - 28, y - 19), (x + 28, y + 19), (x + 28, y - 19), (x - 28, y + 19)], stroke=_INK, fill=_LIGHT)
            line([(x, y), (x, y - 30)])
            if kind == "valve_control":
                add("ellipse", x=x, y=y - 34, rx=18, ry=9, stroke=_INK, fill=_LIGHT)
            else:
                add("rect", x=x - 13, y=y - 43, width=26, height=16, stroke=_INK, fill=_LIGHT)
                line([(x - 13, y - 27), (x + 13, y - 43)])
        elif kind == "digital_input":
            line([(x - 50, y + 12), (x - 20, y + 12)])
            line([(x + 20, y + 12), (x + 50, y + 12)])
            line([(x - 20, y + 12), (x + 18, y - 7)])
            line([(x, y - 7), (x, y - 30), (x - 15, y - 30), (x + 15, y - 30)])
        elif kind in ("analog_sensor", "digital_sensor", "indicator"):
            add("circle", x=x, y=y, radius=29, stroke=_INK, fill=_LIGHT)
            line([(x - 29, y), (x + 29, y)])
            line([(x, y + 29), (x, y + 47)], dash=True)
            letters = "".join(c for c in item.source_tag.split("-")[0] if c.isalpha())[:6]
            text(x, y - 8, letters or {"analog_sensor": "AI", "digital_sensor": "DI", "indicator": "ST"}[kind], 11)
            text(x, y + 17, item.source_tag[-8:] if item.source_tag else "", 9)
        else:
            add("rect", x=x - 38, y=y - 28, width=76, height=56, stroke=_INK, fill=_LIGHT)
            text(x, y + 4, kind[:12], 10)
        # A tag already present in the visible heading need not be repeated
        # beneath a symbol, where a downward terminal's pipe can cross it.
        tag_in_heading = item.name[:55].startswith(item.source_tag + " · ")
        if item.source_tag and item.source_tag != item.name and not tag_in_heading:
            text(x, y + 68, item.source_tag[:55], 9, role="source_tag")
    footer = "Aucune association PLC ni validation FAT humaine dans cet export."
    if document.source_name:
        footer += " Source : " + document.source_name[:95]
    text(28, height - 24, footer, 9, _INK, "start")
    return width, height, shapes


def _svg(document: PidDocument) -> bytes:
    width, height, shapes = _scene(document)
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    root = ET.Element("{http://www.w3.org/2000/svg}svg", {"viewBox": f"0 0 {width:g} {height:g}", "width": f"{width:g}", "height": f"{height:g}", "role": "img"})
    ET.SubElement(root, "title").text = _xml_text(document.title)
    ET.SubElement(root, "metadata", {"id": "fat-studio-pid"}).text = _native(document)
    ET.SubElement(root, "rect", {"width": "100%", "height": "100%", "fill": "white"})
    for shape in shapes:
        kind = shape["kind"]
        attributes = {"stroke": shape.get("stroke", "none"), "stroke-width": str(shape.get("width", 1.8) if kind not in ("rect",) else 1.8), "fill": shape.get("fill", "none")}
        if shape.get("dash"):
            attributes["stroke-dasharray"] = "6 4"
        if kind in ("polygon", "polyline"):
            attributes["points"] = " ".join(f"{x:g},{y:g}" for x, y in shape["points"])
        elif kind == "circle":
            attributes.update(cx=str(shape["x"]), cy=str(shape["y"]), r=str(shape["radius"]))
        elif kind == "ellipse":
            attributes.update(cx=str(shape["x"]), cy=str(shape["y"]), rx=str(shape["rx"]), ry=str(shape["ry"]))
        elif kind == "rect":
            attributes.update({key: str(shape[key]) for key in ("x", "y", "width", "height")})
        elif kind == "text":
            attributes.update(x=str(shape["x"]), y=str(shape["y"]), **{"font-family": "Arial, sans-serif", "font-size": str(shape["size"]), "text-anchor": shape["anchor"]})
        element = ET.SubElement(root, kind, attributes)
        if kind == "text":
            element.text = shape["text"]
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def engineering_scene(document: PidDocument):
    from .pid_sheet import sheet_scene

    return sheet_scene(document, _scene(document)[2])


def _pdf(document: PidDocument) -> bytes:
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from .pid_sheet import FONT_BOLD, FONT_REGULAR, register_fonts

    register_fonts()
    scene = engineering_scene(document)
    stream = io.BytesIO()
    drawing = canvas.Canvas(stream, pagesize=(scene.width_mm * mm, scene.height_mm * mm), pageCompression=1)
    drawing.setTitle(document.drawing.drawing_title or document.title)
    drawing.setAuthor(document.drawing.company)
    drawing.setSubject(" - ".join(value for value in (document.drawing.document_number,
        "Révision " + document.drawing.revision if document.drawing.revision else "") if value))
    drawing.setCreator("Vanguard FAT Studio")
    drawing.translate(0, scene.height_mm * mm)
    drawing.scale(mm, -mm)
    for shape in scene.shapes:
        stroke, fill = shape.get("stroke"), shape.get("fill")
        drawing.setStrokeColor(HexColor(stroke if stroke not in (None, "none") else "#000000"))
        drawing.setFillColor(HexColor(fill if fill not in (None, "none") else "#ffffff"))
        drawing.setLineWidth(shape["lineweight"])
        drawing.setDash([3, 1.5] if shape.get("dash") else [])
        stroked, filled = stroke not in (None, "none"), fill not in (None, "none")
        kind = shape["kind"]
        if kind in ("polygon", "polyline"):
            path = drawing.beginPath()
            path.moveTo(*shape["points"][0])
            for point in shape["points"][1:]:
                path.lineTo(*point)
            if kind == "polygon":
                path.close()
            drawing.drawPath(path, stroke=stroked, fill=filled)
        elif kind == "rect":
            drawing.rect(shape["x"], shape["y"], shape["width"], shape["height"], stroke=stroked, fill=filled)
        elif kind == "circle":
            drawing.circle(shape["x"], shape["y"], shape["radius"], stroke=stroked, fill=filled)
        elif kind == "ellipse":
            drawing.ellipse(shape["x"] - shape["rx"], shape["y"] - shape["ry"],
                            shape["x"] + shape["rx"], shape["y"] + shape["ry"], stroke=stroked, fill=filled)
        elif kind == "text":
            drawing.saveState()
            drawing.translate(shape["x"], shape["y"])
            drawing.scale(1, -1)
            drawing.setFont(FONT_BOLD if shape.get("bold") else FONT_REGULAR, shape["size"])
            if shape["anchor"] == "middle":
                drawing.drawCentredString(0, 0, shape["text"])
            else:
                drawing.drawString(0, 0, shape["text"])
            drawing.restoreState()
    drawing.showPage()
    drawing.save()
    writer = PdfWriter()
    reader = PdfReader(io.BytesIO(stream.getvalue()))
    writer.append(reader)
    if reader.metadata:
        writer.add_metadata({key: str(value) for key, value in reader.metadata.items() if value is not None})
    writer.add_attachment("fat-studio-pid.json", _native(document).encode("utf-8"))
    result = io.BytesIO()
    writer.write(result)
    return result.getvalue()


def _render_png(document, *, preview=False):
    import pypdfium2 as pdfium
    from PIL.PngImagePlugin import PngInfo

    with _PDF_RENDER_LOCK, pdfium.PdfDocument(_pdf(document)) as pdf:
        page = pdf[0]
        width, height = page.get_size()
        scale = min(1600 / width, 1100 / height) if preview else min(2, 3600 / max(width, height))
        bitmap = page.render(scale=scale)
        try:
            image = bitmap.to_pil()
            result = io.BytesIO()
            metadata = PngInfo()
            if not preview:
                metadata.add_text("fat-studio-pid", json.dumps(document.model_dump(mode="json"), ensure_ascii=True), zip=True)
            image.save(result, format="PNG", pnginfo=metadata, dpi=(72 * scale, 72 * scale))
            return result.getvalue()
        finally:
            bitmap.close()
            page.close()


def _png(document: PidDocument) -> bytes:
    return _render_png(document)


def export_pid_preview(project: Project) -> dict:
    import base64

    document = project_document(project)
    scene = engineering_scene(document)
    png = _render_png(document, preview=True)
    return {"width_mm": scene.width_mm, "height_mm": scene.height_mm,
            "image_data_url": "data:image/png;base64," + base64.b64encode(png).decode("ascii"),
            "warnings": scene.warnings}


def _dxf(document: PidDocument) -> bytes:
    import ezdxf
    from ezdxf.colors import aci2rgb
    from .pid_sheet import cad_text_height, text_width

    scene = engineering_scene(document)
    drawing = ezdxf.new("R2000")
    drawing.units = 4  # Printed sheet millimetres, never process dimensions.
    drawing.header["$MEASUREMENT"] = 1
    drawing.header["$LWDISPLAY"] = True
    drawing.set_modelspace_vport(height=scene.height_mm * 1.05, center=(scene.width_mm / 2, scene.height_mm / 2))
    drawing.appids.new("FAT_STUDIO_PID")
    record = drawing.rootdict.add_xrecord("FAT_STUDIO_PID")
    native = json.dumps(document.model_dump(mode="json"), ensure_ascii=True, separators=(",", ":"))
    record.extend([(1, native[index:index + 200]) for index in range(0, len(native), 200)])
    drawing.styles.new("PID_REGULAR", dxfattribs={"font": "Geist-Regular.ttf"})
    drawing.styles.new("PID_BOLD", dxfattribs={"font": "Geist-Bold.ttf"})
    drawing.linetypes.new("PID_DASHED", dxfattribs={"description": "Proposed documentary connection", "pattern": [4.5, 3, -1.5]})
    for layer, weight in (("PID_BORDER", 70), ("PID_TITLEBLOCK", 35), ("PID_REVISIONS", 18),
                          ("PID_EQUIPMENT", 35), ("PID_PIPES", 50), ("PID_SIGNALS", 18), ("PID_TEXT", 18)):
        drawing.layers.new(layer, dxfattribs={"color": 7, "lineweight": weight})
    # Historical names remain available to CAD consumers, without duplicate art.
    drawing.layers.new("PID_SYMBOLS", dxfattribs={"color": 7, "lineweight": 18})
    model = drawing.modelspace()
    aci_palette = [(index, tuple(aci2rgb(index))) for index in range(1, 256)]

    def cad_colour(shape):
        if shape.get("service") and document.drawing.color_mode == "service":
            return service_definition(shape["service"])["aci"]
        colour = shape.get("fill") if shape["kind"] == "text" else shape.get("stroke")
        if not colour or colour in ("none", "#000000", "#ffffff"):
            return 7
        rgb = tuple(int(colour[index:index + 2], 16) for index in (1, 3, 5))
        return min(aci_palette, key=lambda candidate: sum((a - b) ** 2 for a, b in zip(rgb, candidate[1], strict=True)))[0]

    def fill_boundary(shape, attrs):
        """Preserve PDF painter order, including white symbol backgrounds."""
        fill = shape.get("fill")
        kind = shape["kind"]
        if fill in (None, "none") or kind in ("text", "polyline"):
            return
        # ACI255 is actual paper white, whereas7 adapts to the CAD background.
        colour = 255 if fill == "#ffffff" else attrs["color"]
        hatch = model.add_hatch(color=colour, dxfattribs={"layer": attrs["layer"]})
        if kind in ("polygon", "rect"):
            if kind == "rect":
                x, y, w, h = shape["x"], scene.height_mm - shape["y"], shape["width"], shape["height"]
                points = [(x, y), (x + w, y), (x + w, y - h), (x, y - h)]
            else:
                points = [(x, scene.height_mm - y) for x, y in shape["points"]]
            hatch.paths.add_polyline_path(points, is_closed=True)
        else:
            boundary = hatch.paths.add_edge_path()
            center = (shape["x"], scene.height_mm - shape["y"])
            if kind == "circle":
                boundary.add_arc(center, shape["radius"], 0, 360)
            elif kind == "ellipse":
                rx, ry = shape["rx"], shape["ry"]
                axis, ratio = ((rx, 0), ry / rx) if rx >= ry else ((0, ry), rx / ry)
                boundary.add_ellipse(center, axis, ratio, 0, 360)

    for shape in scene.shapes:
        kind = shape["kind"]
        attrs = {"layer": shape["layer"], "color": cad_colour(shape), "lineweight": round(shape["lineweight"] * 100)}
        fill_boundary(shape, attrs)
        if shape.get("dash"):
            attrs["linetype"] = "PID_DASHED"
        if kind in ("polygon", "polyline"):
            model.add_lwpolyline([(x, scene.height_mm - y) for x, y in shape["points"]], close=kind == "polygon", dxfattribs=attrs)
        elif kind == "rect":
            x, y, w, h = shape["x"], scene.height_mm - shape["y"], shape["width"], shape["height"]
            model.add_lwpolyline([(x, y), (x + w, y), (x + w, y - h), (x, y - h)], close=True, dxfattribs=attrs)
        elif kind == "circle":
            model.add_circle((shape["x"], scene.height_mm - shape["y"]), shape["radius"], dxfattribs=attrs)
        elif kind == "ellipse":
            rx, ry = shape["rx"], shape["ry"]
            axis, ratio = ((rx, 0), ry / rx) if rx >= ry else ((0, ry), rx / ry)
            model.add_ellipse((shape["x"], scene.height_mm - shape["y"]), axis, ratio=ratio, dxfattribs=attrs)
        elif kind == "text" and shape["text"]:
            value = shape["text"].replace("\\", "/").replace("%%", "% %").replace("%<", "% <")
            bold = shape.get("bold", False)
            x = shape["x"] - text_width(value, shape["size"], bold) / 2 if shape["anchor"] == "middle" else shape["x"]
            entity = model.add_text(value, dxfattribs={**attrs, "height": cad_text_height(shape["size"], bold),
                "style": "PID_BOLD" if shape.get("bold") else "PID_REGULAR"})
            # Explicit baseline-left placement survives R2000 readers which
            # disagree about omitted alignment points for centred TEXT.
            entity.dxf.insert = (x, scene.height_mm - shape["y"])
    drawing.layouts.rename("Layout1", "PID_SHEET")
    layout = drawing.layouts.get("PID_SHEET")
    layout.page_setup(size=(scene.width_mm, scene.height_mm), margins=(0, 0, 0, 0), units="mm",
                      scale=(1, 1), name=f"PID {document.drawing.paper_size}")
    layout.add_viewport(center=(scene.width_mm / 2, scene.height_mm / 2),
                        size=(scene.width_mm, scene.height_mm),
                        view_center_point=(scene.width_mm / 2, scene.height_mm / 2),
                        view_height=scene.height_mm)
    stream = io.StringIO()
    drawing.write(stream)
    return stream.getvalue().encode("cp1252", errors="backslashreplace")


def _graphml(document: PidDocument) -> bytes:
    namespace = "http://graphml.graphdrawing.org/xmlns"
    ET.register_namespace("", namespace)
    root = ET.Element(f"{{{namespace}}}graphml")
    fields = {"name": "node", "type": "node", "source_kind": "node", "rotation": "node", "documentary": "node", "source_tag": "node", "x": "node", "y": "node", "label": "edge", "source_port": "edge", "target_port": "edge", "service": "edge", "pid_document": "graph"}
    for name, scope in fields.items():
        ET.SubElement(root, "key", {"id": name, "for": scope, "attr.name": name, "attr.type": "double" if name in ("x", "y") else "string"})
    graph = ET.SubElement(root, "graph", {"id": "pid", "edgedefault": "directed"})
    ET.SubElement(graph, "data", {"key": "pid_document"}).text = _native(document)
    for item in document.equipment:
        node = ET.SubElement(graph, "node", {"id": item.id})
        for key, value in {"name": item.name, "type": item.type, "source_kind": item.source_kind, "rotation": item.rotation, "documentary": str(item.documentary).lower(), "source_tag": item.source_tag, "x": item.position.x, "y": item.position.y}.items():
            ET.SubElement(node, "data", {"key": key}).text = _xml_text(str(value))
    for item in document.connections:
        edge = ET.SubElement(graph, "edge", {"id": item.id, "source": item.source, "target": item.target, "directed": str(item.directed).lower()})
        ET.SubElement(edge, "data", {"key": "label"}).text = _xml_text(item.label)
        ET.SubElement(edge, "data", {"key": "source_port"}).text = _xml_text(item.source_port)
        ET.SubElement(edge, "data", {"key": "target_port"}).text = _xml_text(item.target_port)
        ET.SubElement(edge, "data", {"key": "service"}).text = item.service
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _csv_zip(document: PidDocument) -> bytes:
    result = io.BytesIO()

    def table(rows, columns):
        text = io.StringIO(newline="")
        writer = csv.DictWriter(text, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            # Prevent spreadsheet applications from evaluating imported formula text.
            writer.writerow({key: "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value for key, value in row.items()})
        return text.getvalue().encode("utf-8-sig")

    equipment = [{**item.model_dump(), "x": item.position.x, "y": item.position.y} for item in document.equipment]
    with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("equipment.csv", table(equipment, ["id", "name", "type", "source_kind", "rotation", "documentary", "source_tag", "x", "y", "page", "confidence", "provenance", "review_required"]))
        archive.writestr("connections.csv", table([item.model_dump() for item in document.connections], ["id", "source", "target", "source_port", "target_port", "label", "service", "directed", "inferred", "confidence"]))
        archive.writestr("fat-studio-pid.json", _native(document))
    return result.getvalue()


def _drawio(document: PidDocument) -> bytes:
    root = ET.Element("mxfile", {"host": "Vanguard FAT Studio", "version": "1.0"})
    diagram = ET.SubElement(root, "diagram", {"name": _xml_text(document.title), "id": "pid"})
    model = ET.SubElement(diagram, "mxGraphModel", {"grid": "1", "gridSize": "10"})
    cells = ET.SubElement(model, "root")
    ET.SubElement(cells, "mxCell", {"id": "0"})
    ET.SubElement(cells, "mxCell", {"id": "1", "parent": "0"})
    ET.SubElement(cells, "object", {"id": "fat-studio-pid", "pid": _native(document)})
    for item in document.equipment:
        # Embed our vector symbols as self-contained images; no external URI is used.
        single = PidDocument(title=item.name, equipment=[item.model_copy(update={"position": PidPosition(x=0, y=0)})])
        symbol = ET.Element("{http://www.w3.org/2000/svg}svg", {"viewBox": "70 85 100 130", "width": "100", "height": "130"})
        # A per-symbol scene is rendered through the same safe SVG writer, then its
        # viewport crops out the header/footer. draw.io accepts a data URI image.
        full = ET.fromstring(_svg(single))
        for element in list(full):
            if element.tag.rsplit("}", 1)[-1] not in ("metadata", "title") and element.get("width") != "100%":
                symbol.append(element)
        data = quote(ET.tostring(symbol, encoding="utf-8"), safe="")
        cell = ET.SubElement(cells, "mxCell", {"id": "node-" + item.id, "value": _xml_text(item.name), "style": "shape=image;image=data:image/svg+xml," + data + ";html=0;verticalLabelPosition=top;", "vertex": "1", "parent": "1"})
        ET.SubElement(cell, "mxGeometry", {"x": str(item.position.x), "y": str(item.position.y), "width": "100", "height": "130", "as": "geometry"})
    by_id = {item.id: item for item in document.equipment}
    for item in document.connections:
        service = service_definition(item.service)
        colour = service["color"] if item.service != "unspecified" and document.drawing.color_mode == "service" else _INK
        style = "edgeStyle=orthogonalEdgeStyle;html=0;endArrow=" + ("block" if item.directed else "none") + ";strokeColor=" + colour + ";"
        for end, item_id, terminal in (("exit", item.source, item.source_port), ("entry", item.target, item.target_port)):
            equipment = by_id[item_id]
            point = port_point(equipment.type, terminal, equipment.rotation) if terminal else None
            if point is not None:
                # The symbol centre (120,158) is cropped by viewBox 70,85,100,130.
                style += f"{end}X={point[0] / 100:.12g};{end}Y={(23 + point[1]) / 130:.12g};{end}Perimeter=0;"
        label = " | ".join(value for value in (service["code"] if item.service != "unspecified" else "", item.label) if value)
        cell = ET.SubElement(cells, "mxCell", {"id": "edge-" + item.id, "value": _xml_text(label), "service": item.service, "source": "node-" + item.source, "target": "node-" + item.target, "edge": "1", "parent": "1", "style": style})
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def export_pid(project: Project, format: str) -> tuple[bytes, str, str]:
    document = project_document(project)
    normalized = {"pid": "json", "pid-json": "json", "graph": "graph-json", "json-graph": "graph-json", "csv-zip": "csv", "draw.io": "drawio"}.get(format.lower(), format.lower())
    if normalized == "json":
        return _native(document).encode("utf-8"), "application/json", "pid.json"
    if normalized == "graph-json":
        return json.dumps(_graph(document), ensure_ascii=False, indent=2).encode("utf-8"), "application/json", "graph.json"
    if normalized == "svg":
        return _svg(document), "image/svg+xml", "svg"
    if normalized == "pdf":
        return _pdf(document), "application/pdf", "pdf"
    if normalized == "png":
        return _png(document), "image/png", "png"
    if normalized == "dxf":
        return _dxf(document), "image/vnd.dxf", "dxf"
    if normalized == "dwg":
        return dxf_to_dwg(_dxf(document)), "image/vnd.dwg", "dwg"
    if normalized == "graphml":
        return _graphml(document), "application/graphml+xml", "graphml"
    if normalized == "csv":
        return _csv_zip(document), "application/zip", "csv.zip"
    if normalized == "drawio":
        return _drawio(document), "application/vnd.jgraph.mxfile", "drawio"
    raise ValueError("Format P&ID inconnu. Formats : " + ", ".join(EXPORT_FORMATS) + ".")
