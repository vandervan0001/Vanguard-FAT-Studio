"""Physical model choices are explicit; P&ID files restore drawing data only.

External fixtures do not use export_pid or embedded FAT metadata. Separate
geometry checks remove native payloads before reading the visible drawing.
"""

import io
import json
import math
from urllib.parse import unquote
from xml.etree import ElementTree as ET

import ezdxf
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream
import pytest

from fat_studio.archive import export_archive, prepare_archive, restore_archive
from fat_studio.catalog import CATALOG_BY_TYPE
from fat_studio.exchange import project_package, read_project
from fat_studio.models import Connection, Equipment, Position, Project, Tag
from fat_studio.pid_cad import cad_capabilities, dwg_to_dxf
from fat_studio.pid_exchange import PidPrepareRequest, prepare_pid
from fat_studio.pid_export import EXPORT_FORMATS, engineering_scene, export_pid, project_document
from fat_studio.pid_import import inspect_pid
from fat_studio.pid_models import PidDocument, PidEquipment
from fat_studio.pid_ports import port_point, process_ports
from fat_studio.storage import Store


def _external(format):
    if format == "json":
        return json.dumps({"nodes": [
            {"id": "HX", "kind": "HeatExchanger", "rotation": 90},
            {"id": "V3", "kind": "ValveThreeWay", "rotation": 270},
        ], "edges": [
            {"source": "HX", "target": "V3", "source_port": "primary_out", "target_port": "AB"},
            {"source": "HX", "target": "V3", "source_port": "secondary_out", "target_port": "A"},
        ]}).encode()
    if format == "graphml":
        return b'''<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
        <key id="kind" for="node" attr.name="kind"/><key id="rot" for="node" attr.name="rotation"/>
        <key id="sp" for="edge" attr.name="source_port"/><key id="tp" for="edge" attr.name="target_port"/>
        <graph edgedefault="undirected"><node id="HX"><data key="kind">HeatExchanger</data><data key="rot">90</data></node>
        <node id="V3"><data key="kind">ThreeWayValve</data><data key="rot">270</data></node>
        <edge source="HX" target="V3"><data key="sp">primary_out</data><data key="tp">AB</data></edge>
        <edge source="HX" target="V3"><data key="sp">secondary_out</data><data key="tp">A</data></edge>
        </graph></graphml>'''
    if format == "csv":
        return b"id,type,rotation\nHX,heat_exchanger,90\nV3,valve_three_way,270\n"
    return b'''<PlantModel><Equipment ID="HX" ComponentClass="HeatExchanger" rotation="90"/>
        <PipingComponent ID="V3" ComponentClass="ThreeWayValve" rotation="270"/>
        <Connection FromID="HX" ToID="V3" source_port="primary_out" target_port="AB"/>
        <Connection FromID="HX" ToID="V3" source_port="secondary_out" target_port="A"/></PlantModel>'''


@pytest.mark.parametrize("format", ["json", "graphml", "csv", "xml"])
def test_independent_external_files_default_to_documentary_until_model_chosen(format):
    document = inspect_pid(_external(format), "independent." + format, ocr=False)
    assert [item.type for item in document.equipment] == ["heat_exchanger", "three_way_valve"]
    assert [item.rotation for item in document.equipment] == [90, 270]
    original = document.model_dump_json()
    default = prepare_pid(PidPrepareRequest(document=document, selected_ids=["HX", "V3"]))["project"]
    assert [(item.type, item.symbol_kind) for item in default.equipment] == [
        ("pid_symbol", "heat_exchanger"), ("pid_symbol", "three_way_valve")]
    assert all(not item.params and not item.bindings for item in default.equipment)
    assert default.tags == default.scenarios == []
    if format != "csv":
        assert [(edge.source_port, edge.target_port) for edge in default.connections] == [
            ("primary_out", "AB"), ("secondary_out", "A")]
    explicit = prepare_pid(PidPrepareRequest(document=document, selected_ids=["HX", "V3"],
        types={"HX": "heat_exchanger", "V3": "valve_three_way"}))
    assert [item.type for item in explicit["project"].equipment] == ["heat_exchanger", "valve_three_way"]
    assert [item.rotation for item in explicit["project"].equipment] == [90, 270]
    assert all(not item.params and not item.bindings for item in explicit["project"].equipment)
    assert explicit["project"].tags == explicit["project"].scenarios == []
    assert any("choisi explicitement" in warning for warning in explicit["warnings"])
    assert document.model_dump_json() == original


