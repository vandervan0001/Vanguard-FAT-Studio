"""Explicit drawing conventions survive interchange without plant inference."""

from hashlib import sha256
import io
import json
from pathlib import Path
import zipfile

from ezdxf.colors import aci2rgb
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from fat_studio.app import create_app
from fat_studio.archive import export_archive, prepare_archive, restore_archive
from fat_studio.demo import demo_project
from fat_studio.exchange import project_package, read_project
from fat_studio.models import Connection
from fat_studio.pid_cad import cad_capabilities
from fat_studio.pid_conventions import SERVICE_DEFINITIONS, conventions_catalog, service_definition
from fat_studio.pid_exchange import PidPrepareRequest, prepare_pid
from fat_studio.pid_export import EXPORT_FORMATS, export_pid, project_document
from fat_studio.pid_import import inspect_pid
from fat_studio.pid_models import PidConnection
from fat_studio.pid_symbols import PID_SYMBOLS, resolve_symbol
from fat_studio.pid_titleblock import PidDrawingSettings
from fat_studio.storage import Store


def drawing_project():
    project = demo_project()
    project.id = "conventions-test"
    project.pid_drawing = PidDrawingSettings(layout_style="compact", color_mode="service")
    for index, connection in enumerate(project.connections):
        connection.service = SERVICE_DEFINITIONS[1 + index % 9]["id"]
    return project


@pytest.mark.parametrize("definition", SERVICE_DEFINITIONS)
def test_service_is_explicit_and_valid_in_project_and_document(definition):
    values = {"id": "L1", "source": "P1", "target": "T1", "service": definition["id"]}
    assert Connection(**values).service == PidConnection(**values).service == definition["id"]
    if definition["id"] != "unspecified":
        assert "#" + "".join(f"{channel:02X}" for channel in aci2rgb(definition["aci"])) == definition["color"]


@pytest.mark.parametrize("invalid", ["warm", "#ff0000", "cold_supply ", "ISO-red", None, 1, True])
def test_unknown_or_coerced_services_are_rejected(invalid):
    for model in (Connection, PidConnection):
        with pytest.raises(ValidationError):
            model(id="L1", source="P1", target="T1", service=invalid)


def test_legacy_connections_do_not_infer_service_from_a_label_or_name():
    for model in (Connection, PidConnection):
        assert model(id="L1", source="HOT", target="COLD", label="cold / red / 90°C").service == "unspecified"
    assert PidDrawingSettings().layout_style == "compact"
    assert PidDrawingSettings().color_mode == "service"
    for invalid in ({"layout_style": "tiny"}, {"color_mode": "ISO"}):
        with pytest.raises(ValidationError):
            PidDrawingSettings(**invalid)


@pytest.mark.parametrize("symbol", [item for item in PID_SYMBOLS if item.get("instrument_code")])
def test_explicit_instrument_function_types_resolve_without_guessing_tag_numbers(symbol):
    assert resolve_symbol(symbol["instrument_code"]) == symbol["id"]
    assert resolve_symbol(symbol["instrument_code"] + "-101") is None


def test_catalog_copies_do_not_change_the_shared_palette_or_instrument_guide():
    data = conventions_catalog()
    data["services"][1]["color"] = "#badbad"
    data["instruments"][0]["code"] = "X"
    service_definition("hot_supply")["color"] = "#badbad"
    assert service_definition("cold_supply")["color"] == "#0052A5"
    assert service_definition("unknown")["id"] == "unspecified"
    assert conventions_catalog()["instruments"][0]["code"] == "FI"


@pytest.mark.parametrize("format", EXPORT_FORMATS)
def test_service_and_print_options_roundtrip_in_all_native_formats(format):
    if format == "dwg" and not cad_capabilities()["available"]:
        pytest.skip("Real LibreDWG is not installed")
    project = drawing_project()
    before = project.model_dump_json()
    payload, _, extension = export_pid(project, format)
    restored = inspect_pid(payload, "conventions." + extension, ocr=False)
    assert [(item.id, item.service) for item in restored.connections] == [(item.id, item.service) for item in project.connections]
    assert restored.drawing == project.pid_drawing
    prepared = prepare_pid(PidPrepareRequest(document=restored, selected_ids=[item.id for item in restored.equipment]))["project"]
    assert [item.service for item in prepared.connections] == [item.service for item in project.connections]
    assert project.model_dump_json() == before


def test_raw_graph_explicit_service_is_preserved_and_invalid_service_rejected():
    graph = {"nodes": [{"id": "P1", "kind": "pump"}, {"id": "T1", "kind": "tank"}],
             "edges": [{"id": "L1", "source": "P1", "target": "T1", "attributes": {"service": "hot_return"}}]}
    doc = inspect_pid(json.dumps(graph).encode(), "external.graph.json", ocr=False)
    assert doc.connections[0].service == "hot_return"
    graph["edges"][0]["attributes"]["service"] = "inferred-red"
    with pytest.raises(ValueError):
        inspect_pid(json.dumps(graph).encode(), "external.graph.json", ocr=False)


def test_project_and_archive_preserve_service_and_layout_on_isolated_stores(tmp_path):
    project = drawing_project()
    project.pid_drawing.color_mode = "monochrome"
    assert read_project(project_package(project).model_dump(mode="json")) == project
    source, target = Store(tmp_path / "source"), Store(tmp_path / "restored")
    try:
        source.save_project(project)
        recovered = restore_archive(target, prepare_archive(export_archive(source, project)))
        assert recovered == project
        assert project_document(recovered).connections[0].service == project.connections[0].service
    finally:
        source.close()
        target.close()


def test_passive_reference_and_font_download_preserve_project_context(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        project = client.get("/api/project")
        state = client.get("/api/state").json()
        data = client.get("/api/pid/conventions")
        assert data.status_code == 200
        catalog = data.json()
        assert len(catalog["services"]) == 10
        assert {item["code"] for item in catalog["instruments"]} >= {"FT", "FIC", "TIC", "PT", "LT"}
        assert {item["id"] for item in catalog["references"]} >= {"isa-5.1", "iso-10628-2", "en-1861"}
        fonts = client.get("/api/pid/cad-fonts")
        assert fonts.status_code == 200 and fonts.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(fonts.content)) as archive:
            assert set(archive.namelist()) == {"Geist-Regular.ttf", "Geist-Bold.ttf", "OFL.txt", "README.txt"}
            for name in ("Geist-Regular.ttf", "Geist-Bold.ttf", "OFL.txt"):
                source = Path(__file__).parents[1] / "fat_studio/web/brand" / name
                assert sha256(archive.read(name)).digest() == sha256(source.read_bytes()).digest()
            assert "SIL OPEN FONT LICENSE" in archive.read("OFL.txt").decode()
        assert client.get("/api/project").content == project.content
        assert client.get("/api/project").headers["X-FAT-Project-Revision"] == project.headers["X-FAT-Project-Revision"]
        assert client.get("/api/state").json()["run_id"] == state["run_id"]
