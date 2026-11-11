"""Documentary equipment, native interchange and visible multiport CAD geometry.

Native roundtrips test embedded data, not recognition of arbitrary P&ID symbols.
The separate stripped-CAD cases verify real entities and terminal coordinates.
"""

import csv
import io
import json
import math
from xml.etree import ElementTree as ET
import zipfile

import ezdxf
from PIL import Image
from pypdf import PdfReader
import pytest

from fat_studio import pid_cad
from fat_studio.demo import demo_project
from fat_studio.engine import DemoController, ProcessEngine
from fat_studio.models import Connection, Equipment, Position, Project, Tag, validate_project
from fat_studio.pid_exchange import PidPrepareRequest, prepare_pid
from fat_studio.pid_export import EXPORT_FORMATS, engineering_scene, export_pid, project_document
from fat_studio.pid_import import inspect_pid
from fat_studio.pid_models import PidConnection, PidDocument, PidEquipment, PidPosition
from fat_studio.pid_symbols import PID_SYMBOLS


# Keep the historical multiport drawing witness below the project safety bound
# of 50 objects. The 20 sourced/function additions are covered as a separate
# project in test_pid_sourced_symbols.py, not by increasing the product bound.
HISTORICAL_SYMBOL_IDS = {
    "tank", "vessel", "pressure_vessel", "agitated_tank", "reactor", "column", "separator",
    "heat_exchanger", "plate_heat_exchanger", "heater", "cooler", "condenser", "evaporator", "boiler",
    "pump", "positive_displacement_pump", "metering_pump", "compressor", "blower", "fan", "filter",
    "filter_press", "membrane_filter", "strainer", "cyclone", "centrifuge", "static_mixer", "manual_valve",
    "gate_valve", "ball_valve", "globe_valve", "butterfly_valve", "diaphragm_valve", "needle_valve",
    "three_way_valve", "four_way_valve", "check_valve", "pressure_regulator", "relief_valve", "rupture_disc", "generic",
}