@pytest.mark.parametrize("type,canonical", [("heat_exchanger", "heat_exchanger"),
    ("valve_three_way", "three_way_valve"), ("three_way_valve", "three_way_valve"),
    ("PlateHeatExchanger", "plate_heat_exchanger")])
@pytest.mark.parametrize("documentary", [False, True])
def test_native_drawing_type_or_flag_cannot_implicitly_choose_new_physics(type, canonical, documentary):
    source = PidDocument(equipment=[PidEquipment(id="source", name="Source", type=type,
                         documentary=documentary, rotation=180, source_kind="OriginalVendorClass")])
    project = prepare_pid(PidPrepareRequest(document=source, selected_ids=["source"]))["project"]
    item = project.equipment[0]
    assert (item.type, item.symbol_kind, item.source_kind, item.rotation) == (
        "pid_symbol", canonical, "OriginalVendorClass", 180)
    assert not item.params and not item.bindings and not project.tags


def test_documentary_alias_is_not_a_silent_simulation_choice():
    source = PidDocument(equipment=[PidEquipment(id="v", name="Valve", type="three_way_valve")])
    project = prepare_pid(PidPrepareRequest(document=source, selected_ids=["v"], types={"v": "three_way_valve"}))["project"]
    assert project.equipment[0].type == "pid_symbol"
    assert project.equipment[0].symbol_kind == "three_way_valve"


@pytest.mark.parametrize("type", ["tank", "pump", "pump_vfd", "valve_onoff", "valve_control",
                                   "analog_sensor", "digital_sensor", "digital_input", "indicator"])
def test_existing_nine_default_import_choices_are_unchanged(type):
    source = PidDocument(equipment=[PidEquipment(id="old", name="Legacy", type=type)])
    project = prepare_pid(PidPrepareRequest(document=source, selected_ids=["old"]))["project"]
    assert project.equipment[0].type == type and project.equipment[0].symbol_kind == ""


@pytest.fixture
def physical_project():
    tanks = [Equipment(id=identifier, name=identifier, type="tank", position=Position(x=x, y=300),
                        params={"capacity_l": 1500, "initial_level_pct": 60})
             for identifier, x in (("COMMON", 0), ("A", 400), ("B", 800))]
    valve = Equipment(id="V3", name="V3-101", type="valve_three_way", rotation=270,
        position=Position(x=200, y=100), source_kind="VendorThreeWayValve",
        params={"mode": "diverting", "common_tank_id": "COMMON", "branch_a_tank_id": "A",
                "branch_b_tank_id": "B", "max_flow_l_s": 27.5, "response_s": .2, "initial_position_pct": 41},
        bindings={"command": "V3_CMD", "position": "V3_POS", "flow_a": "V3_FA", "flow_b": "V3_FB"})
    hx = Equipment(id="HX", name="HX-201", type="heat_exchanger", rotation=90,
        position=Position(x=600, y=100), source_kind="PlateHeatExchanger",
        params={"ua_kw_k": 7.5, "primary_volume_l": 25, "secondary_volume_l": 31,
                "primary_inlet_temperature_c": 91, "secondary_inlet_temperature_c": 17,
                "primary_flow_equipment": "V3", "primary_flow_field": "flow_a_l_s"},
        bindings={"primary_temperature": "HX_TP", "secondary_temperature": "HX_TS", "heat": "HX_Q"})
    unknown = Equipment(id="CUSTOM", name="Custom-999", type="pid_symbol", symbol_kind="generic",
                        source_kind="VendorUnknownAssembly", position=Position(x=1000, y=100))
    tags = [Tag(id=identifier, name=identifier, data_type="REAL", direction=direction,
                writable=direction == "input", min=-10000, max=10000, initial_value=0.0)
            for identifier, direction in [("V3_CMD", "output"), ("V3_POS", "input"),
                ("V3_FA", "input"), ("V3_FB", "input"), ("HX_TP", "input"), ("HX_TS", "input"), ("HX_Q", "input")]]
    edges = [("COMMON", "out", "V3", "AB"), ("V3", "A", "HX", "primary_in"),
             ("HX", "primary_out", "A", "in"), ("B", "out", "HX", "secondary_in"),
             ("HX", "secondary_out", "COMMON", "in"), ("V3", "B", "B", "in")]
    return Project(id="physical-exchange", name="Two explicitly configured FAT models",
        equipment=[*tanks, valve, hx, unknown], tags=tags,
        connections=[Connection(id=f"branch_{i}", source=source, target=target,
            source_port=sp, target_port=tp, directed=True) for i, (source, sp, target, tp) in enumerate(edges)])


