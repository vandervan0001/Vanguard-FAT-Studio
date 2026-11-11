"""P&ID passive boundaries and persistence on isolated temporary workspaces."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Event

from fastapi.testclient import TestClient
import pytest

from fat_studio.app import create_app
from fat_studio.pid_exchange import PidPrepareRequest, prepare_pid
from fat_studio.pid_models import PidDocument, PidEquipment, PidConnection


def drawing():
    return PidDocument(title="Transfert à revoir", equipment=[
        PidEquipment(id="P101", name="P-101", type="pump", position={"x": 140, "y": 240}),
        PidEquipment(id="TK101", name="TK-101", type="tank", position={"x": 420, "y": 240}),
        PidEquipment(id="HX101", name="HX-101", type="heat_exchanger"),
    ], connections=[PidConnection(id="L1", source="P101", target="TK101")])


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as instance:
        instance.headers["X-FAT-Token"] = instance.get("/api/session").json()["token"]
        yield instance


def context(client):
    response = client.get("/api/project")
    state = client.get("/api/state").json()
    return {"X-FAT-Project-ID": response.json()["id"],
            "X-FAT-Project-Revision": response.headers["X-FAT-Project-Revision"],
            "X-FAT-Run-ID": state["run_id"] or ""}


def test_catalog_attribution_and_free_capabilities(client):
    catalogue = client.get("/api/pid/catalog").json()
    assert len(catalogue["entries"]) == 10
    assert "Scott Duncan" in catalogue["source"]["name"]
    assert catalogue["source"]["revision"] == "3f21a8540cac027489d22ebc7af757b0b5299880"
    assert "CC BY 4.0" in catalogue["source"]["license"]
    assert {item["category"] for item in catalogue["entries"]} == {"pid", "timeseries"}
    caps = client.get("/api/pid/capabilities").json()
    assert caps["local_only"] is True
    assert {item["format"] for item in caps["imports"]} >= {"pdf", "dwg", "dxf", "svg", "xml"}
    assert caps["limits"]["max_equipment"] == 50


def test_inspection_is_real_passive_and_context_guarded(client):
    before = client.get("/api/project").content
    headers = context(client)
    response = client.post("/api/pid/inspect?filename=roundtrip.json", content=drawing().model_dump_json(), headers=headers)
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["equipment"]] == ["P101", "TK101", "HX101"]
    assert client.get("/api/project").content == before
    assert context(client) == headers
    assert client.post("/api/pid/inspect?filename=a.json", content="{}", headers={"X-FAT-Token": ""}).status_code == 403
    assert client.post("/api/pid/inspect?filename=a.json", content="{}", headers={"X-FAT-Project-Revision": "stale"}).status_code == 409


def test_preparation_preserves_saved_project_and_source(client):
    old_project = client.get("/api/project").json()
    before = context(client)
    response = client.post("/api/pid/prepare", json={"document": drawing().model_dump(),
        "selected_ids": ["P101", "TK101"], "types": {}, "name": "Nouveau transfert"}, headers=before)
    assert response.status_code == 200, response.text
    prepared = response.json()["project"]
    assert prepared["id"] != old_project["id"]
    assert prepared["tags"] == [] and prepared["scenarios"] == []
    assert prepared["plc"]["mode"] == "demo"
    assert prepared["plc"]["demo_controller"] == "manual_lab_v1"
    assert prepared["plc"]["approved_virtual_target"] == ""
    assert len(prepared["pid_document"]["equipment"]) == 3
    assert len(prepared["equipment"]) == 2 and len(prepared["connections"]) == 1
    assert prepared["equipment"][0]["bindings"] == {}
    assert context(client) == before
    assert client.get("/api/project").json() == old_project
    assert client.put("/api/project", json=prepared, headers=before).status_code == 200
    assert client.get("/api/project").json()["pid_document"]["title"] == "Transfert à revoir"
    entries = client.get("/api/projects").json()
    assert {old_project["id"], prepared["id"]} <= {item["id"] for item in entries}


def test_imported_source_survives_restart(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as initial:
        initial.headers["X-FAT-Token"] = initial.get("/api/session").json()["token"]
        prepared = prepare_pid(PidPrepareRequest(document=drawing(), selected_ids=["P101", "TK101"]))
        assert initial.put("/api/project", json=prepared["project"].model_dump()).status_code == 200
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as reopened:
        assert reopened.get("/api/project").json()["pid_document"]["equipment"][2]["type"] == "heat_exchanger"
        assert reopened.get("/api/state").json()["connection"]["connected"] is False


def test_review_refuses_unknown_types_duplicates_and_invalid_links():
    for ids, types in [(["HX101"], {"HX101": "nonexistent-model"}), (["missing"], {}), (["P101", "P101"], {}), (["P101"], {"missing": "tank"})]:
        with pytest.raises(ValueError):
            prepare_pid(PidPrepareRequest(document=drawing(), selected_ids=ids, types=types))
    result = prepare_pid(PidPrepareRequest(document=drawing(), selected_ids=["HX101"], types={"HX101": "indicator"}))
    assert result["project"].equipment[0].type == "indicator"


def test_documentary_exchange_preserves_specialized_and_unclassified_objects(client):
    source = drawing()
    source.equipment[2].type = "heat_exchanger"
    source.equipment.append(PidEquipment(id="X999", name="Objet inconnu", type="vendor_special_vessel"))
    response = client.post("/api/pid/prepare", json={"document": source.model_dump(),
        "selected_ids": ["HX101", "X999"], "types": {}, "name": "Source documentaire"})
    assert response.status_code == 200, response.text
    equipment = response.json()["project"]["equipment"]
    assert [item["type"] for item in equipment] == ["pid_symbol", "pid_symbol"]
    assert [item["symbol_kind"] for item in equipment] == ["heat_exchanger", "generic"]
    assert equipment[1]["source_kind"] == "vendor_special_vessel"
    assert all(item["bindings"] == {} for item in equipment)
    definitions = client.get("/api/pid/symbols").json()["symbols"]
    exchanger = next(item for item in definitions if item["id"] == "heat_exchanger")
    valve = next(item for item in definitions if item["id"] == "three_way_valve")
    assert len(exchanger["ports"]) == 4
    assert {port["id"] for port in valve["ports"]} == {"AB", "A", "B"}


def test_preparation_preserves_full_metadata_without_overflow():
    source = drawing()
    source.metadata = {f"field_{index}": "source" for index in range(40)}
    result = prepare_pid(PidPrepareRequest(document=source, selected_ids=["P101"]))
    restored = PidDocument.model_validate_json(result["project"].pid_document.model_dump_json())
    assert len(restored.metadata) == 40
    assert restored.metadata == source.metadata


def test_stop_remains_available_while_passive_parser_runs(client, monkeypatch):
    entered, release = Event(), Event()

    async def delayed(*args):
        entered.set()
        await asyncio.to_thread(release.wait, 5)
        return drawing()

    monkeypatch.setattr("fat_studio.pid_api.inspect_isolated", delayed)
    assert client.post("/api/run/start", json={}).status_code == 200
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            parsing = pool.submit(client.post, "/api/pid/inspect?filename=test.svg", content="<svg/>")
            assert entered.wait(3)
            stopping = pool.submit(client.post, "/api/run/stop", json={})
            assert stopping.result(timeout=2).status_code == 200
            release.set()
            assert parsing.result(timeout=3).status_code == 200
    finally:
        release.set()
    assert client.get("/api/state").json()["status"] == "stopped"


def test_disconnected_inspection_cancels_passive_work(client, monkeypatch):
    from starlette.requests import Request
    cancelled = Event()

    async def parser(*args):
        try:
            await asyncio.sleep(30)
        finally:
            cancelled.set()

    async def disconnected(*args):
        await asyncio.sleep(.02)
        return True

    monkeypatch.setattr("fat_studio.pid_api.inspect_isolated", parser)
    monkeypatch.setattr(Request, "is_disconnected", disconnected)
    response = client.post("/api/pid/inspect?filename=test.svg", content="<svg/>")
    assert response.status_code == 499
    assert cancelled.is_set()
    assert client.get("/api/state").json()["status"] == "idle"


@pytest.mark.parametrize("kind", ["svg", "pdf", "png", "dxf", "json", "graph", "graphml", "csv", "drawio"])
def test_snapshot_exports_and_stale_rejection(client, kind):
    headers = context(client)
    response = client.get("/api/pid/export/" + kind, headers=headers)
    assert response.status_code == 200, response.text[:100]
    assert len(response.content) > 50
    assert response.headers["X-FAT-Project-Revision"] == headers["X-FAT-Project-Revision"]
    assert "attachment" in response.headers["Content-Disposition"]
    if kind == "json":
        assert json.loads(response.content)["format"] == "fat-studio/pid"
    assert client.get("/api/pid/export/" + kind, headers={**headers, "X-FAT-Project-Revision": "stale"}).status_code == 409


def test_unsupported_or_hostile_documents_do_not_touch_state(client):
    before = client.get("/api/project").content
    for filename, content in [("test.exe", b"MZ"), ("test.pdf", b"%PDF-corrupt"),
                              ("test.svg", b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///secret">]><svg>&x;</svg>')]:
        response = client.post("/api/pid/inspect?filename=" + filename, content=content)
        assert response.status_code == 400, response.text
        assert client.get("/api/project").content == before
    assert client.get("/api/state").json()["status"] == "idle"
    assert client.get("/api/pid/export/exe").status_code == 400
