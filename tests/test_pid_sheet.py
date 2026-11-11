"""Physical print geometry, readable document control and honest native exchange."""

import base64
import io
import json
from pathlib import Path

import ezdxf
from PIL import Image
from pypdf import PdfReader
import pytest
from reportlab.lib.units import mm

from fat_studio.exchange import read_project
from fat_studio.models import Connection, Equipment, Position, Project
from fat_studio.pid_cad import cad_capabilities, dwg_to_dxf
from fat_studio.pid_export import engineering_scene, export_pid, export_pid_preview, project_document
from fat_studio.pid_import import inspect_pid
from fat_studio.pid_sheet import PAPER_MM, _shape_bounds, text_width, wrap_text
from fat_studio.pid_titleblock import DrawingRevision, PidDrawingSettings


def _project(settings=None):
    return Project(id="print-sheet", name="Plan schématique", pid_drawing=settings or PidDrawingSettings(), equipment=[
        Equipment(id="P", name="P-1", type="pid_symbol", symbol_kind="pump", position=Position(x=0, y=0)),
        Equipment(id="T", name="TK-2", type="pid_symbol", symbol_kind="tank", position=Position(x=100, y=0)),
    ], connections=[Connection(id="pipe", source="P", target="T", source_port="out", target_port="in")])


def _cad(payload):
    return ezdxf.read(io.StringIO(payload.decode("cp1252")))


@pytest.mark.parametrize("size", PAPER_MM)
@pytest.mark.parametrize("orientation", ["portrait", "landscape"])
def test_pdf_and_cad_use_exact_printed_paper_dimensions_in_mm(size, orientation):
    project = _project(PidDrawingSettings(paper_size=size, orientation=orientation))
    short, long = PAPER_MM[size]
    expected = (long, short) if orientation == "landscape" else (short, long)
    pdf = PdfReader(io.BytesIO(export_pid(project, "pdf")[0]))
    assert len(pdf.pages) == 1
    assert (float(pdf.pages[0].mediabox.width), float(pdf.pages[0].mediabox.height)) == pytest.approx(
        (expected[0] * mm, expected[1] * mm), abs=1e-3)
    drawing = _cad(export_pid(project, "dxf")[0])
    assert drawing.units == 4
    assert "PID_SHEET" in drawing.layouts.names(), list(drawing.layouts.names())
    layout = drawing.layouts.get("PID_SHEET")
    assert (layout.dxf.paper_width, layout.dxf.paper_height) == pytest.approx(expected)
    assert (layout.dxf.scale_numerator, layout.dxf.scale_denominator) == (1, 1)
    assert any((v.dxf.width, v.dxf.height, v.dxf.view_height) == pytest.approx((expected[0], expected[1], expected[1]))
               for v in layout.query("VIEWPORT"))
    restored = inspect_pid(export_pid(project, "pdf")[0], "printed.pdf", ocr=False)
    assert restored.drawing == project.pid_drawing


def test_independent_a3_oracle_preserves_35mm_pitch_and_180mm_titleblock_without_scene_helper():
    # Two 100-unit symbols 100 units apart fit with the documented .35 cap.
    # This oracle deliberately does not use engineering_scene/diagram_transform.
    drawing = _cad(export_pid(_project(), "dxf")[0])
    circles = list(drawing.modelspace().query("CIRCLE"))
    assert len(circles) == 1
    assert circles[0].dxf.radius == pytest.approx(8.75)
    tank_x = {round(entity.dxf.center.x, 7) for entity in drawing.modelspace().query("ELLIPSE")}
    assert len(tank_x) == 1
    assert next(iter(tank_x)) - circles[0].dxf.center.x == pytest.approx(35)
    block = [list(entity.get_points("xy")) for entity in drawing.modelspace().query("LWPOLYLINE")
             if entity.dxf.layer == "PID_TITLEBLOCK" and entity.closed]
    assert min(x for points in block for x, _ in points) == pytest.approx(230)
    assert max(x for points in block for x, _ in points) == pytest.approx(410)


def _maximum_settings():
    return PidDrawingSettings(paper_size="A2", company="C" * 100, client="L" * 100,
        project_reference="P" * 64, site="S" * 100, unit="U" * 80, drawing_title="T" * 160,
        document_number="N" * 64, revision="R" * 16, issue_date="2026-11-11",
        drawn_by="D" * 64, checked_by="V" * 64, approved_by="A" * 64,
        notes=("Note complète de conception. " * 50)[:1200], sheet_number=12, sheet_total=23,
        revisions=[DrawingRevision(revision=f"REV{i}-" + "R" * 11, date="2026-11-11",
            description=str(i) + "E" * 139, drawn_by="d" * 64, checked_by="v" * 64, approved_by="a" * 64)
            for i in range(5)])


