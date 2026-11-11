"""Sourced symbol geometry and functional codes remain inert and attributable."""

from hashlib import sha256
import io
from pathlib import Path
from xml.etree import ElementTree as ET

import ezdxf
from pypdf import PdfReader
import pytest

from fat_studio import pid_cad
from fat_studio.models import Connection, Equipment, Position, Project
from fat_studio.pid_exchange import PidPrepareRequest, prepare_pid
from fat_studio.pid_export import EXPORT_FORMATS, engineering_scene, export_pid, project_document
from fat_studio.pid_import import inspect_pid
from fat_studio.pid_ports import port_point
from fat_studio.pid_symbols import PID_SYMBOLS, PID_SYMBOLS_BY_ID, resolve_symbol


ROOT = Path(__file__).parents[1]
COMMIT = "8a68f2569a9a977079ece242aa7771b9d53448a8"
SOURCED = {"pump_general", "valve_general", "heat_exchanger_general", "compressor_general"}
INSTRUMENTS = {
    "flow_transmitter": "FT", "pressure_transmitter": "PT", "level_transmitter": "LT", "temperature_transmitter": "TT",
    "flow_indicator": "FI", "pressure_indicator": "PI", "level_indicator": "LI", "temperature_indicator": "TI",
    "flow_indicating_controller": "FIC", "pressure_indicating_controller": "PIC",
    "level_indicating_controller": "LIC", "temperature_indicating_controller": "TIC",
    "level_alarm_high": "LAH", "level_alarm_low": "LAL", "pressure_switch_high": "PSH", "pressure_switch_low": "PSL",
}


def test_source_geometry_is_attributed_to_exact_revision_with_license_retained():
    assert {symbol["id"] for symbol in PID_SYMBOLS if symbol.get("source")} == SOURCED
    for identifier in SOURCED:
        symbol = PID_SYMBOLS_BY_ID[identifier]
        source = symbol["source"]
        assert source["commit"] == COMMIT and source["license"] == "MIT"
        assert source["url"].startswith(f"https://github.com/nukleon84/pyflowsheet/blob/{COMMIT}/")
        assert len(source["source_sha256"]) == 64 and source["changes"]
        assert "conformité non certifiée" in symbol["references"][0]
    license_bytes = (ROOT / "fat_studio/pid_symbols_pyflowsheet_LICENSE.txt").read_bytes()
    assert sha256(license_bytes).hexdigest() == "7531c6bcc185c118554ead3d46f8a487387b2ef9c5e80a98edee554515651d59"
    assert b"Copyright (c) 2020 Jochen Steimel" in license_bytes


def test_adapted_pump_and_valve_keep_the_source_outline_and_terminal_topology():
    pump = PID_SYMBOLS_BY_ID["pump_general"]
    circle = next(shape for shape in pump["shapes"] if shape["kind"] == "circle")
    assert (circle["x"], circle["y"], circle["radius"]) == (50, 50, 25)
    lines = [shape["points"] for shape in pump["shapes"] if shape["kind"] == "polyline"]
    # Source pump diagonals touch the top/bottom of the circle and meet at the
    # right-hand tangent; this distinguishes it from a triangle in a circle.
    assert [[50, 25], [75, 50]] in lines and [[50, 75], [75, 50]] in lines
    valve = PID_SYMBOLS_BY_ID["valve_general"]
    outline = next(shape["points"] for shape in valve["shapes"] if shape["kind"] == "polygon")
    assert outline == [[25, 35], [75, 65], [75, 35], [25, 65]]
    for identifier in ("pump_general", "valve_general", "compressor_general"):
        assert port_point(identifier, "in", 0) == (0, 50)
        assert port_point(identifier, "out", 0) == (100, 50)


def test_sourced_radial_exchanger_does_not_rewrite_existing_lateral_exchanger_ports():
    expected = {"primary_in": (0, 50), "primary_out": (100, 50), "secondary_in": (50, 0), "secondary_out": (50, 100)}
    for terminal, point in expected.items():
        assert port_point("heat_exchanger_general", terminal, 0) == point
    assert port_point("heat_exchanger", "primary_in", 0) == (0, 35)
    assert port_point("heat_exchanger", "secondary_out", 0) == (100, 75)
    serpentine = [shape for shape in PID_SYMBOLS_BY_ID["heat_exchanger_general"]["shapes"]
                  if shape["kind"] == "polyline" and len(shape["points"]) == 6][0]
    assert serpentine["points"][2] == pytest.approx([41.6666666667, 37.5])
    assert serpentine["points"][3] == pytest.approx([58.3333333333, 62.5])


@pytest.mark.parametrize("identifier,code", INSTRUMENTS.items())
def test_instrument_functions_have_explicit_labels_and_one_documentary_tap(identifier, code):
    symbol = PID_SYMBOLS_BY_ID[identifier]
    assert symbol["instrument_code"] == symbol["prefix"] == code
    assert f"({code})" in symbol["label"]
    assert symbol["simulation"] is False
    assert symbol["ports"] == [{"id": "tap", "label": "Prise de mesure ou raccord documentaire", "x": 50, "y": 100, "direction": "bidirectional"}]
    assert port_point(identifier, "tap", 90) == (0, 50)
    assert port_point(identifier, "tap", 270) == (100, 50)
    assert resolve_symbol(identifier) == identifier
    assert resolve_symbol(code + "-101") is None
    assert not {"bindings", "params", "faults", "state", "plc", "command"} & symbol.keys()


