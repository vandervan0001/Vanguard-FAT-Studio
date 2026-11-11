"""Printed CAD glyphs, colours and placement without native JSON restoration."""

import io
from pathlib import Path

import ezdxf
from ezdxf import path
from ezdxf.addons import text2path
from ezdxf.colors import aci2rgb
from ezdxf.fonts import fonts
from ezdxf.fonts.font_manager import FontManager
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
import pytest

from fat_studio.models import Connection, Equipment, Position, Project
from fat_studio.pid_cad import cad_capabilities, dwg_to_dxf
from fat_studio.pid_conventions import SERVICE_DEFINITIONS
from fat_studio.pid_export import engineering_scene, export_pid, project_document
from fat_studio.pid_titleblock import DrawingRevision, PidDrawingSettings


BRAND = Path(__file__).resolve().parents[1] / "fat_studio/web/brand"


@pytest.fixture
def bundled_cad_fonts(monkeypatch):
    manager = FontManager()
    manager.build([str(BRAND)], support_dirs=False)
    monkeypatch.setattr(fonts, "font_manager", manager)


def _project():
    return Project(id="cad-print", name="Extrait de revue", pid_drawing=PidDrawingSettings(
        drawing_title="VIRDEN / ALUN - EXTRAIT DE REVUE", document_number="EX-VIR-PID-014",
        revision="A", issue_date="2026-11-11", company="VANGUARD FAT STUDIO / EXEMPLE",
        revisions=[DrawingRevision(revision="A", date="2026-11-11",
            description="Première mise en page de l'extrait documentaire revu", drawn_by="Préparation assistée")]),
        equipment=[Equipment(id="P", name="P-101", type="pid_symbol", symbol_kind="pump", position=Position(x=0, y=0)),
                   Equipment(id="T", name="TK-102", type="pid_symbol", symbol_kind="tank", position=Position(x=500, y=0))],
        connections=[Connection(id="cold", source="P", target="T", label="Circuit déclaré", service="cold_supply")])


def _cad(payload):
    return ezdxf.read(io.StringIO(payload.decode("cp1252")))


def _glyph_bounds(entity):
    bounds = path.bbox(text2path.make_paths_from_entity(entity), fast=False)
    return bounds.extmin.x, bounds.extmin.y, bounds.extmax.x, bounds.extmax.y


def _font_outline_box(text, bold, size):
    """Independent TTF outlines/advances oracle in PDF em units."""
    font = TTFont(BRAND / ("Geist-Bold.ttf" if bold else "Geist-Regular.ttf"))
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    advance, boxes = 0, []
    for letter in text:
        name = cmap[ord(letter)]
        pen = BoundsPen(glyphs)
        glyphs[name].draw(pen)
        if pen.bounds:
            x1, y1, x2, y2 = pen.bounds
            boxes.append((x1 + advance, y1, x2 + advance, y2))
        advance += font["hmtx"][name][0]
    scale = size / font["head"].unitsPerEm
    box = (min(b[0] for b in boxes) * scale, min(b[1] for b in boxes) * scale,
           max(b[2] for b in boxes) * scale, max(b[3] for b in boxes) * scale)
    font.close()
    return box, advance * scale


@pytest.mark.parametrize("format", ["dxf", "dwg"])
def test_actual_cad_glyphs_match_pdf_em_and_center_without_alignment_fields(format, bundled_cad_fonts):
    if format == "dwg" and not cad_capabilities()["available"]:
        pytest.skip("Optional real LibreDWG unavailable")
    project = _project()
    scene = engineering_scene(project_document(project))
    payload = export_pid(project, format)[0]
    drawing = _cad(dwg_to_dxf(payload) if format == "dwg" else payload)
    # CAD drawing engine reads the real entities and TTF glyphs; no JSON import.
    entities = list(drawing.modelspace().query("TEXT"))
    labels = [shape for shape in scene.shapes if shape["kind"] == "text" and shape["text"]]
    assert len(entities) == len(labels) > 40
    for entity, label in zip(entities, labels, strict=True):
        assert entity.dxf.halign == 0 and entity.dxf.valign == 0
        assert entity.dxf.text == label["text"]
        box, advance = _font_outline_box(label["text"], label.get("bold", False), label["size"])
        left = label["x"] - advance / 2 if label["anchor"] == "middle" else label["x"]
        baseline = scene.height_mm - label["y"]
        assert _glyph_bounds(entity) == pytest.approx(
            (left + box[0], baseline + box[1], left + box[2], baseline + box[3]), abs=1e-7)
    assert drawing.styles.get("PID_REGULAR").dxf.font == "Geist-Regular.ttf"
    assert drawing.styles.get("PID_BOLD").dxf.font == "Geist-Bold.ttf"
    description = next(entity for entity in entities if entity.dxf.text.startswith("Première mise"))
    assert _glyph_bounds(description)[2] < 325  # Description cell ends at x=326 mm.


