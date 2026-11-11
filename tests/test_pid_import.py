"""Real small files exercise the local P&ID interchange boundaries."""

import base64
import io
import json
import zipfile

import ezdxf
import pytest
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from fat_studio.pid_import import MAX_DOCUMENT, MAX_UPLOAD, inspect_pid
from fat_studio.pid_models import PidDocument, PidEquipment, PidPosition


def _native():
    return PidDocument(title="Feuille revue", equipment=[
        PidEquipment(id="P-101", name="Pompe", type="pump", position=PidPosition(x=70, y=50)),
        PidEquipment(id="TK-102", name="Cuve", type="tank", position=PidPosition(x=300, y=50)),
    ])


def _pdf(count=1, image=None):
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(400, 200))
    for _ in range(count):
        if image:
            canvas.drawImage(ImageReader(image), 0, 0, width=400, height=200)
        else:
            canvas.drawString(40, 100, "P-101")
            canvas.drawString(300, 100, "TK-102")
            canvas.line(45, 95, 305, 95)
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def _image(format="PNG"):
    image = Image.new("RGB", (1200, 400), "white")
    draw = ImageDraw.Draw(image)
    # Pillow ships a scalable default font; no OS font or download is needed.
    font = ImageFont.load_default(size=70)
    draw.text((80, 130), "P-101", fill="black", font=font)
    draw.text((650, 130), "TK-102", fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return buffer.getvalue()


def test_pdf_real_vector_tags_positions_and_geometric_candidate():
    doc = inspect_pid(_pdf(), "drawing.pdf", ocr=False)
    assert [item.source_tag for item in doc.equipment] == ["P-101", "TK-102"]
    assert [item.type for item in doc.equipment] == ["pump", "tank"]
    assert 40 < doc.equipment[0].position.x < 60
    assert len(doc.connections) == 1
    assert doc.connections[0].inferred and not doc.connections[0].directed
    assert all(item.review_required for item in doc.equipment)
    assert doc.pages[0].image_data_url.startswith("data:image/png;base64,")
    assert len(doc.source_sha256) == 64


def test_pdf_page_selection_is_explicit_and_bounded():
    source = _pdf(count=3)
    default = inspect_pid(source, "drawing.pdf", ocr=False)
    assert len(default.pages) == 1
    assert any("3 pages" in warning for warning in default.warnings)
    chosen = inspect_pid(source, "drawing.pdf", pages="2-3", ocr=False)
    assert [page.number for page in chosen.pages] == [2, 3]
    assert {item.page for item in chosen.equipment} == {2, 3}
    for selection in ("0", "4", "3-1", "all", "1,", "1-21"):
        with pytest.raises(ValueError, match="[Pp]age|[Ss]élection"):
            inspect_pid(source, "drawing.pdf", pages=selection, ocr=False)


def test_pdf_rejects_encrypted_and_broken_files():
    writer = PdfWriter()
    writer.append(io.BytesIO(_pdf()))
    writer.encrypt("private")
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(ValueError, match="chiffré"):
        inspect_pid(buffer.getvalue(), "encrypted.pdf")
    with pytest.raises(ValueError, match="PDF"):
        inspect_pid(b"%PDF-broken", "broken.pdf")


def test_pdf_reads_native_attachment_without_guessing_types():
    writer = PdfWriter()
    writer.append(io.BytesIO(_pdf()))
    writer.add_attachment("fat-studio-pid.json", _native().model_dump_json().encode())
    buffer = io.BytesIO()
    writer.write(buffer)
    doc = inspect_pid(buffer.getvalue(), "native.pdf")
    assert doc.title == "Feuille revue"
    assert doc.equipment[0].name == "Pompe"
    assert doc.source_format == "pdf"


def test_pdf_rotated_page_positions_match_the_rendered_preview():
    writer = PdfWriter()
    writer.append(io.BytesIO(_pdf()))
    writer.pages[0].rotate(90)
    buffer = io.BytesIO()
    writer.write(buffer)
    doc = inspect_pid(buffer.getvalue(), "rotated.pdf", ocr=False)
    assert doc.pages[0].width == 200 and doc.pages[0].height == 400
    assert 90 < doc.equipment[0].position.x < 110
    assert 40 < doc.equipment[0].position.y < 60
    assert len(doc.connections) == 1


@pytest.mark.parametrize("overflow", ["objects", "path", "segments"])
def test_pdf_incomplete_geometry_keeps_preview_and_text_but_no_partial_links(monkeypatch, overflow):
    from fat_studio import pid_import

    # Lower the same production bound to cover each stop condition cheaply.
    monkeypatch.setattr(pid_import, "MAX_SEGMENTS", 7)
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(400, 200))
    canvas.drawString(40, 100, "P-101")
    canvas.drawString(300, 100, "TK-102")
    canvas.line(45, 95, 305, 95)  # A prefix alone would yield a plausible link.
    if overflow == "objects":
        for i in range(8):
            canvas.drawString(10, 10 + i * 5, "Note")
    elif overflow == "path":
        path = canvas.beginPath()
        path.moveTo(10, 10)
        for i in range(8):
            path.lineTo(20 + i, 10)
        canvas.drawPath(path)
    else:
        for start in (10, 40):
            path = canvas.beginPath()
            path.moveTo(start, 10)
            for i in range(4):
                path.lineTo(start + i + 1, 10)
            canvas.drawPath(path)
    canvas.showPage()
    canvas.drawString(40, 100, "P-201")
    canvas.drawString(300, 100, "TK-202")
    canvas.line(45, 95, 305, 95)
    canvas.save()
    doc = inspect_pid(buffer.getvalue(), "dense.pdf", pages="1-2", ocr=False)
    assert {item.source_tag for item in doc.equipment} == {"P-101", "TK-102", "P-201", "TK-202"}
    assert len(doc.connections) == 1
    assert (doc.connections[0].source, doc.connections[0].target) == ("P-201", "TK-202")
    assert len(doc.pages) == 2 and all(page.image_data_url and "P-" in page.text for page in doc.pages)
    assert any("Page 1" in warning and "toutes les liaisons" in warning for warning in doc.warnings)


