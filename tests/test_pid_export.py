"""Observable interchange: inert drawing output and exact native metadata."""

import csv
import io
import json
from urllib.parse import unquote
from xml.etree import ElementTree as ET
import zipfile

import ezdxf
from PIL import Image
from pypdf import PdfReader
import pytest

from fat_studio.demo import demo_project
from fat_studio.models import Equipment, Position, Project
from fat_studio.pid_export import EXPORT_FORMATS, export_pid, project_document
from fat_studio.pid_models import PidDocument, PidEquipment
from fat_studio.pid_import import inspect_pid


def test_document_is_current_drawing_without_plc_configuration():
    project = demo_project()
    project.pid_document = PidDocument(
        source_name="source.pdf", source_sha256="a" * 64, source_format="pdf",
        equipment=[PidEquipment(id="P101", name="Original", source_tag="P-101", confidence=.7, provenance="page 2"),
                   PidEquipment(id="discarded", name="Non sélectionné")],
    )
    project.equipment[1].name = "Pompe revue"
    project.equipment[1].position = Position(x=-200, y=350)
    document = project_document(project)
    pump = next(item for item in document.equipment if item.id == "P101")
    assert pump.name == "Pompe revue" and pump.position.x == -200
    assert pump.source_tag == "P-101" and pump.confidence == .7
    assert document.source_name == "source.pdf" and document.source_sha256 == "a" * 64
    assert "discarded" not in {item.id for item in document.equipment}
    assert not document.pages
    assert "plc" not in document.model_dump() and "tags" not in document.model_dump()
    assert "ns=3" not in document.model_dump_json()
    assert len(project.pid_document.equipment) == 2


def test_full_source_metadata_stays_exportable():
    project = demo_project()
    metadata = {f"key{i}": str(i) for i in range(40)}
    project.pid_document = PidDocument(metadata=metadata)
    assert project_document(project).metadata == metadata


@pytest.mark.parametrize("format", [format for format in EXPORT_FORMATS if format != "dwg"])
def test_all_local_formats_export_empty_project(format):
    payload, media_type, extension = export_pid(Project(id="empty", name="Vide"), format)
    assert len(payload) > 40 and media_type and extension


def test_svg_is_vector_and_escapes_untrusted_text():
    project = demo_project()
    project.name = '<script>alert("x")</script> & cuve\x00'
    project.equipment[0].name = '<image href="https://example.invalid/">'
    payload, _, _ = export_pid(project, "svg")
    drawing = ET.fromstring(payload)
    assert not drawing.findall(".//{*}script") and not drawing.findall(".//{*}image")
    metadata = drawing.find("{*}metadata")
    native = PidDocument.model_validate_json(metadata.text)
    assert native.title == project.name
    assert drawing.find("{*}ellipse") is not None and drawing.find("{*}polygon") is not None
    assert "<script>" in drawing.find("{*}title").text


def test_pdf_vectors_readable_text_and_attachment():
    project = demo_project()
    project.name = "P&ID · réservoir à Zürich"
    payload, media_type, extension = export_pid(project, "pdf")
    assert payload.startswith(b"%PDF-") and media_type == "application/pdf" and extension == "pdf"
    pdf = PdfReader(io.BytesIO(payload))
    assert len(pdf.pages) == 1 and "réservoir" in pdf.pages[0].extract_text()
    content = pdf.pages[0].get_contents().get_data()
    assert b" m" in content and b" l" in content  # Actual vector paths, not a screenshot.
    assert PidDocument.model_validate_json(pdf.attachments["fat-studio-pid.json"][0]) == project_document(project)


def test_png_pixels_and_exact_native_metadata():
    project = demo_project()
    payload, media_type, extension = export_pid(project, "png")
    assert media_type == "image/png" and extension == "png"
    with Image.open(io.BytesIO(payload)) as image:
        assert image.width > 1500 and image.height > 1000
        assert PidDocument.model_validate_json(image.info["fat-studio-pid"]) == project_document(project)
        assert image.convert("RGB").getextrema() != ((255, 255),) * 3