def test_maximum_title_revision_and_notes_values_wrap_without_truncation_or_cell_overflow():
    project = _project(_maximum_settings())
    sheet = engineering_scene(project_document(project))
    source = project.pid_drawing.model_dump()
    pdf = PdfReader(io.BytesIO(export_pid(project, "pdf")[0]))
    joined = "".join(pdf.pages[0].extract_text().split())
    for key in ("company", "client", "project_reference", "site", "unit", "drawing_title", "document_number",
                "revision", "issue_date", "drawn_by", "checked_by", "approved_by", "notes"):
        assert "".join(source[key].split()) in joined, key
    for record in source["revisions"]:
        for key, value in record.items():
            assert "".join(value.split()) in joined, key
    assert "12/23" in joined
    for layer in ("PID_TITLEBLOCK", "PID_REVISIONS"):
        cells = [shape for shape in sheet.shapes if shape["layer"] == layer and shape["kind"] == "rect"]
        low_y = min(shape["y"] for shape in cells)
        low_x = min(shape["x"] for shape in cells)
        for shape in sheet.shapes:
            if shape["layer"] != layer or shape["kind"] != "text" or shape["y"] < low_y or shape["x"] < low_x:
                continue
            x1, y1, x2, y2 = _shape_bounds(shape)
            assert any(x1 >= cell["x"] + .1 and x2 <= cell["x"] + cell["width"] - .1
                       and y1 >= cell["y"] + .1 and y2 <= cell["y"] + cell["height"] - .1
                       for cell in cells), shape
    assert min(shape["size"] for shape in sheet.shapes if shape["kind"] == "text") >= 1.8


def test_impossible_small_sheet_metadata_is_rejected_instead_of_shrunk_or_clipped():
    settings = _maximum_settings()
    settings.paper_size = "A4"
    settings.layout_style = "full"
    with pytest.raises(ValueError, match="format|feuille plus grande"):
        export_pid(_project(settings), "pdf")


def test_long_unbroken_references_and_notes_preserve_all_characters():
    value = "ABC_" * 40
    lines = wrap_text(value, 20, 2.5)
    assert "".join(lines) == value
    assert all(text_width(line, 2.5) <= 20 for line in lines)


def test_bottom_zone_ticks_stay_outside_titleblock_and_values_have_bottom_padding():
    sheet = engineering_scene(project_document(_project()))
    bottom = sheet.height_mm - 10
    ticks = [shape for shape in sheet.shapes if shape["layer"] == "PID_BORDER" and shape["kind"] == "polyline"
             and shape["points"][0][1] == bottom]
    assert ticks and all(point[1] >= bottom for tick in ticks for point in tick["points"])
    cells = [shape for shape in sheet.shapes if shape["kind"] == "rect" and shape["layer"] == "PID_TITLEBLOCK"]
    last_top = max(cell["y"] for cell in cells)
    values = [shape for shape in sheet.shapes if shape["kind"] == "text" and shape["layer"] == "PID_TITLEBLOCK"
              and shape["y"] > last_top + 5]
    assert values and all(_shape_bounds(shape)[3] <= bottom - 1 for shape in values)


def test_pdf_fonts_are_embedded_and_empty_visas_do_not_become_signatures_or_dates():
    pdf = PdfReader(io.BytesIO(export_pid(_project(), "pdf")[0]))
    fonts = [font.get_object() for font in pdf.pages[0]["/Resources"]["/Font"].values()]
    embedded = [font for font in fonts if "/FontDescriptor" in font and "/FontFile2" in font["/FontDescriptor"]]
    assert len(embedded) >= 2  # Existing Geist regular and bold files are embedded.
    text = pdf.pages[0].extract_text()
    assert "BROUILLON" in text and "Non renseigné" in text and "SANS ÉCHELLE" in text
    assert "2026-11-11" not in text and "signature" not in text.lower()


def test_pdf_document_properties_preserve_company_title_number_revision_and_creation_date():
    project = _project(PidDrawingSettings(company="Entreprise explicitement déclarée",
        drawing_title="Titre métier déclaré", document_number="BE-PID-204", revision="B3", issue_date="2000-01-02"))
    metadata = PdfReader(io.BytesIO(export_pid(project, "pdf")[0])).metadata
    assert metadata.title == "Titre métier déclaré" and metadata.author == "Entreprise explicitement déclarée"
    assert metadata.subject == "BE-PID-204 - Révision B3"
    assert metadata.creator == "Vanguard FAT Studio"
    assert metadata.get("/CreationDate") and "20000102" not in metadata["/CreationDate"]
    assert project.pid_drawing.issue_date == "2000-01-02"  # Declared issue date is not the file creation time.