def test_pdf_real_segment_limit_degrades_to_manual_review():
    from fat_studio.pid_import import MAX_SEGMENTS

    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(400, 200))
    canvas.drawString(40, 100, "P-101")
    path = canvas.beginPath()
    path.moveTo(10, 10)
    for i in range(MAX_SEGMENTS + 1):
        path.lineTo(10 + i % 100, 10 + i % 40)
    canvas.drawPath(path)
    canvas.save()
    doc = inspect_pid(buffer.getvalue(), "dense-real-limit.pdf", ocr=False)
    assert [item.source_tag for item in doc.equipment] == ["P-101"]
    assert not doc.connections and doc.pages[0].image_data_url and "P-101" in doc.pages[0].text
    assert any("limite de géométrie" in warning for warning in doc.warnings)


def _pdf_with_documentary_references():
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(400, 400))
    canvas.setFont("Helvetica", 7)
    canvas.drawString(15, 180, "FILENAME: P-200 P&IDS.DWG")
    canvas.drawString(15, 160, "P-200 P&IDS.DWG")
    canvas.drawString(310, 50, "DRAWING NUMBER")
    canvas.drawString(310, 32, "P-207")
    canvas.drawString(15, 140, "EPA requirements for permit P-499 apply to all regulated discharge systems.")
    canvas.drawString(15, 120, "REF SHT P-208")
    canvas.drawString(15, 100, "REFSHT P209")
    canvas.drawString(15, 80, "RE SHL P210")  # Common OCR fragmentation of a sheet-reference label.
    canvas.save()
    return buffer.getvalue()


def test_pdf_context_discards_file_cartouche_and_regulatory_references_only():
    # Synthetic text/positions derived from reviewed failure modes; no source PDF copied.
    writer = PdfWriter()
    writer.append(io.BytesIO(_pdf_with_documentary_references()))
    overlay = io.BytesIO()
    canvas = Canvas(overlay, pagesize=(400, 400))
    canvas.drawString(310, 100, "P-101")  # An actual tag near the same border survives.
    canvas.drawString(15, 240, "P-499")  # Same identifier is allowed outside the paragraph.
    canvas.save()
    writer.pages[0].merge_page(PdfReader(overlay).pages[0])
    buffer = io.BytesIO()
    writer.write(buffer)
    doc = inspect_pid(buffer.getvalue(), "references.pdf", ocr=False)
    assert {item.source_tag for item in doc.equipment} == {"P-101", "P-499"}
    assert "P-207" in doc.pages[0].text and "P-200" in doc.pages[0].text
    assert any("cartouche" in warning for warning in doc.warnings)