def test_every_service_colour_has_an_exact_r2000_palette_representation():
    for service in SERVICE_DEFINITIONS:
        if service["id"] == "unspecified":
            continue
        assert "#%02x%02x%02x" % tuple(aci2rgb(service["aci"])) == service["color"].lower()


@pytest.mark.parametrize("mode", ["service", "monochrome"])
@pytest.mark.parametrize("format", ["dxf", "dwg"])
def test_service_codes_and_legend_are_retained_with_matching_actual_cad_colours(mode, format):
    if format == "dwg" and not cad_capabilities()["available"]:
        pytest.skip("Optional real LibreDWG unavailable")
    project = _project()
    project.pid_drawing.color_mode = mode
    scene = engineering_scene(project_document(project))
    payload = export_pid(project, format)[0]
    drawing = _cad(dwg_to_dxf(payload) if format == "dwg" else payload)
    actual = [entity for entity in drawing.modelspace() if entity.dxftype() != "HATCH"]
    visible_shapes = [shape for shape in scene.shapes if shape["kind"] != "text" or shape["text"]]
    assert len(actual) == len(visible_shapes)
    assert any("CHWS" in shape.get("text", "") and shape.get("role") == "connection_label" for shape in scene.shapes)
    assert any("CHWS - Départ froid" == shape.get("text") for shape in scene.shapes)
    service_shapes = [(shape, entity) for shape, entity in zip(visible_shapes, actual, strict=True) if shape.get("service") == "cold_supply"]
    assert len(service_shapes) >= 4  # Pipe, arrow, caption, legend swatch.
    for shape, entity in service_shapes:
        expected = shape["fill"] if shape["kind"] == "text" else shape["stroke"]
        if mode == "monochrome":
            assert expected == "#000000" and entity.dxf.color == 7
        else:
            assert expected.lower() == "#%02x%02x%02x" % tuple(aci2rgb(entity.dxf.color))


def test_compact_titleblock_removes_only_unused_history_rows_and_frees_plot_area():
    project = _project()
    compact = engineering_scene(project_document(project))
    project.pid_drawing.layout_style = "full"
    full = engineering_scene(project_document(project))
    def cells(scene):
        return [shape for shape in scene.shapes if shape["kind"] == "rect" and shape["layer"] in ("PID_TITLEBLOCK", "PID_REVISIONS")]
    compact_height = max(shape["y"] + shape["height"] for shape in cells(compact)) - min(shape["y"] for shape in cells(compact))
    full_height = max(shape["y"] + shape["height"] for shape in cells(full)) - min(shape["y"] for shape in cells(full))
    assert compact_height < .65 * full_height
    assert compact.diagram_box[3] > full.diagram_box[3] + 35
    assert len([shape for shape in cells(compact) if shape["layer"] == "PID_REVISIONS"]) == 12
    assert len([shape for shape in cells(full) if shape["layer"] == "PID_REVISIONS"]) == 36
    assert {shape["text"] for shape in compact.shapes if shape["kind"] == "text"} == {shape["text"] for shape in full.shapes if shape["kind"] == "text"}


@pytest.mark.parametrize("format", ["dxf", "dwg"])
def test_cad_preserves_white_symbol_masks_and_coloured_arrow_fills_in_painter_order(format):
    if format == "dwg" and not cad_capabilities()["available"]:
        pytest.skip("Optional real LibreDWG unavailable")
    project = _project()
    project.equipment[0].symbol_kind = "ball_valve"
    scene = engineering_scene(project_document(project))
    payload = export_pid(project, format)[0]
    drawing = _cad(dwg_to_dxf(payload) if format == "dwg" else payload)
    entities = iter(drawing.modelspace())
    expected_fills = 0
    for shape in scene.shapes:
        if shape["kind"] == "text" and not shape["text"]:
            continue
        if shape["kind"] not in ("text", "polyline") and shape.get("fill") not in (None, "none"):
            hatch = next(entities)
            assert hatch.dxftype() == "HATCH" and hatch.dxf.solid_fill == 1
            assert hatch.dxf.color == (255 if shape["fill"] == "#ffffff" else 152)
            assert hatch.paths and len(hatch.paths) == 1
            # White masks must precede their black outline, exactly as PDF
            # fill then stroke. They hide intersecting art beneath the circle.
            expected_fills += 1
        assert next(entities).dxftype() != "HATCH"
    assert next(entities, None) is None
    assert expected_fills >= 6