def test_caption_avoids_its_vertical_pipe_and_preserves_every_endpoint():
    project = Project(id="caption", name="Branche", equipment=[
        Equipment(id="V", name="TV-1", type="pid_symbol", symbol_kind="three_way_valve", position=Position(x=0, y=200)),
        Equipment(id="H", name="HX-2", type="pid_symbol", symbol_kind="heat_exchanger", position=Position(x=500, y=80))],
        connections=[Connection(id="A", source="V", target="H", source_port="A", target_port="secondary_in",
                                label="Branche A - source déclarée")])
    sheet = engineering_scene(project_document(project))
    captions = [shape for shape in sheet.shapes if shape.get("role") == "connection_label"]
    assert " ".join(shape["text"] for shape in captions) == "Branche A - source déclarée"
    pipes = [shape for shape in sheet.shapes if shape["layer"] == "PID_PIPES" and shape["kind"] == "polyline"]
    for label in captions:
        x1, y1, x2, y2 = _shape_bounds(label)
        assert not any(max(a[0], b[0]) >= x1 - .3 and min(a[0], b[0]) <= x2 + .3
                       and max(a[1], b[1]) >= y1 - .3 and min(a[1], b[1]) <= y2 + .3
                       for pipe in pipes for a, b in zip(pipe["points"], pipe["points"][1:]))
    # Independently rotate the two named terminals and apply only the sheet fit.
    scale, dx, dy = sheet.diagram_transform
    source = (170 * scale + dx, 278 * scale + dy)
    target = (570 * scale + dx, 183 * scale + dy)
    assert any(pipe["points"][0] == pytest.approx(source) and pipe["points"][-1] == pytest.approx(target) for pipe in pipes)


@pytest.mark.parametrize("size,orientation", [("A4", "portrait"), ("A3", "landscape"), ("A0", "portrait")])
def test_preview_is_bounded_monochrome_and_never_mutates_drawing_settings(size, orientation):
    project = _project(PidDrawingSettings(paper_size=size, orientation=orientation))
    before = project.model_dump_json()
    result = export_pid_preview(project)
    image = base64.b64decode(result["image_data_url"].split(",", 1)[1])
    with Image.open(io.BytesIO(image)) as image:
        assert image.width <= 1600 and image.height <= 1100
        assert all(max(pixel) - min(pixel) <= 2 for pixel in image.convert("RGB").get_flattened_data())
    assert result["width_mm"] in PAPER_MM[size] and result["height_mm"] in PAPER_MM[size]
    assert project.model_dump_json() == before


def test_dense_drawing_warns_without_shrinking_plot_text_below_readable_minimum():
    project = _project()
    project.equipment.extend(Equipment(id=f"E{i}", name=f"P-{i}", type="pid_symbol", symbol_kind="pump",
        position=Position(x=i * 8000, y=i * 8000)) for i in range(2, 12))
    scene = engineering_scene(project_document(project))
    assert any("Densité" in warning for warning in scene.warnings)
    assert all(shape["size"] >= 1.8 for shape in scene.shapes if shape["kind"] == "text")


def test_real_dwg_preserves_mm_sheet_1to1_layout_lineweights_and_dash():
    if not cad_capabilities()["available"]:
        pytest.skip("Optional real LibreDWG unavailable")
    project = _project(PidDrawingSettings(document_number="DWG-CONTROL", company="Exemple déclaré"))
    project.pid_document = project_document(project)
    project.pid_document.connections[0].inferred = True
    payload = export_pid(project, "dwg")[0]
    assert payload.startswith(b"AC1015")
    drawing = _cad(dwg_to_dxf(payload))
    assert drawing.units == 4
    layout = drawing.layouts.get("PID_SHEET")
    assert (layout.dxf.paper_width, layout.dxf.paper_height) == (420, 297)
    assert (layout.dxf.scale_numerator, layout.dxf.scale_denominator) == (1, 1)
    assert any((v.dxf.width, v.dxf.height, v.dxf.view_height) == pytest.approx((420, 297, 297)) for v in layout.query("VIEWPORT"))
    assert drawing.layers.get("PID_BORDER").dxf.lineweight == 70
    assert drawing.layers.get("PID_PIPES").dxf.lineweight == 50
    assert any(entity.dxf.get("linetype") == "PID_DASHED" for entity in drawing.modelspace())
    text = [entity.dxf.text for entity in drawing.modelspace().query("TEXT")]
    assert "DWG-CONTROL" in text and "Exemple déclaré" in text
    restored = inspect_pid(payload, "roundtrip.dwg", ocr=False)
    assert restored.drawing == project.pid_drawing


def test_public_thermal_example_keeps_drawing_ports_and_full_project_metadata():
    source = Path(__file__).resolve().parents[1] / "examples/pid-thermal-loop.project.json"
    project = read_project(json.loads(source.read_text(encoding="utf-8")))
    project.pid_drawing.document_number = "THERMAL-PID-001"
    document = project_document(project)
    assert document.drawing.document_number == "THERMAL-PID-001"
    assert next(item for item in document.equipment if item.id == "V3").type == "three_way_valve"
    assert {(edge.source_port, edge.target_port) for edge in document.connections} >= {("A", "secondary_in"), ("B", "in")}