def test_pdf_ocr_fallback_uses_accepted_tags_and_preserves_vector_text(monkeypatch):
    from fat_studio import pid_ocr

    calls = []

    def recognize(image):
        calls.append(image.size)
        return [("P-101", 80, 100, .9), ("TK-102", 300, 100, .9),
                ("FILENAME: P-200 P&IDS.DWG", 150, 300, .9)]

    monkeypatch.setattr(pid_ocr, "recognize", recognize)
    doc = inspect_pid(_pdf_with_documentary_references(), "references.pdf")
    assert calls and {item.source_tag for item in doc.equipment} == {"P-101", "TK-102"}
    assert "P-207" in doc.pages[0].text and "[OCR local]" in doc.pages[0].text
    assert all("OCR local CPU" in item.provenance for item in doc.equipment)
    assert not doc.connections


def test_raster_ambiguous_at_prefix_requires_legend_instead_of_sensor_guess(monkeypatch):
    from fat_studio import pid_ocr

    monkeypatch.setattr(pid_ocr, "recognize", lambda image: [
        ("AT5510", 100, 100, .93), ("AT-5520 ALUM TANK", 500, 100, .92),
        ("AIT-5511", 700, 100, .93),
    ])
    doc = inspect_pid(_image(), "alum.png")
    assert [item.type for item in doc.equipment] == ["unknown", "unknown", "analog_sensor"]
    assert all(item.review_required for item in doc.equipment)
    assert all("légende requise" in item.provenance for item in doc.equipment[:2])
    assert any("Préfixe AT ambigu" in warning for warning in doc.warnings)


def test_explicit_graph_at_types_remain_authoritative():
    source = {"nodes": [{"id": "AT-5510", "kind": "tank"},
                         {"id": "AT-5520", "type": "Instrument", "role": "transmitter"}], "edges": []}
    doc = inspect_pid(json.dumps(source).encode(), "typed.json")
    assert [item.type for item in doc.equipment] == ["tank", "analog_sensor"]


def test_graph_preserves_explicit_documentary_ports_rotation_and_original_kind():
    source = {"nodes": [
        {"id": "HX-1", "attributes": {"kind": "plate_heat_exchanger", "source_kind": "SupplierHX", "rotation": 90, "documentary": True}},
        {"id": "V-1", "attrs": {"kind": "three_way_valve", "rotation": 270}},
        {"id": "CUSTOM-1", "properties": {"kind": "VendorUnknownAssembly"}},
    ], "edges": [{"source": "HX-1", "target": "V-1", "properties": {"source_port": "hot_out", "target_port": "common"}}]}
    doc = inspect_pid(json.dumps(source).encode(), "documentary.json")
    assert [item.type for item in doc.equipment] == ["plate_heat_exchanger", "three_way_valve", "VendorUnknownAssembly"]
    assert doc.equipment[0].source_kind == "SupplierHX"
    assert doc.equipment[0].documentary and not doc.equipment[1].documentary
    assert [item.rotation for item in doc.equipment] == [90, 270, 0]
    assert (doc.connections[0].source_port, doc.connections[0].target_port) == ("hot_out", "common")
    assert doc.equipment[2].source_kind == "VendorUnknownAssembly"


@pytest.mark.parametrize("rotation", [True, "90", 90.0, 45, -90])
def test_graph_rejects_ambiguous_or_unsupported_rotation(rotation):
    source = {"nodes": [{"id": "HX-1", "rotation": rotation}], "edges": []}
    with pytest.raises(ValueError, match="Rotation documentaire"):
        inspect_pid(json.dumps(source).encode(), "bad-rotation.json")


@pytest.mark.parametrize("value", [None, True, 42, {"id": "hot_out"}, "x" * 81])
def test_graph_does_not_coerce_documentary_ports_or_original_kind(value):
    source = {"nodes": [{"id": "hx"}, {"id": "v"}],
              "edges": [{"source": "hx", "target": "v", "source_port": value}]}
    with pytest.raises(ValueError, match="source_port documentaire"):
        inspect_pid(json.dumps(source).encode(), "bad-port.json")
    source = {"nodes": [{"id": "hx", "source_kind": value}], "edges": []}
    with pytest.raises(ValueError, match="source_kind documentaire"):
        inspect_pid(json.dumps(source).encode(), "bad-kind.json")