def test_physical_terminal_vocabulary_is_distinct_from_plc_signal_ports(physical_project):
    for identifier, expected in [("HX", {"primary_in", "primary_out", "secondary_in", "secondary_out"}),
                                  ("V3", {"AB", "A", "B"})]:
        item = next(item for item in physical_project.equipment if item.id == identifier)
        assert {port["id"] for port in process_ports(item)} == expected
        assert expected.isdisjoint(CATALOG_BY_TYPE[item.type]["ports"])
    assert port_point("valve_three_way", "AB", 90) == (50, 0)


def test_physical_drawing_omits_configuration_and_declares_documentary_restoration(physical_project):
    document = project_document(physical_project)
    items = {item.id: item for item in document.equipment}
    assert items["HX"].type == "heat_exchanger" and items["HX"].documentary
    assert items["V3"].type == "three_way_valve" and items["V3"].documentary
    assert items["HX"].source_kind == "PlateHeatExchanger"
    assert items["V3"].source_kind == "VendorThreeWayValve"
    payload = document.model_dump_json()
    assert all(key not in payload for key in ('"params"', '"bindings"', '"tags"', '"plc"', 'V3_CMD', 'ua_kw_k'))
    assert any("réimport documentaire" in warning for warning in document.warnings)
    assert document.connections[1].source_port == "A" and document.connections[1].target_port == "primary_in"


def _requires_dwg(format):
    if format == "dwg" and not cad_capabilities()["available"]:
        pytest.skip("Optional local LibreDWG unavailable; DWG not qualified by this run")


@pytest.mark.parametrize("format", EXPORT_FORMATS)
def test_ten_formats_restore_new_model_drawings_as_documentary_not_physics(physical_project, format):
    _requires_dwg(format)
    expected = project_document(physical_project)
    payload, media_type, extension = export_pid(physical_project, format)
    assert payload and media_type
    restored = inspect_pid(payload, "drawing." + extension, ocr=False)
    assert restored.equipment == expected.equipment and restored.connections == expected.connections
    project = prepare_pid(PidPrepareRequest(document=restored, selected_ids=["HX", "V3", "CUSTOM"]))["project"]
    assert [(item.type, item.symbol_kind) for item in project.equipment] == [
        ("pid_symbol", "three_way_valve"), ("pid_symbol", "heat_exchanger"), ("pid_symbol", "generic")]
    assert all(not item.params and not item.bindings for item in project.equipment)
    assert project.tags == project.scenarios == []


def test_complete_project_json_and_archive_restore_physics_and_bindings(physical_project, tmp_path):
    restored_json = read_project(json.loads(project_package(physical_project).model_dump_json()))
    assert restored_json == physical_project
    source, target = Store(tmp_path / "source"), Store(tmp_path / "target")
    try:
        source.save_project(physical_project)
        plan = prepare_archive(export_archive(source, physical_project))
        restored_archive = restore_archive(target, plan)
        assert restored_archive == physical_project
        for restored in (restored_json, restored_archive):
            valve = next(item for item in restored.equipment if item.id == "V3")
            hx = next(item for item in restored.equipment if item.id == "HX")
            assert valve.type == "valve_three_way" and valve.params["branch_a_tank_id"] == "A"
            assert valve.bindings["command"] == "V3_CMD"
            assert hx.type == "heat_exchanger" and hx.params["ua_kw_k"] == 7.5
            assert hx.params["primary_flow_equipment"] == "V3"
            assert hx.bindings["primary_temperature"] == "HX_TP"
            assert restored.connections == physical_project.connections
    finally:
        source.close()
        target.close()