def test_dxf_contains_geometry_and_exact_metadata():
    project = demo_project()
    payload, _, _ = export_pid(project, "dxf")
    drawing = ezdxf.read(io.StringIO(payload.decode("cp1252")))
    assert len(drawing.modelspace().query("CIRCLE")) >= 4
    assert len(drawing.modelspace().query("LWPOLYLINE")) >= 10
    assert any(entity.dxf.text == "TK-101" for entity in drawing.modelspace().query("TEXT"))
    record = "".join(value for code, value in drawing.rootdict["FAT_STUDIO_PID"].tags if code == 1)
    assert PidDocument.model_validate_json(record) == project_document(project)


def test_graph_json_uses_scott_duncan_schema_and_positions():
    project = demo_project()
    graph = json.loads(export_pid(project, "graph")[0])
    assert set(graph) == {"schema_version", "generator", "generated_at", "plant", "nodes", "edges", "stats", "issues", "fat_studio_drawing"}
    assert graph["fat_studio_drawing"] == project.pid_drawing.model_dump(mode="json")
    assert graph["plant"]["id"] == project.id
    assert graph["nodes"][0]["attributes"]["position"] == project.equipment[0].position.model_dump()
    assert graph["edges"][0]["source"] == project.connections[0].source
    assert all("type" in edge and "derived" in edge for edge in graph["edges"])


def test_graphml_preserves_connections_directedness_and_metadata():
    project = demo_project()
    project.connections[0].directed = False
    root = ET.fromstring(export_pid(project, "graphml")[0])
    graph = root.find("{*}graph")
    assert len(graph.findall("{*}node")) == len(project.equipment)
    assert graph.find("{*}edge").get("directed") == "false"
    assert PidDocument.model_validate_json(graph.find("{*}data[@key='pid_document']").text) == project_document(project)


def test_csv_has_two_tables_and_no_formula_injection():
    project = demo_project()
    project.equipment[0].name = '=WEBSERVICE("https://example.invalid")'
    project.connections[0].label = "  +1+1"
    payload, _, _ = export_pid(project, "csv")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert set(archive.namelist()) == {"equipment.csv", "connections.csv", "fat-studio-pid.json"}
        equipment = list(csv.DictReader(io.StringIO(archive.read("equipment.csv").decode("utf-8-sig"))))
        connections = list(csv.DictReader(io.StringIO(archive.read("connections.csv").decode("utf-8-sig"))))
        assert equipment[0]["name"].startswith("'=")
        assert connections[0]["label"].startswith("'  +")
        assert equipment[0]["x"] == str(project.equipment[0].position.x)
        assert PidDocument.model_validate_json(archive.read("fat-studio-pid.json")) == project_document(project)


def test_drawio_symbols_are_self_contained_and_ids_do_not_collide():
    project = Project(id="drawing", name="Exemple", equipment=[Equipment(id="fat-studio-pid", name="Réservoir", type="tank")])
    root = ET.fromstring(export_pid(project, "drawio")[0])
    cells = root.findall(".//mxCell")
    assert len({cell.get("id") for cell in cells}) == len(cells)
    symbol = next(cell for cell in cells if cell.get("vertex") == "1")
    styles = dict(item.split("=", 1) for item in symbol.get("style").split(";") if "=" in item)
    assert styles["image"].startswith("data:image/svg+xml,")
    svg = ET.fromstring(unquote(styles["image"].split(",", 1)[1]))
    assert svg.find("{*}rect") is not None  # Tank shell retained in draw.io.
    assert PidDocument.model_validate_json(root.find(".//object").get("pid")) == project_document(project)


def test_unknown_format_refused():
    with pytest.raises(ValueError, match="Format P&ID inconnu"):
        export_pid(demo_project(), "exe")


@pytest.mark.parametrize("format", ["json", "svg", "pdf", "png", "dxf", "graphml", "csv", "drawio"])
def test_export_import_restores_drawing_without_ocr_or_process_configuration(format):
    project = demo_project()
    payload, _, extension = export_pid(project, format)
    imported = inspect_pid(payload, "roundtrip." + extension, ocr=False)
    original = project_document(project)
    assert imported.equipment == original.equipment
    assert imported.connections == original.connections