def test_csv_and_graphml_preserve_explicit_documentary_orientation_and_ports():
    doc = inspect_pid(b"tag,type,rotation,source_kind,documentary\nHX-1,heat_exchanger,180,VendorExchanger,true\n", "symbols.csv")
    assert doc.equipment[0].rotation == 180 and doc.equipment[0].source_kind == "VendorExchanger"
    assert doc.equipment[0].documentary
    graph = b'''<graphml>
      <key id="kind" for="node" attr.name="kind"/><key id="rot" for="node" attr.name="rotation"/>
      <key id="src" for="node" attr.name="source_kind"/>
      <key id="sp" for="edge" attr.name="source_port"/><key id="tp" for="edge" attr.name="target_port"/>
      <graph edgedefault="undirected"><node id="HX-1"><data key="kind">heat_exchanger</data>
      <data key="rot">90</data><data key="src">VendorHX</data></node><node id="V-1"/>
      <edge source="HX-1" target="V-1"><data key="sp">cold_out</data><data key="tp">branch_a</data></edge></graph>
      </graphml>'''
    doc = inspect_pid(graph, "symbols.graphml")
    assert doc.equipment[0].rotation == 90 and doc.equipment[0].source_kind == "VendorHX"
    assert (doc.connections[0].source_port, doc.connections[0].target_port) == ("cold_out", "branch_a")


def test_xml_preserves_only_canonical_explicit_port_and_rotation_attributes():
    xml = b'''<PlantModel><Equipment ID="hx" ComponentClass="PlateHeatExchanger" rotation="270" source_kind="VendorHX"/>
      <Equipment ID="v" ComponentClass="ThreeWayValve"/>
      <Connection FromID="hx" ToID="v" FromNode="2" ToNode="1" source_port="hot_out" target_port="common"/>
      <Connection FromID="hx" ToID="v" FromNode="3" ToNode="2"/></PlantModel>'''
    doc = inspect_pid(xml, "symbols.xml")
    assert doc.equipment[0].type == "plate_heat_exchanger" and doc.equipment[0].source_kind == "VendorHX"
    assert [item.rotation for item in doc.equipment] == [270, 0]
    assert (doc.connections[0].source_port, doc.connections[0].target_port) == ("hot_out", "common")
    assert not doc.connections[1].source_port and not doc.connections[1].target_port


@pytest.mark.parametrize("source_kind,canonical", [
    ("pressure_vessel", "pressure_vessel"), ("PressureVessel", "pressure_vessel"),
    ("vessel", "vessel"), ("agitated_tank", "agitated_tank"),
    ("pressure_regulator", "pressure_regulator"), ("PlateHeatExchanger", "plate_heat_exchanger"),
    ("ThreeWayValve", "three_way_valve"), ("CheckValve", "check_valve"),
    ("positive_displacement_pump", "positive_displacement_pump"), ("metering_pump", "metering_pump"),
])
def test_graph_and_prepare_preserve_specialized_documentary_identity(source_kind, canonical):
    from fat_studio.pid_exchange import PidPrepareRequest, prepare_pid

    source = {"nodes": [{"id": "UNIT-1", "kind": source_kind}], "edges": []}
    doc = inspect_pid(json.dumps(source).encode(), "specialized.json")
    assert doc.equipment[0].type == canonical and doc.equipment[0].source_kind == source_kind
    project = prepare_pid(PidPrepareRequest(document=doc, selected_ids=["UNIT-1"]))["project"]
    item = project.equipment[0]
    assert item.type == "pid_symbol" and item.symbol_kind == canonical and item.source_kind == source_kind
    assert not item.bindings and not item.params and not project.tags and not project.scenarios