def equipment_library_project() -> Project:
    """The 41 historical symbols; HX and multiway terminal witnesses."""
    equipment = [Equipment(
        id="doc_" + symbol["id"], name=f"DOC-{index + 1:03}", type="pid_symbol",
        symbol_kind=symbol["id"], source_kind="VendorClass_" + symbol["id"],
        rotation=(0, 90, 180, 270)[index % 4],
        position=Position(x=(index % 7) * 220.0, y=(index // 7) * 210.0),
    ) for index, symbol in enumerate(symbol for symbol in PID_SYMBOLS if symbol["id"] in HISTORICAL_SYMBOL_IDS)]
    declared = [
        ("tank", "out", "heat_exchanger", "primary_in"),
        ("heat_exchanger", "primary_out", "vessel", "in"),
        ("pressure_vessel", "out", "heat_exchanger", "secondary_in"),
        ("heat_exchanger", "secondary_out", "agitated_tank", "in"),
        ("three_way_valve", "AB", "reactor", "in"),
        ("three_way_valve", "A", "separator", "feed"),
        ("three_way_valve", "B", "boiler", "feed"),
        ("four_way_valve", "P1", "heater", "in"),
        ("four_way_valve", "P2", "cooler", "in"),
        ("four_way_valve", "P3", "pump", "in"),
        ("four_way_valve", "P4", "generic", "in"),
    ]
    connections = [Connection(id=f"declared_{index + 1}", source="doc_" + source, target="doc_" + target,
                              source_port=source_port, target_port=target_port,
                              label=f"Reviewed connection {index + 1}", directed=False)
                   for index, (source, source_port, target, target_port) in enumerate(declared)]
    source = PidDocument(title="Documentary library reviewed", source_name="reviewed-library.pid.json",
                         source_format="json", source_sha256="a" * 64,
                         equipment=[PidEquipment(
                             id=item.id, name=item.name, type=item.symbol_kind, documentary=True,
                             source_kind=item.source_kind, source_tag=item.name,
                             rotation=item.rotation, position=PidPosition(x=item.position.x, y=item.position.y),
                             provenance="Reviewed source page 1", review_required=False, confidence=1,
                         ) for item in equipment],
                         connections=[PidConnection(**item.model_dump(), inferred=False, confidence=1) for item in connections])
    return Project(id="documentary-library", name="41 documentary symbols", equipment=equipment,
                   connections=connections, pid_document=source)


@pytest.fixture
def library_project():
    return equipment_library_project()


def _cad(payload: bytes):
    return ezdxf.read(io.StringIO(payload.decode("cp1252")))


def _available(format: str):
    if format == "dwg" and not pid_cad.cad_capabilities()["available"]:
        pytest.skip("Optional real LibreDWG not installed; no DWG qualification from this run")


def test_41_documentary_objects_prepare_without_creating_tags_or_simulated_equipment(library_project):
    validation = validate_project(library_project)
    assert not validation["valid"]
    assert [issue["path"] for issue in validation["errors"]] == ["tags"]
    assert len(library_project.equipment) == 41
    assert {item.rotation for item in library_project.equipment} == {0, 90, 180, 270}
    result = prepare_pid(PidPrepareRequest(document=library_project.pid_document,
                         selected_ids=[item.id for item in library_project.equipment]))["project"]
    assert [item.type for item in result.equipment] == ["pid_symbol"] * 41
    assert [(item.symbol_kind, item.source_kind, item.rotation) for item in result.equipment] == [
        (item.symbol_kind, item.source_kind, item.rotation) for item in library_project.equipment]
    assert result.connections == library_project.connections
    assert result.tags == [] and result.scenarios == []
    assert all(item.bindings == {} for item in result.equipment)
    assert result.plc.mode == "demo" and not result.plc.approved_virtual_target
    assert result.pid_document.equipment == library_project.pid_document.equipment


@pytest.mark.parametrize("format", EXPORT_FORMATS)
def test_native_roundtrip_preserves_41_documentary_types_rotations_and_declared_ports(library_project, format):
    _available(format)
    expected = project_document(library_project)
    payload, media_type, extension = export_pid(library_project, format)
    assert payload and media_type
    if format == "dwg":
        assert payload.startswith(b"AC1015")
    restored = inspect_pid(payload, "library." + extension, ocr=False)
    assert restored.equipment == expected.equipment
    assert restored.connections == expected.connections
    assert len(restored.connections) == 11
    assert all(item.documentary for item in restored.equipment)
    generic = next(item for item in restored.equipment if item.type == "generic")
    assert generic.source_kind == "VendorClass_generic"
    prepared = prepare_pid(PidPrepareRequest(document=restored, selected_ids=[item.id for item in restored.equipment]))["project"]
    assert all(item.type == "pid_symbol" for item in prepared.equipment)
    assert [item.symbol_kind for item in prepared.equipment] == [item.symbol_kind for item in library_project.equipment]
    assert prepared.connections == library_project.connections


def test_export_has_only_declared_hx_and_multiway_connections(library_project):
    doc = project_document(library_project)
    hx = [link for link in doc.connections if "doc_heat_exchanger" in (link.source, link.target)]
    hx_ports = [(link.source_port if link.source == "doc_heat_exchanger" else link.target_port) for link in hx]
    assert sorted(hx_ports) == ["primary_in", "primary_out", "secondary_in", "secondary_out"]
    assert all(link.source != link.target for link in doc.connections)
    assert len(doc.connections) == len(library_project.connections) == 11
    for identifier, ports in [("three_way_valve", {"AB", "A", "B"}), ("four_way_valve", {"P1", "P2", "P3", "P4"})]:
        assert {link.source_port for link in doc.connections if link.source == "doc_" + identifier} == ports
    # Two external circuits must not acquire an invented internal mixing edge.
    assert not any(link.source == link.target == "doc_heat_exchanger" for link in doc.connections)


def test_svg_pdf_and_png_have_visible_symbol_drawing_beside_native_data(library_project):
    svg = ET.fromstring(export_pid(library_project, "svg")[0])
    visible_text = [element.text for element in svg.findall(".//{*}text")]
    assert {item.name for item in library_project.equipment} <= set(visible_text)
    assert {"primary_in", "primary_out", "secondary_in", "secondary_out", "AB", "A", "B"} <= set(visible_text)
    assert len(svg.findall("{*}polyline")) > 100
    pdf = PdfReader(io.BytesIO(export_pid(library_project, "pdf")[0]))
    text = pdf.pages[0].extract_text()
    assert all(item.name in text for item in library_project.equipment)
    assert "primary_in" in text and "secondary_out" in text and "AB" in text
    assert b" m" in pdf.pages[0].get_contents().get_data()
    with Image.open(io.BytesIO(export_pid(library_project, "png")[0])) as image:
        assert image.width > 1500 and image.height > 1000
        assert image.convert("RGB").getextrema() != ((255, 255),) * 3


def test_public_graph_tables_include_actual_terminal_fields(library_project):
    expected = project_document(library_project)
    graph = json.loads(export_pid(library_project, "graph-json")[0])
    for node, item in zip(graph["nodes"], expected.equipment, strict=True):
        assert node["kind"] == item.type
        assert node["attributes"]["source_kind"] == item.source_kind
        assert node["attributes"]["rotation"] == item.rotation
        assert node["attributes"]["documentary"] is True
    for edge, item in zip(graph["edges"], expected.connections, strict=True):
        assert edge["attributes"]["source_port"] == item.source_port
        assert edge["attributes"]["target_port"] == item.target_port
    root = ET.fromstring(export_pid(library_project, "graphml")[0])
    graphml = root.find("{*}graph")
    for node, item in zip(graphml.findall("{*}node"), expected.equipment, strict=True):
        values = {child.get("key"): child.text for child in node}
        assert values["type"] == item.type and values["source_kind"] == item.source_kind
        assert int(values["rotation"]) == item.rotation and values["documentary"] == "true"
    for edge, item in zip(graphml.findall("{*}edge"), expected.connections, strict=True):
        values = {child.get("key"): child.text for child in edge}
        assert (values["source_port"], values["target_port"]) == (item.source_port, item.target_port)
    with zipfile.ZipFile(io.BytesIO(export_pid(library_project, "csv")[0])) as archive:
        objects = list(csv.DictReader(io.StringIO(archive.read("equipment.csv").decode("utf-8-sig"))))
        edges = list(csv.DictReader(io.StringIO(archive.read("connections.csv").decode("utf-8-sig"))))
    for row, item in zip(objects, expected.equipment, strict=True):
        assert row["type"] == item.type and row["source_kind"] == item.source_kind
        assert int(row["rotation"]) == item.rotation and row["documentary"].lower() == "true"
    assert [(row["source_port"], row["target_port"]) for row in edges] == [
        (item.source_port, item.target_port) for item in expected.connections]


def _terminal_world(project, item_id, terminal):
    item = next(item for item in project.equipment if item.id == item_id)
    symbol = next(symbol for symbol in PID_SYMBOLS if symbol["id"] == item.symbol_kind)
    port = next(port for port in symbol["ports"] if port["id"] == terminal)
    # Independent quarter-turn rotation and documented scene translation.
    angle = math.radians(item.rotation)
    px, py = port["x"] - 50, port["y"] - 50
    x = item.position.x - min(item.position.x for item in project.equipment) + 120
    y = item.position.y - min(item.position.y for item in project.equipment) + 158
    return (x + px * math.cos(angle) - py * math.sin(angle), y + px * math.sin(angle) + py * math.cos(angle))


@pytest.mark.parametrize("format", ["dxf", "dwg"])
def test_stripped_native_cad_still_contains_visible_labels_layers_and_rotated_terminal_geometry(library_project, format):
    _available(format)
    payload = export_pid(library_project, format)[0]
    drawing = _cad(pid_cad.dwg_to_dxf(payload) if format == "dwg" else payload)
    assert "FAT_STUDIO_PID" in drawing.rootdict
    del drawing.rootdict["FAT_STUDIO_PID"]
    stream = io.StringIO()
    drawing.write(stream)
    drawing = ezdxf.read(io.StringIO(stream.getvalue()))
    assert "FAT_STUDIO_PID" not in drawing.rootdict
    entities = drawing.modelspace()
    assert {"PID_BORDER", "PID_EQUIPMENT", "PID_PIPES", "PID_TEXT", "PID_TITLEBLOCK"} <= {entity.dxf.layer for entity in entities}
    labels = {entity.dxf.text for entity in entities.query("TEXT")}
    assert {item.name for item in library_project.equipment} <= labels
    assert {"primary_in", "primary_out", "secondary_in", "secondary_out", "AB", "A", "B"} <= labels
    assert len(entities.query("CIRCLE")) >= 10 and len(entities.query("ELLIPSE")) >= 10
    assert drawing.units == 4  # Modelspace now measures the printed sheet in mm.
    sheet = engineering_scene(project_document(library_project))
    scale, offset_x, offset_y = sheet.diagram_transform
    polylines = [list(entity.get_points("xy")) for entity in entities.query("LWPOLYLINE") if len(entity) >= 2 and not entity.closed]
    for connection in library_project.connections:
        start = _terminal_world(library_project, connection.source, connection.source_port)
        end = _terminal_world(library_project, connection.target, connection.target_port)
        start = (start[0] * scale + offset_x, sheet.height_mm - (start[1] * scale + offset_y))
        end = (end[0] * scale + offset_x, sheet.height_mm - (end[1] * scale + offset_y))
        assert any(tuple(points[0]) == pytest.approx(start, abs=1e-7) and tuple(points[-1]) == pytest.approx(end, abs=1e-7)
                   for points in polylines), connection.id


def test_documentary_engine_does_not_publish_zero_values_good_quality_or_accept_faults(library_project):
    engine = ProcessEngine(library_project)
    assert not engine.validation["valid"]
    expected = {item.id: {"documentary": True, "quality": "not_simulated"} for item in library_project.equipment}
    assert engine.equipment_state == expected
    assert engine.values == engine.qualities == engine.tags == {}
    with pytest.raises(ValueError, match="invalide"):
        engine.step({}, 0.1)
    assert engine.equipment_state == expected
    assert engine.values == engine.qualities == engine.tags == {}
    for item in library_project.equipment:
        for fault in ("motor_trip", "valve_stuck", "sensor_stuck", "out_of_range"):
            with pytest.raises(ValueError, match="Complétez|indisponible"):
                engine.set_fault(item.id, fault)
    assert engine.faults == {}
    engine.reset()
    assert engine.equipment_state == expected


def test_documentary_objects_in_valid_manual_project_still_publish_no_process_value(library_project):
    library_project.tags = [Tag(id="manual_contact", name="Manual contact", direction="input",
                                data_type="BOOL", writable=True, initial_value=False)]
    engine = ProcessEngine(library_project)
    assert engine.validation["valid"]
    assert engine.step({}, 0.1) == {"manual_contact": False}
    assert engine.values == {"manual_contact": False}
    assert all(state == {"documentary": True, "quality": "not_simulated"} for state in engine.equipment_state.values())
    for fault in ("motor_trip", "valve_stuck", "sensor_stuck", "out_of_range"):
        with pytest.raises(ValueError, match="indisponible"):
            engine.set_fault("doc_heat_exchanger", fault)
    assert engine.faults == {}


def test_adding_documentary_library_preserves_existing_demo_process_signals(library_project):
    baseline = demo_project()
    combined = baseline.model_copy(deep=True)
    combined.equipment.extend(library_project.equipment)
    combined.connections.extend(library_project.connections)
    original_engine, combined_engine = ProcessEngine(baseline), ProcessEngine(combined)
    commands = DemoController(baseline).read_commands(original_engine.values, 0.1)
    assert combined_engine.validation["valid"]
    assert combined_engine.step(commands, 0.1) == original_engine.step(commands, 0.1)
    assert combined_engine.values == original_engine.values and combined_engine.qualities == original_engine.qualities
    for item in baseline.equipment:
        assert combined_engine.equipment_state[item.id] == original_engine.equipment_state[item.id]
    for item in library_project.equipment:
        assert combined_engine.equipment_state[item.id] == {"documentary": True, "quality": "not_simulated"}