_TERMINALS = {"HX": {"primary_in": (0, 35), "primary_out": (100, 35),
                      "secondary_in": (0, 75), "secondary_out": (100, 75)},
              "V3": {"AB": (0, 50), "A": (100, 50), "B": (50, 100)},
              "COMMON": {"in": (0, 50), "out": (100, 50)},
              "A": {"in": (0, 50)}, "B": {"in": (0, 50), "out": (100, 50)}}


def _expected_terminal(project, identifier, terminal):
    item = next(item for item in project.equipment if item.id == identifier)
    px, py = _TERMINALS[identifier][terminal]
    angle = math.radians(item.rotation)
    local = (50 + (px - 50) * math.cos(angle) - (py - 50) * math.sin(angle),
             50 + (px - 50) * math.sin(angle) + (py - 50) * math.cos(angle))
    return (item.position.x - min(e.position.x for e in project.equipment) + 70 + local[0],
            item.position.y - min(e.position.y for e in project.equipment) + 108 + local[1])


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("format", ["svg", "pdf", "dxf", "dwg"])
def test_visible_vectors_without_native_data_have_rotated_physical_terminal_connections(physical_project, rotation, format):
    _requires_dwg(format)
    for item in physical_project.equipment:
        if item.id in ("HX", "V3"):
            item.rotation = rotation
    payload = export_pid(physical_project, format)[0]
    height = max(430, max(e.position.y for e in physical_project.equipment) - min(e.position.y for e in physical_project.equipment) + 310)
    sheet = engineering_scene(project_document(physical_project)) if format != "svg" else None
    if sheet:
        height = sheet.height_mm
    if format == "svg":
        root = ET.fromstring(payload)
        root.remove(root.find("{*}metadata"))
        root = ET.fromstring(ET.tostring(root))
        assert root.find("{*}metadata") is None
        lines = [[tuple(map(float, point.split(","))) for point in element.get("points").split()]
                 for element in root.findall("{*}polyline")]
    elif format == "pdf":
        writer = PdfWriter()
        writer.add_page(PdfReader(io.BytesIO(payload)).pages[0])
        stream = io.BytesIO()
        writer.write(stream)
        reader = PdfReader(io.BytesIO(stream.getvalue()))
        assert not reader.attachments
        text = reader.pages[0].extract_text()
        assert all(label in text for label in ("HX-201", "V3-101", "primary_in", "secondary_out", "AB"))
        lines, current = [], []
        for values, operation in ContentStream(reader.pages[0].get_contents(), reader).operations:
            if operation == b"m":
                current = [tuple(map(float, values))]
            elif operation == b"l":
                current.append(tuple(map(float, values)))
            elif operation in (b"S", b"s"):
                if current:
                    lines.append(current)
                current = []
    else:
        drawing = ezdxf.read(io.StringIO((dwg_to_dxf(payload) if format == "dwg" else payload).decode("cp1252")))
        del drawing.rootdict["FAT_STUDIO_PID"]
        stream = io.StringIO()
        drawing.write(stream)
        drawing = ezdxf.read(io.StringIO(stream.getvalue()))
        assert "FAT_STUDIO_PID" not in drawing.rootdict
        labels = {entity.dxf.text for entity in drawing.modelspace().query("TEXT")}
        assert {"HX-201", "V3-101", "primary_in", "secondary_out", "AB"} <= labels
        lines = [[(x, height - y) for x, y in entity.get_points("xy")]
                 for entity in drawing.modelspace().query("LWPOLYLINE") if not entity.closed]
    for edge in physical_project.connections:
        expected_start = _expected_terminal(physical_project, edge.source, edge.source_port)
        expected_end = _expected_terminal(physical_project, edge.target, edge.target_port)
        if sheet:
            scale, dx, dy = sheet.diagram_transform
            expected_start = (expected_start[0] * scale + dx, expected_start[1] * scale + dy)
            expected_end = (expected_end[0] * scale + dx, expected_end[1] * scale + dy)
        assert any(len(points) >= 4 and points[0] == pytest.approx(expected_start, abs=1e-4)
                   and points[-1] == pytest.approx(expected_end, abs=1e-4) for points in lines), edge.id


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_drawio_visible_connectors_anchor_to_rotated_ports_without_native_object(physical_project, rotation):
    for item in physical_project.equipment:
        if item.id in ("HX", "V3"):
            item.rotation = rotation
    root = ET.fromstring(export_pid(physical_project, "drawio")[0])
    cells = root.find(".//root")
    cells.remove(cells.find("object"))
    assert root.find(".//object") is None
    for edge in physical_project.connections:
        cell = next(cell for cell in cells.findall("mxCell") if cell.get("id") == "edge-" + edge.id)
        style = dict(part.split("=", 1) for part in cell.get("style").split(";") if "=" in part)
        for prefix, identifier, terminal in (("exit", edge.source, edge.source_port), ("entry", edge.target, edge.target_port)):
            expected = _expected_terminal(physical_project, identifier, terminal)
            item = next(item for item in physical_project.equipment if item.id == identifier)
            # The node image is 100x130, with its 100x100 body below a 23px label band.
            local_x = expected[0] - (item.position.x - min(e.position.x for e in physical_project.equipment) + 70)
            local_y = expected[1] - (item.position.y - min(e.position.y for e in physical_project.equipment) + 108)
            assert float(style[prefix + "X"]) == pytest.approx(local_x / 100)
            assert float(style[prefix + "Y"]) == pytest.approx((23 + local_y) / 130)
            assert style[prefix + "Perimeter"] == "0"
            # Cross-check the terminal against the actual independent image
            # viewport/glyph, not only the connector's stored scalar fields.
            node = next(node for node in cells.findall("mxCell") if node.get("id") == "node-" + identifier)
            encoded_image = node.get("style").split("image=data:image/svg+xml,", 1)[1].split(";", 1)[0]
            image = ET.fromstring(unquote(encoded_image))
            vx, vy, vw, vh = map(float, image.get("viewBox").split())
            point = (vx + float(style[prefix + "X"]) * vw, vy + float(style[prefix + "Y"]) * vh)
            glyph_ends = [tuple(map(float, text.split(","))) for shape in image.findall("{*}polyline")
                          for text in (shape.get("points").split()[0], shape.get("points").split()[-1])]
            assert any(endpoint == pytest.approx(point, abs=1e-7) for endpoint in glyph_ends)