def test_hand_valve_prefix_and_unknown_assembly_are_not_plc_actuators_or_indicators():
    from fat_studio.pid_exchange import PidPrepareRequest, prepare_pid

    doc = inspect_pid(b'<svg width="400" height="200"><text x="50" y="50">HV-101</text></svg>', "hand-valve.svg")
    assert doc.equipment[0].type == "manual_valve"
    project = prepare_pid(PidPrepareRequest(document=doc, selected_ids=["HV-101"]))["project"]
    assert project.equipment[0].type == "pid_symbol" and project.equipment[0].symbol_kind == "manual_valve"
    assert not project.equipment[0].bindings
    doc = inspect_pid(b'{"nodes":[{"id":"X-1","kind":"VendorUnknownAssembly"}],"edges":[]}', "custom.json")
    project = prepare_pid(PidPrepareRequest(document=doc, selected_ids=["X-1"]))["project"]
    assert project.equipment[0].type == "pid_symbol" and project.equipment[0].symbol_kind == "generic"
    assert project.equipment[0].source_kind == "VendorUnknownAssembly"


def test_real_local_cpu_ocr_scan_and_scanned_pdf():
    scan = _image()
    doc = inspect_pid(scan, "scan.png")
    assert {item.source_tag for item in doc.equipment} == {"P-101", "TK-102"}
    assert not doc.connections  # Recognition of text does not establish piping.
    assert all(item.review_required for item in doc.equipment)
    image = Image.open(io.BytesIO(scan))
    pdf = inspect_pid(_pdf(image=image), "scanned.pdf")
    assert {item.source_tag for item in pdf.equipment} == {"P-101", "TK-102"}
    assert not pdf.connections


@pytest.mark.parametrize("format,extension", [("PNG", "png"), ("JPEG", "jpg"), ("BMP", "bmp"), ("WEBP", "webp"), ("TIFF", "tiff")])
def test_real_rasters_can_be_backgrounds_without_ocr(format, extension):
    doc = inspect_pid(_image(format), f"image.{extension}", ocr=False)
    assert not doc.equipment
    assert len(doc.pages) == 1 and doc.pages[0].width == 1200
    assert any("OCR désactivé" in warning for warning in doc.warnings)


def test_multipage_tiff_requires_selection():
    first = Image.new("RGB", (100, 90), "white")
    second = Image.new("RGB", (140, 120), "white")
    buffer = io.BytesIO()
    first.save(buffer, format="TIFF", save_all=True, append_images=[second])
    doc = inspect_pid(buffer.getvalue(), "multi.tiff", pages="2", ocr=False)
    assert doc.pages[0].number == 2 and doc.pages[0].width == 140


def test_png_native_metadata_is_bounded_and_round_trips():
    image = Image.new("RGB", (10, 10), "white")
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("fat-studio-pid", _native().model_dump_json(), zip=True)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", pnginfo=metadata)
    doc = inspect_pid(buffer.getvalue(), "native.png")
    assert doc.title == "Feuille revue" and doc.equipment[0].name == "Pompe"
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("fat-studio-pid", "x" * (MAX_DOCUMENT + 1), zip=True)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", pnginfo=metadata)
    with pytest.raises(ValueError, match="Métadonnées PNG"):
        inspect_pid(buffer.getvalue(), "bomb.png")