def test_instrument_and_sourced_entries_do_not_share_mutable_primitives():
    assert {symbol["id"] for symbol in PID_SYMBOLS if symbol.get("instrument_code")} == set(INSTRUMENTS)
    a, b = PID_SYMBOLS_BY_ID["flow_transmitter"], PID_SYMBOLS_BY_ID["pressure_transmitter"]
    assert a["shapes"] == b["shapes"] and a["shapes"] is not b["shapes"]
    assert a["shapes"][0] is not b["shapes"][0]
    assert a["ports"][0] is not b["ports"][0]


@pytest.fixture
def sourced_project():
    # Distinct project to preserve max50 bound, covering all20 additions with
    # every declared terminal rather than dropping overflow from a fixture.
    equipment = [Equipment(id="doc_" + identifier, name="DOC-" + str(index + 1), type="pid_symbol",
                           symbol_kind=identifier, source_kind="Declared_" + identifier,
                           position=Position(x=(index % 5) * 220.0, y=(index // 5) * 210.0),
                           rotation=(0, 90, 180, 270)[index % 4])
                 for index, identifier in enumerate(sorted(SOURCED) + list(INSTRUMENTS))]
    equipment.append(Equipment(id="endpoint", name="Endpoint", type="pid_symbol", symbol_kind="generic",
                               position=Position(x=1300.0, y=420.0)))
    connections = [Connection(id=f"wire_{index}_{port['id']}", source=item.id, target="endpoint",
                              source_port=port["id"], target_port="in", directed=False)
                   for index, item in enumerate(equipment[:-1])
                   for port in PID_SYMBOLS_BY_ID[item.symbol_kind]["ports"]]
    project = Project(id="sourced-symbols", name="Sourced symbols and functions", equipment=equipment, connections=connections)
    project.pid_drawing.paper_size = "A1"
    return project


@pytest.mark.parametrize("format", EXPORT_FORMATS)
def test_all_new_families_and_all_terminals_survive_native_exchange_without_renaming(sourced_project, format):
    if format == "dwg" and not pid_cad.cad_capabilities()["available"]:
        pytest.skip("Optional real LibreDWG not installed")
    expected = project_document(sourced_project)
    payload, _, extension = export_pid(sourced_project, format)
    restored = inspect_pid(payload, "symbols." + extension, ocr=False)
    assert restored.equipment == expected.equipment
    assert restored.connections == expected.connections
    assert len(restored.equipment) == 21 and len(restored.connections) == 26
    prepared = prepare_pid(PidPrepareRequest(document=restored, selected_ids=[item.id for item in restored.equipment]))["project"]
    assert [item.symbol_kind for item in prepared.equipment] == [item.symbol_kind for item in sourced_project.equipment]
    assert prepared.connections == sourced_project.connections
    assert prepared.tags == prepared.scenarios == []
    assert all(item.bindings == {} for item in prepared.equipment)


@pytest.mark.parametrize("format", ["dxf", "dwg"])
def test_actual_cad_entities_keep_instrument_codes_and_every_rotated_terminal(sourced_project, format):
    if format == "dwg" and not pid_cad.cad_capabilities()["available"]:
        pytest.skip("Optional real LibreDWG not installed")
    payload = export_pid(sourced_project, format)[0]
    drawing = ezdxf.read(io.StringIO((pid_cad.dwg_to_dxf(payload) if format == "dwg" else payload).decode("cp1252")))
    del drawing.rootdict["FAT_STUDIO_PID"]
    labels = {entity.dxf.text for entity in drawing.modelspace().query("TEXT")}
    assert set(INSTRUMENTS.values()) <= labels
    sheet = engineering_scene(project_document(sourced_project))
    scale, dx, dy = sheet.diagram_transform
    routes = [list(entity.get_points("xy")) for entity in drawing.modelspace().query("LWPOLYLINE")
              if not entity.closed and entity.dxf.layer == "PID_PIPES"]
    for connection in sourced_project.connections:
        source = next(item for item in sourced_project.equipment if item.id == connection.source)
        px, py = port_point(source.symbol_kind, connection.source_port, source.rotation)
        # Documented legacy-scene translation, independently of its output.
        center_x = source.position.x - min(item.position.x for item in sourced_project.equipment) + 120
        center_y = source.position.y - min(item.position.y for item in sourced_project.equipment) + 158
        expected = ((center_x + px - 50) * scale + dx,
                    sheet.height_mm - ((center_y + py - 50) * scale + dy))
        assert any(tuple(route[0]) == pytest.approx(expected, abs=1e-7) for route in routes), connection.id


def test_instrument_function_codes_are_visible_in_svg_and_pdf_not_only_native_data(sourced_project):
    svg = ET.fromstring(export_pid(sourced_project, "svg")[0])
    assert set(INSTRUMENTS.values()) <= {element.text for element in svg.findall(".//{*}text")}
    page = PdfReader(io.BytesIO(export_pid(sourced_project, "pdf")[0])).pages[0]
    words = set(page.extract_text().split())
    assert set(INSTRUMENTS.values()) <= words