def test_png_remains_a_visible_drawing_after_native_text_is_removed(physical_project):
    payload = export_pid(physical_project, "png")[0]
    with Image.open(io.BytesIO(payload)) as source:
        image = source.convert("RGB")
    plain = io.BytesIO()
    image.save(plain, format="PNG")
    with Image.open(io.BytesIO(plain.getvalue())) as restored:
        assert "fat-studio-pid" not in restored.info
        assert restored.width > 1500 and restored.height > 1000
        pixels = list(restored.convert("RGB").get_flattened_data())
        assert sum(max(pixel) < 180 for pixel in pixels) > 1000
        assert all(max(pixel) - min(pixel) <= 2 for pixel in pixels)  # Engineering plot is monochrome.


def test_unknown_drawing_ports_are_preserved_without_a_fabricated_anchor(physical_project):
    physical_project.connections[0].target_port = "VendorUnknownPort"
    doc = project_document(physical_project)
    assert doc.connections[0].target_port == "VendorUnknownPort"
    assert port_point("valve_three_way", "VendorUnknownPort", 90) is None
    root = ET.fromstring(export_pid(physical_project, "drawio")[0])
    edge = next(cell for cell in root.findall(".//mxCell") if cell.get("id") == "edge-branch_0")
    assert "entryX=" not in edge.get("style") and "exitX=" in edge.get("style")


@pytest.mark.parametrize("name,repeat_tag", [("TV-101 · Répartition vers A", False),
                                           ("Répartition vers A", True)])
def test_export_does_not_repeat_a_source_tag_already_visible_in_the_heading(name, repeat_tag):
    project = Project(id="label-layout", name="Valve label", equipment=[Equipment(
        id="valve", name=name, type="pid_symbol", symbol_kind="three_way_valve")],
        pid_document=PidDocument(equipment=[PidEquipment(id="valve", name="Source", source_tag="TV-101")]))
    original = project.model_dump_json()
    svg = ET.fromstring(export_pid(project, "svg")[0])
    labels = [element.text for element in svg.findall("{*}text")]
    assert name in labels
    assert labels.count("TV-101") == int(repeat_tag)
    # Source identity is retained even when its redundant visible label is omitted.
    document = PidDocument.model_validate_json(svg.find("{*}metadata").text)
    assert document.equipment[0].source_tag == "TV-101"
    assert project.model_dump_json() == original
