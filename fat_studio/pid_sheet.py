"""Engineering drawing sheets in printed millimetres, without process scaling.

The frame, typography and weights are house conventions, not a standards
conformity statement. Legacy SVG/draw.io geometry remains a separate contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading


PAPER_MM = {"A4": (210, 297), "A3": (297, 420), "A2": (420, 594),
            "A1": (594, 841), "A0": (841, 1189)}
FONT_REGULAR = "VanguardPidGeist"
FONT_BOLD = "VanguardPidGeistBold"
_FONT_LOCK = threading.Lock()
_STATUS = {"draft": "BROUILLON", "for_review": "POUR REVUE", "for_information": "POUR INFORMATION",
           "for_construction": "POUR CONSTRUCTION", "as_built": "TEL QUE CONSTRUIT"}


def register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    with _FONT_LOCK:
        for name, file in ((FONT_REGULAR, "Geist-Regular.ttf"), (FONT_BOLD, "Geist-Bold.ttf")):
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(Path(__file__).parent / "web/brand" / file)))


def text_width(text, size, bold=False):
    from reportlab.pdfbase import pdfmetrics

    register_fonts()
    return pdfmetrics.stringWidth(text, FONT_BOLD if bold else FONT_REGULAR, size)


def cad_text_height(size, bold=False):
    """DXF TEXT height is cap height; PDF font size is an em, both in mm."""
    from reportlab.pdfbase import pdfmetrics

    register_fonts()
    face = pdfmetrics.getFont(FONT_BOLD if bold else FONT_REGULAR).face
    return size * face.capHeight / 1000


def wrap_text(value, width, size, *, bold=False):
    """Wrap every character, including long unbroken references; never truncate."""
    lines = []
    for paragraph in str(value).replace("\t", " ").split("\n"):
        line = ""
        for word in paragraph.split():
            candidate = (line + " " + word).strip()
            if text_width(candidate, size, bold) <= width:
                line = candidate
                continue
            if line:
                lines.append(line)
                line = ""
            for char in word:
                if line and text_width(line + char, size, bold) > width:
                    lines.append(line)
                    line = ""
                line += char
        lines.append(line)
    return lines or [""]


@dataclass
class SheetScene:
    width_mm: float
    height_mm: float
    shapes: list[dict]
    warnings: list[str]
    diagram_box: tuple[float, float, float, float]
    # Physical affine transform of legacy drawing coordinates: x'=scale*x+dx.
    diagram_transform: tuple[float, float, float]


def paper_dimensions(settings):
    short, long = PAPER_MM[settings.paper_size]
    return (long, short) if settings.orientation == "landscape" else (short, long)


def _shape_bounds(shape):
    kind = shape["kind"]
    if kind in ("polyline", "polygon"):
        xs, ys = zip(*shape["points"])
        return min(xs), min(ys), max(xs), max(ys)
    x, y = shape["x"], shape["y"]
    if kind == "text":
        width = text_width(shape["text"], shape["size"], shape.get("bold", False))
        left = x - width / 2 if shape["anchor"] == "middle" else x
        return left, y - shape["size"], left + width, y + shape["size"] * .25
    if kind == "rect":
        return x, y, x + shape["width"], y + shape["height"]
    rx, ry = (shape["radius"],) * 2 if kind == "circle" else (shape["rx"], shape["ry"])
    return x - rx, y - ry, x + rx, y + ry


def _intersects_pipe(bounds, segments):
    x1, y1, x2, y2 = bounds
    return any(max(a[0], b[0]) >= x1 - .5 and min(a[0], b[0]) <= x2 + .5
               and max(a[1], b[1]) >= y1 - .4 and min(a[1], b[1]) <= y2 + .4
               for a, b in segments)


def _caption(original, shape, scale, dx, dy, plot, pipe_segments):
    route = [(x * scale + dx, y * scale + dy) for x, y in original["route_points"]]
    horizontal = sorted(((a, b) for a, b in zip(route, route[1:]) if abs(a[1] - b[1]) < 1e-6),
                        key=lambda pair: abs(pair[1][0] - pair[0][0]), reverse=True)
    px, py, pw, ph = plot
    for start, end in horizontal[:6]:
        available = min(pw, abs(end[0] - start[0]) - 4)
        if available < 12:
            continue
        lines = wrap_text(original["full_text"], available, 2.5)
        if len(lines) > 3:
            continue
        for above in (True, False):
            labels = []
            for index, value in enumerate(lines):
                baseline = start[1] - 2 - (len(lines) - 1 - index) * 3.3 if above else start[1] + 4 + index * 3.3
                label = {**shape, "x": (start[0] + end[0]) / 2, "y": baseline,
                         "text": value, "size": 2.5, "anchor": "middle"}
                bounds = _shape_bounds(label)
                if bounds[0] < px or bounds[2] > px + pw or bounds[1] < py or bounds[3] > py + ph or _intersects_pipe(bounds, pipe_segments):
                    break
                labels.append(label)
            if len(labels) == len(lines):
                return labels
    return None


def sheet_scene(document, legacy_shapes) -> SheetScene:
    """Create one editable folio. Source coordinates are schematic, not lengths."""
    settings = document.drawing
    compact = settings.layout_style == "compact"
    width, height = paper_dimensions(settings)
    shapes, warnings = [], []
    left, top, right, bottom = 20.0, 10.0, width - 10.0, height - 10.0
    inner_width = right - left
    block_width = 180.0
    block_left = right - block_width

    def add(kind, layer, **values):
        shapes.append({"kind": kind, "layer": layer, "stroke": "#000000", "fill": "none",
                       "lineweight": .18, **values})

    def line(points, layer="PID_TITLEBLOCK", weight=.18, **values):
        add("polyline", layer, points=points, lineweight=weight, **values)

    def text(x, y, value, size=2.5, layer="PID_TITLEBLOCK", bold=False, anchor="start"):
        add("text", layer, x=x, y=y, text=value, size=size, bold=bold, anchor=anchor,
            stroke="none", fill="#000000")

    # Measure the title block before placing it. Values keep fixed physical type.
    fields = [
        [("ENTREPRISE", settings.company, 90, 3.0), ("CLIENT", settings.client, 90, 3.0)],
        [("TITRE DU PLAN", settings.drawing_title or document.title, 180, 3.5)],
        [("RÉFÉRENCE PROJET", settings.project_reference, 60, 2.5),
         ("SITE", settings.site, 60, 2.5), ("UNITÉ / INSTALLATION", settings.unit, 60, 2.5)],
        [("NUMÉRO DE DOCUMENT", settings.document_number, 90, 3.5),
         ("RÉVISION", settings.revision, 30, 3.5), ("DATE D'ÉMISSION", settings.issue_date, 60, 2.5)],
        [("DESSINÉ PAR", settings.drawn_by, 60, 2.5), ("VÉRIFIÉ PAR", settings.checked_by, 60, 2.5),
         ("APPROUVÉ PAR", settings.approved_by, 60, 2.5)],
        [("STATUT", _STATUS[settings.status], 75, 2.7),
         ("FOLIO", f"{settings.sheet_number} / {settings.sheet_total}", 30, 2.7),
         ("FORMAT", settings.paper_size + (" / P" if settings.orientation == "portrait" else " / L"), 30, 2.7),
         ("ÉCHELLE", "SANS ÉCHELLE", 45, 2.7)],
    ]
    if compact:
        fields = [[(label, value, cell_width, min(size, 3.0 if index in (1, 3) else 2.5))
                   for label, value, cell_width, size in row] for index, row in enumerate(fields)]
    rows = []
    for index, fields_in_row in enumerate(fields):
        cells = [(label, wrap_text(value or "Non renseigné", cell_width - 4, size, bold=index in (1, 3)),
                  cell_width, size) for label, value, cell_width, size in fields_in_row]
        row_height = (max(5 + len(lines) * size * 1.2 for _, lines, _, size in cells) if compact
                      else max(4.6 + len(lines) * size * 1.3 for _, lines, _, size in cells) + 3)
        rows.append((cells, row_height, index in (1, 3)))
    title_height = sum(row[1] for row in rows)
    revision_widths = [12, 19, 65, 28, 28, 28]
    revision_rows = []
    for index in range(max(1, len(settings.revisions)) if compact else 5):
        record = settings.revisions[index] if index < len(settings.revisions) else None
        values = [record.revision, record.date, record.description, record.drawn_by, record.checked_by, record.approved_by] if record else [""] * 6
        lines = [wrap_text(value, cell_width - 2, 2.2) for value, cell_width in zip(values, revision_widths, strict=True)]
        revision_rows.append((lines, max(6, max(len(value) for value in lines) * 2.8 + 2)))
    revision_heading_height = 10 if compact else 12
    revision_height = revision_heading_height + sum(row[1] for row in revision_rows)
    right_height = title_height + (2 if compact else 3) + revision_height
    side_by_side = inner_width - block_width - 6 >= 55
    notes_width = inner_width - block_width - 6 if side_by_side else inner_width
    notes_lines = wrap_text(settings.notes, notes_width - 4, 2.5) if settings.notes.strip() else []
    notes_height = (7 + len(notes_lines) * 3.3) if notes_lines else 0
    from .pid_conventions import service_definition

    services = [service_definition(service) for service in dict.fromkeys(
        connection.service for connection in document.connections if connection.service != "unspecified")]
    service_columns = 2 if notes_width >= 150 else 1
    service_rows = (len(services) + service_columns - 1) // service_columns
    legend_height = (30 + (6 + service_rows * 5 if services else 0)) if settings.show_legend else 0
    annotations_height = notes_height + legend_height + (3 if notes_height and legend_height else 0)
    reserve = max(right_height, annotations_height) if side_by_side else right_height + annotations_height + (4 if annotations_height else 0)
    if bottom - reserve - top < 35:
        raise ValueError("Cartouche, révisions et notes trop chargés pour ce format ; choisir une feuille plus grande ou alléger les textes.")
    title_top = bottom - title_height
    rev_top = title_top - (2 if compact else 3) - revision_height

    # Frame and modest coordinate zones remain outside all content rectangles.
    add("rect", "PID_BORDER", x=left, y=top, width=inner_width, height=bottom - top, lineweight=.7)
    zone_count = max(4, round(inner_width / 70))
    for index in range(zone_count):
        x = left + (index + .5) * inner_width / zone_count
        text(x, 7.5, str(index + 1), 2.5, "PID_BORDER", anchor="middle")
        text(x, height - 4.5, str(index + 1), 2.5, "PID_BORDER", anchor="middle")
        if index:
            zone_x = left + index * inner_width / zone_count
            line([(zone_x, top), (zone_x, top + 2)], "PID_BORDER", .35)
            line([(zone_x, bottom), (zone_x, bottom + 2)], "PID_BORDER", .35)
    vertical_zones = max(3, round((bottom - top) / 70))
    for index in range(vertical_zones):
        y = top + (index + .5) * (bottom - top) / vertical_zones
        label = chr(65 + index)
        text(left - 5, y + 1, label, 2.5, "PID_BORDER", anchor="middle")
        text(right + 5, y + 1, label, 2.5, "PID_BORDER", anchor="middle")

    y = title_top
    for cells, row_height, bold in rows:
        x = block_left
        for label, lines, cell_width, size in cells:
            add("rect", "PID_TITLEBLOCK", x=x, y=y, width=cell_width, height=row_height,
                lineweight=.35 if bold else .18)
            text(x + 2, y + (2.5 if compact else 3.3), label, 1.8)
            for index, value in enumerate(lines):
                baseline = y + 3 + size + index * size * 1.2 if compact else y + 6.3 + size + index * size * 1.3
                text(x + 2, baseline, value, size, bold=bold)
            x += cell_width
        y += row_height
    text(block_left + 1, rev_top + (3 if compact else 3.8), "HISTORIQUE DES RÉVISIONS", 2.5 if compact else 2.7, "PID_REVISIONS", bold=True)
    headers = ["RÉV.", "DATE", "DESCRIPTION", "DESSINÉ", "VÉRIFIÉ", "APPROUVÉ"]
    x = block_left
    for header, cell_width in zip(headers, revision_widths, strict=True):
        header_top, header_height = (4, 6) if compact else (5, 7)
        add("rect", "PID_REVISIONS", x=x, y=rev_top + header_top, width=cell_width, height=header_height, lineweight=.18)
        text(x + 1, rev_top + (8 if compact else 9.4), header, 2, "PID_REVISIONS", bold=True)
        x += cell_width
    y = rev_top + revision_heading_height
    for cells, row_height in revision_rows:
        x = block_left
        for lines, cell_width in zip(cells, revision_widths, strict=True):
            add("rect", "PID_REVISIONS", x=x, y=y, width=cell_width, height=row_height, lineweight=.18)
            for index, value in enumerate(lines):
                text(x + 1, y + 3.2 + index * 2.8, value, 2.2, "PID_REVISIONS")
            x += cell_width
        y += row_height

    annotation_top = bottom - reserve if side_by_side else rev_top - annotations_height - 4
    y = annotation_top
    if notes_lines:
        text(left + 2, y + 4, "NOTES", 2.7, bold=True)
        for index, value in enumerate(notes_lines):
            text(left + 2, y + 8 + index * 3.3, value)
        y += notes_height + 3
    if settings.show_legend:
        text(left + 2, y + 4, "LÉGENDE DES TRACÉS", 2.7, bold=True)
        line([(left + 2, y + 9), (left + 13, y + 9)], weight=.35)
        text(left + 16, y + 10, "Liaison déclarée", 2.3)
        line([(left + 2, y + 15), (left + 13, y + 15)], weight=.18, dash=True)
        text(left + 16, y + 16, "Liaison proposée, à revoir", 2.3)
        text(left + 2, y + 22, "Implantation schématique, sans échelle", 2.3)
        text(left + 2, y + 27, "CAO : 1 unité = 1 mm sur feuille", 2.3)
        if services:
            text(left + 2, y + 33, "SERVICES : CONVENTION DU PROJET", 2.1, bold=True)
            for index, service in enumerate(services):
                column, row = index % service_columns, index // service_columns
                x = left + 2 + column * notes_width / service_columns
                baseline = y + 38 + row * 5
                colour = service["color"] if settings.color_mode == "service" else "#000000"
                line([(x, baseline - 1), (x + 9, baseline - 1)], weight=.5, stroke=colour, service=service["id"])
                text(x + 12, baseline, service["code"] + " - " + service["label"], 2.1)

    plot = (left + 5, top + 9, inner_width - 10, bottom - reserve - top - 15)
    px, py, pw, ph = plot
    # First two and final legacy shapes are its title/subtitle/footer, not plant.
    plant = legacy_shapes[2:-1]
    if not plant:
        text(px + pw / 2, py + ph / 2, "Aucun équipement dans le dessin enregistré", 3,
             "PID_TEXT", anchor="middle")
        return SheetScene(width, height, shapes, warnings, plot, (1, px, py))
    bounds = [_shape_bounds(shape) for shape in plant]
    minx, miny = min(b[0] for b in bounds), min(b[1] for b in bounds)
    maxx, maxy = max(b[2] for b in bounds), max(b[3] for b in bounds)
    raw_width, raw_height = max(1, maxx - minx), max(1, maxy - miny)
    scale = min(pw / raw_width, ph / raw_height)
    # A generous physical drawing size for small diagrams; no real-world scale.
    scale = min(scale, .35)
    dense = scale < .16
    if dense:
        warnings.append("Densité du dessin élevée : symboles réduits, textes gardés lisibles ; choisir un format plus grand ou répartir les équipements sur plusieurs folios.")
    if ph < 60:
        warnings.append("Zone de dessin réduite par les métadonnées ; choisir un format plus grand.")
    dx = px + (pw - raw_width * scale) / 2 - minx * scale
    dy = py + (ph - raw_height * scale) / 2 - miny * scale
    pipe_segments = [(tuple((a[0] * scale + dx, a[1] * scale + dy)), tuple((b[0] * scale + dx, b[1] * scale + dy)))
                     for pipe in plant if pipe.get("layer") == "PID_PIPES" and pipe["kind"] == "polyline"
                     for a, b in zip(pipe["points"], pipe["points"][1:])]
    for original in plant:
        shape = dict(original)
        kind = shape["kind"]
        shape["layer"] = shape.get("layer", "PID_TEXT" if kind == "text" else "PID_EQUIPMENT")
        service = original.get("service", "unspecified")
        service_colour = service_definition(service)["color"] if service != "unspecified" and settings.color_mode == "service" else "#000000"
        shape["stroke"] = "none" if kind == "text" else service_colour
        original_fill = shape.get("fill", "none")
        shape["fill"] = service_colour if kind == "text" or original_fill in ("#23465c", "#0055dd") or original.get("service_arrow") else "#ffffff" if original_fill != "none" else "none"
        shape["lineweight"] = .5 if shape["layer"] == "PID_PIPES" else .35 if kind != "text" else .18
        if kind in ("polyline", "polygon"):
            shape["points"] = [(x * scale + dx, y * scale + dy) for x, y in shape["points"]]
        else:
            shape["x"], shape["y"] = shape["x"] * scale + dx, shape["y"] * scale + dy
            for field in ("width", "height") if kind == "rect" else ("radius",) if kind == "circle" else ("rx", "ry") if kind == "ellipse" else ():
                shape[field] *= scale
        if kind == "text":
            shape["size"] = max(1.8 if shape["size"] <= 6 else 2.5, shape["size"] * scale)
            shape["bold"] = original.get("fill") == "#0055dd"
            text_w = text_width(shape["text"], shape["size"], shape["bold"])
            # Keep every label within the print region rather than clip it.
            if text_w > pw:
                warnings.append("Libellé trop long pour la zone de dessin ; choisir un format plus grand.")
                raise ValueError("Un libellé du dessin dépasse la largeur imprimable ; choisir un format plus grand ou raccourcir le nom affiché.")
            low = px + text_w / 2 if shape["anchor"] == "middle" else px
            high = px + pw - text_w / 2 if shape["anchor"] == "middle" else px + pw - text_w
            shape["x"] = min(high, max(low, shape["x"]))
            shape["y"] = min(py + ph - .8, max(py + shape["size"], shape["y"]))
        if kind == "text" and original.get("role") == "connection_label":
            caption = _caption(original, shape, scale, dx, dy, plot, pipe_segments)
            if caption:
                shapes.extend(caption)
                continue
            warning = "Certains libellés de liaisons sont proches des conduites ; revoir leur disposition ou choisir un format plus grand."
            if warning not in warnings:
                warnings.append(warning)
        if kind == "text" and original.get("role") == "source_tag":
            # A short, bounded caption adjustment avoids a pipe through letters;
            # it does not move nodes, terminals or routes, nor infer topology.
            original_y = shape["y"]
            for offset in (0, -4, 4, -8, 8):
                shape["y"] = original_y + offset
                bx1, by1, bx2, by2 = _shape_bounds(shape)
                if by1 < py or by2 > py + ph:
                    continue
                if not _intersects_pipe((bx1, by1, bx2, by2), pipe_segments):
                    break
            else:
                shape["y"] = original_y
                warning = "Certains libellés sont proches des conduites ; revoir leur disposition ou choisir un format plus grand."
                if warning not in warnings:
                    warnings.append(warning)
        shapes.append(shape)
    if warnings:
        text(left + 5, top + 5.3, "DENSITÉ : VÉRIFIER LA LISIBILITÉ OU CHOISIR UN FORMAT PLUS GRAND", 2.2,
             "PID_TEXT", bold=True)
    return SheetScene(width, height, shapes, warnings, plot, (scale, dx, dy))