def test_svg_geometry_and_transforms_preserve_unknown_tags():
    source = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">
      <g transform="translate(10 20)"><text x="40" y="80">P-101</text>
      <text x="300" y="80">ZZ-901</text><path d="M 40 80 H 300"/></g></svg>'''
    doc = inspect_pid(source, "drawing.svg")
    assert doc.equipment[0].position == PidPosition(x=50, y=100)
    assert doc.equipment[1].type == "unknown"
    assert len(doc.connections) == 1
    assert doc.pages[0].image_data_url


def test_svg_adjacent_text_without_a_stroke_is_not_topology():
    doc = inspect_pid(b'<svg width="400" height="200"><text x="30" y="40">P-101</text><text x="300" y="40">TK-102</text></svg>', "no-pipe.svg")
    assert len(doc.equipment) == 2 and not doc.connections


@pytest.mark.parametrize("extension", ["xml", "svg", "graphml"])
def test_xml_external_entities_and_dtd_are_rejected(extension):
    source = b'<!DOCTYPE root [<!ENTITY secret SYSTEM "file:///C:/Windows/win.ini">]><root>&secret;</root>'
    with pytest.raises(ValueError, match="DTD/entités externes"):
        inspect_pid(source, f"unsafe.{extension}")


def test_xml_depth_and_svg_unsupported_external_images_are_safe():
    source = ("<svg>" + "<g>" * 45 + "</g>" * 45 + "</svg>").encode()
    with pytest.raises(ValueError, match="complexe"):
        inspect_pid(source, "deep.svg")
    doc = inspect_pid(b'<svg width="200" height="100"><script>fetch("https://invalid")</script><image href="https://invalid/secret.svg"/></svg>', "external.svg")
    assert not doc.equipment
    assert any("non exécutés" in warning for warning in doc.warnings)
    assert "https://invalid" not in doc.model_dump_json()


def test_dxf_real_lines_attributes_and_unknown_blocks():
    drawing = ezdxf.new()
    model = drawing.modelspace()
    model.add_text("P-101").dxf.insert = (10, 10, 0)
    model.add_text("TK-102").dxf.insert = (100, 10, 0)
    model.add_line((10, 10), (100, 10))
    block = drawing.blocks.new("CUSTOM_SYMBOL")
    block.add_circle((0, 0), 3)
    model.add_blockref("CUSTOM_SYMBOL", (160, 50))
    buffer = io.StringIO()
    drawing.write(buffer)
    doc = inspect_pid(buffer.getvalue().encode(), "drawing.dxf")
    assert {item.source_tag for item in doc.equipment} >= {"P-101", "TK-102"}
    assert any(item.name == "CUSTOM_SYMBOL" and item.type == "unknown" for item in doc.equipment)
    assert len(doc.connections) == 1 and doc.connections[0].inferred
    assert doc.pages[0].image_data_url


def test_dxf_embedded_native_xrecord():
    drawing = ezdxf.new()
    record = drawing.objects.add_xrecord()
    record.extend([(1, _native().model_dump_json())])
    drawing.rootdict["FAT_STUDIO_PID"] = record
    buffer = io.StringIO()
    drawing.write(buffer)
    doc = inspect_pid(buffer.getvalue().encode(), "native.dxf")
    assert doc.title == "Feuille revue" and doc.source_format == "dxf"


def test_dxf_binary_and_windows_crlf_legacy_codepage():
    drawing = ezdxf.new("R2000")
    drawing.modelspace().add_text("P-101 Pompe été").dxf.insert = (10, 10, 0)
    buffer = io.StringIO()
    drawing.write(buffer)
    data = buffer.getvalue().replace("\n", "\r\n").encode("cp1252")
    doc = inspect_pid(data, "windows.dxf")
    assert "Pompe été" in doc.pages[0].text and doc.equipment[0].source_tag == "P-101"
    binary = io.BytesIO()
    drawing.write(binary, fmt="bin")
    doc = inspect_pid(binary.getvalue(), "binary.dxf")
    assert doc.equipment[0].source_tag == "P-101"


def test_scott_graph_attributes_relations_and_pipe_contraction():
    source = {"nodes": [
        {"id": "P-101", "type": "Equipment", "attrs": {"kind": "centrifugal_pump", "position": {"x": 15, "y": 30}}},
        {"id": "P01.L1.1", "type": "PipeSegment", "confidence": .7},
        {"id": "V-101", "type": "Component", "attrs": {"kind": "control_valve"}},
        {"id": "P01.L1.2", "type": "PipeSegment"},
        {"id": "TK-102", "type": "Equipment", "attrs": {"kind": "tank"}},
        {"id": "PT-101", "type": "Instrument", "attrs": {"role": "transmitter"}},
        {"id": "LOOP:P-101", "type": "ControlLoop"},
    ], "edges": [
        {"source": "P-101", "target": "P01.L1.1", "type": "FLOWS_TO", "confidence": .9},
        {"source": "P01.L1.1", "target": "V-101", "type": "FLOWS_TO", "confidence": .8},
        {"source": "V-101", "target": "P01.L1.2", "type": "FLOWS_TO"},
        {"source": "P01.L1.2", "target": "TK-102", "type": "FLOWS_TO"},
        {"source": "PT-101", "target": "P01.L1.1", "type": "MEASURES"},
        {"source": "PT-101", "target": "V-101", "type": "SIGNAL_TO", "derived": True},
    ]}
    doc = inspect_pid(json.dumps(source).encode(), "graph.json")
    assert len(doc.equipment) == 7 and len(doc.connections) == 8
    assert doc.equipment[0].type == "pump" and doc.equipment[0].position.x == 15
    assert doc.equipment[2].type == "valve_control"
    assert doc.equipment[5].type == "analog_sensor"
    proposed = [edge for edge in doc.connections if edge.label.startswith("FLOWS_TO via")]
    assert {(edge.source, edge.target) for edge in proposed} == {("P-101", "V-101"), ("V-101", "TK-102")}
    assert all(edge.inferred and edge.directed for edge in proposed)
    assert not any(edge.source == "P-101" and edge.target == "TK-102" for edge in proposed)
    assert not any(edge.source == "PT-101" for edge in proposed)


def test_graph_rejects_duplicate_missing_references_and_nonfinite_position():
    cases = [
        {"nodes": [{"id": "P-1"}, {"id": "P-1"}], "edges": []},
        {"nodes": [{"id": "P-1"}], "edges": [{"source": "P-1", "target": "nope"}]},
        {"nodes": [{"id": "P-1", "x": float("inf")}], "edges": []},
    ]
    for source in cases:
        with pytest.raises(ValueError):
            inspect_pid(json.dumps(source).encode(), "graph.json")


@pytest.mark.parametrize("field", ["directed", "derived", "inferred"])
def test_graph_json_rejects_string_booleans_instead_of_changing_meaning(field):
    source = {"nodes": [{"id": "a"}, {"id": "b"}], "edges": [{"source": "a", "target": "b", field: "false"}]}
    with pytest.raises(ValueError, match="booléen"):
        inspect_pid(json.dumps(source).encode(), "graph.json")


@pytest.mark.parametrize("attributes", [{"review_required": "false"}, {"documentary": "false"}, {"documentary": 1}, {"x": True}, {"position": {"x": "30", "y": 40}}, {"page": 1.5}, {"confidence": 1.5}])
def test_graph_json_rejects_ambiguous_scalars(attributes):
    source = {"nodes": [{"id": "a", "attributes": attributes}], "edges": []}
    with pytest.raises(ValueError):
        inspect_pid(json.dumps(source).encode(), "graph.json")


def test_graph_json_rejects_object_references():
    source = {"nodes": [{"id": "a"}], "edges": [{"source": {"id": "a"}, "target": "a"}]}
    with pytest.raises(ValueError, match="référence"):
        inspect_pid(json.dumps(source).encode(), "graph.json")


def test_graphml_explicit_types_positions_and_direction():
    source = b'''<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
      <key id="k1" for="node" attr.name="type" attr.type="string"/>
      <key id="kx" for="node" attr.name="x" attr.type="double"/>
      <graph edgedefault="undirected"><node id="P-101"><data key="k1">pump</data><data key="kx">50</data></node>
      <node id="TK-102"><data key="k1">tank</data></node><edge source="P-101" target="TK-102"/></graph></graphml>'''
    doc = inspect_pid(source, "graph.graphml")
    assert doc.equipment[0].type == "pump" and doc.equipment[0].position.x == 50
    assert not doc.connections[0].directed and not doc.connections[0].inferred


def test_dexpi_subset_preserves_items_and_explicit_connections():
    source = b'''<PlantModel><Equipment ID="e1" TagName="P-101" ComponentClass="CentrifugalPump">
      <Position><Location X="100" Y="20"/></Position><Nozzle ID="n1" TagName="N1"/></Equipment>
      <Equipment ID="e2" TagName="TK-102" ComponentClass="Tank"/>
      <PipingNetworkSegment ID="line1"><Connection FromID="n1"/><Connection ToID="e2"/></PipingNetworkSegment>
      <ShapeCatalogue><Equipment ID="template" ComponentClass="Tank"/></ShapeCatalogue></PlantModel>'''
    doc = inspect_pid(source, "drawing.xml")
    assert {item.id for item in doc.equipment} == {"e1", "n1", "e2", "line1"}
    assert doc.equipment[0].position == PidPosition(x=100, y=-20)
    assert {(edge.source, edge.target) for edge in doc.connections} == {("n1", "line1"), ("line1", "e2")}
    assert all(not edge.inferred and not edge.directed for edge in doc.connections)
    assert "dexpi_subset" in doc.metadata


def test_csv_native_and_payload_limits():
    doc = inspect_pid("tag;type;name;x;y\nP-101;pump;Pompe;20;40\nZZ-4;custom;Autre;200;40\n".encode(), "equipment.csv")
    assert len(doc.equipment) == 2 and doc.equipment[0].name == "Pompe"
    assert doc.equipment[1].type == "custom" and not doc.connections
    single = inspect_pid(b"tag\nP-101\nTK-102\n", "tags.csv")
    assert len(single.equipment) == 2 and not single.connections
    for data, name in [(b"", "empty.pdf"), (b"x" * (MAX_UPLOAD + 1), "large.png"), (b"text", "file.exe")]:
        with pytest.raises(ValueError):
            inspect_pid(data, name)
    native = _native().model_dump()
    native["equipment"].append(native["equipment"][0])
    with pytest.raises(ValueError, match="invalide"):
        inspect_pid(json.dumps(native).encode(), "native.json")


def test_native_rejects_remote_and_fake_previews():
    for preview in ("https://invalid/a.png", "data:image/svg+xml;base64,AAAA", "data:image/png;base64,bm90IGFuIGltYWdl"):
        native = _native().model_dump()
        native["pages"] = [{"number": 1, "image_data_url": preview}]
        with pytest.raises(ValueError):
            inspect_pid(json.dumps(native).encode(), "native.json")


def test_native_archive_only_reads_named_file_and_rejects_bomb():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("fat-studio-pid.json", _native().model_dump_json())
        archive.writestr("../../never-extracted.txt", "ignored")
    doc = inspect_pid(buffer.getvalue(), "native.zip")
    assert doc.title == "Feuille revue"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("fat-studio-pid.json", "x" * (MAX_DOCUMENT + 1))
    with pytest.raises(ValueError, match="4 Mio"):
        inspect_pid(buffer.getvalue(), "bomb.zip")


def test_native_export_graphml_and_drawio_embeddings():
    import html
    payload = html.escape(_native().model_dump_json())
    graph = f'<graphml><graph><data key="pid_document">{payload}</data></graph></graphml>'.encode()
    doc = inspect_pid(graph, "native.graphml")
    assert doc.title == "Feuille revue"
    drawio = f'<mxfile><diagram><object id="fat-studio-pid" pid="{html.escape(_native().model_dump_json(), quote=True)}"/></diagram></mxfile>'.encode()
    assert inspect_pid(drawio, "native.drawio").equipment[0].name == "Pompe"


def test_exported_graph_preserves_ids_labels_flags_and_page():
    from fat_studio.pid_export import _graph
    from fat_studio.pid_models import PidConnection
    source = _native()
    source.equipment[0].review_required = False
    source.equipment[0].provenance = "Source locale revue"
    source.equipment[0].page = 3
    source.connections.append(PidConnection(id="feed_pump_tank", source="P-101", target="TK-102",
                                             label="Alimentation", directed=True, inferred=False, confidence=.9))
    result = inspect_pid(json.dumps(_graph(source)).encode(), "graph.json")
    assert result.equipment == source.equipment
    assert result.connections == source.connections


def test_dwg_uses_only_configured_local_converter(monkeypatch):
    from fat_studio import pid_cad
    drawing = ezdxf.new()
    drawing.modelspace().add_text("P-101")
    buffer = io.StringIO()
    drawing.write(buffer)
    called = []
    monkeypatch.setattr(pid_cad, "dwg_to_dxf", lambda data: called.append(data) or buffer.getvalue().encode())
    doc = inspect_pid(b"AC1032synthetic", "drawing.dwg")
    assert called == [b"AC1032synthetic"] and doc.source_format == "dwg"
    assert doc.equipment[0].source_tag == "P-101"


def test_preview_bytes_are_png_not_svg_or_original_external_resources():
    doc = inspect_pid(b'<svg width="100" height="100"><text x="30" y="30">P-1</text></svg>', "drawing.svg")
    preview = base64.b64decode(doc.pages[0].image_data_url.split(",", 1)[1])
    with Image.open(io.BytesIO(preview)) as image:
        image.verify()
    # Independent reader confirms our synthetic PDF has a genuine text layer.
    assert "P-101" in PdfReader(io.BytesIO(_pdf())).pages[0].extract_text()


def test_malformed_svg_coordinates_have_a_clear_error():
    for source in (b'<svg width="bad" height="200"/>', b'<svg><text x="NaN">P-1</text></svg>'):
        with pytest.raises(ValueError, match="SVG invalide"):
            inspect_pid(source, "bad.svg")
