import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from fat_studio.app import create_app
from fat_studio.mapping import export_mapping, import_mapping
from fat_studio.demo import demo_project


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        token = client.get("/api/session").json()["token"]
        client.headers["X-FAT-Token"] = token
        yield client


def test_demo_api_roundtrip_and_trace_exports(client):
    project = client.get("/api/project").json()
    assert len(project["equipment"]) == 8
    assert client.get("/api/validate").json()["valid"]
    assert client.post("/api/run/start", json={}).status_code == 200
    assert client.put("/api/project", json=project).status_code == 409
    assert client.post("/api/force", json={"tag_id": "pump_cmd", "value": True}).status_code == 400
    assert client.post("/api/markers", json={"message": "FAT boundary"}).status_code == 200
    assert client.post("/api/run/pause").json()["status"] == "paused"
    assert client.post("/api/result", json={"verdict": "pass", "comment": "Operator reviewed"}).status_code == 200
    assert client.post("/api/run/stop").json()["status"] == "stopped"
    for kind in ("csv", "report", "json"):
        response = client.get("/api/export/" + kind)
        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]
    report = client.get("/api/export/report").text
    assert "FAT boundary" in report and "Operator reviewed" in report
    evidence = client.get("/api/export/json").json()
    assert evidence["result"]["verdict"] == "pass"
    assert evidence["project"]["id"] == project["id"]
    assert client.get("/api/runs").json()[0]["verdict"] == "pass"


def test_csrf_origin_and_host_are_rejected(client):
    assert client.post("/api/run/start", json={}, headers={"X-FAT-Token": ""}).status_code == 403
    assert client.post("/api/run/start", json={}, headers={"Origin": "https://evil.invalid"}).status_code == 403
    assert client.get("/api/session", headers={"Host": "evil.invalid"}).status_code == 403
    assert client.get("/api/session", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.get("/api/session", headers={"Origin": "http://127.0.0.1"}).status_code == 200


def test_cross_tab_target_guard(client):
    response = client.post("/api/run/start", json={}, headers={"X-FAT-Project-ID": "another-project"})
    assert response.status_code == 409
    assert client.get("/api/state").json()["status"] == "idle"


def test_invalid_mapping_persists_but_cannot_run(client):
    project = client.get("/api/project").json()
    project["equipment"][1]["bindings"] = {}
    assert client.put("/api/project", json=project).status_code == 200
    assert not client.get("/api/validate").json()["valid"]
    assert client.post("/api/run/start", json={}).status_code == 400


def test_create_save_reload_and_recover_backups(client):
    project = client.post("/api/projects", json={"name": "Mon banc"}).json()
    assert project["equipment"] == []
    project["name"] = "Mon banc révisé"
    assert client.put("/api/project", json=project).status_code == 200
    assert client.post("/api/demo/load").status_code == 200
    assert client.post(f"/api/projects/{project['id']}/load").json()["name"] == "Mon banc révisé"
    assert any(item["id"] == project["id"] for item in client.get("/api/projects").json())


def test_invalid_payload_is_clear_and_body_limit_enforced(client):
    project = client.get("/api/project").json()
    project["tags"][0]["initial_value"] = "false"
    response = client.put("/api/project", json=project)
    assert response.status_code == 422
    assert response.json()["detail"]
    response = client.post("/api/mapping", content="x" * (5 * 1024 * 1024 + 1), headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_project_cannot_self_authorize_plc_connection(client):
    project = client.get("/api/project").json()
    project["plc"].update(mode="opcua", expected_application_uri="urn:test", approved_virtual_target="test")
    assert client.put("/api/project", json=project).status_code == 200
    result = client.get("/api/validate").json()
    assert not result["valid"]
    assert any("politique" in item["message"] for item in result["errors"])
    assert client.post("/api/run/start", json={"target_confirmation": "test @ opc.tcp://127.0.0.1:4840"}).status_code == 400
    assert client.get("/api/state").json()["write_count"] == 0


def test_csv_mapping_roundtrip_and_rejection(client):
    original = demo_project()
    assert import_mapping(original, export_mapping(original)) == original
    exported = client.get("/api/mapping").text
    assert client.post("/api/mapping", json={"csv": exported}).status_code == 200
    assert client.post("/api/mapping", json={"csv": "id,name\nx,x"}).status_code == 400
    # Explicit booleans are not interpreted with Python truthiness.
    assert client.post("/api/mapping", json={"csv": exported.replace("false", "False")}).status_code == 400


def test_persisted_project_is_loaded_on_restart(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as first:
        first.headers["X-FAT-Token"] = first.get("/api/session").json()["token"]
        original = first.get("/api/project").json()
        original["name"] = "Persisted project"
        first.put("/api/project", json=original)
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as second:
        assert second.get("/api/project").json()["name"] == "Persisted project"
        assert second.get("/api/state").json()["status"] == "idle"


def test_corrupt_project_preserved_and_recovery_is_visible(tmp_path):
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects/broken.json").write_text("broken", encoding="utf-8")
    (tmp_path / "last-project.json").write_text(json.dumps({"id": "broken"}), encoding="utf-8")
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        assert "illisible" in client.get("/api/state").json()["error"]
    assert (tmp_path / "projects/broken.json").read_text() == "broken"


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_validation_payload_returns_422_without_echoing_input(client, value):
    project = client.get("/api/project").json()
    payload = json.dumps(project).replace('"speed": 1.0', '"speed": ' + value)
    response = client.put("/api/project", content=payload, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert any("speed" in error["loc"] for error in response.json()["detail"])
    assert all("input" not in error for error in response.json()["detail"])


def test_non_ascii_session_token_is_denied_without_server_error(client):
    response = client.post("/api/run/start", json={}, headers={b"X-FAT-Token": b"\xff"})
    assert response.status_code == 403


def test_same_project_revision_prevents_lost_update_and_stale_start(client):
    response = client.get("/api/project")
    project = response.json()
    revision = response.headers["X-FAT-Project-Revision"]
    context = {"X-FAT-Project-ID": project["id"], "X-FAT-Project-Revision": revision}
    original = json.loads(json.dumps(project))
    project["name"] = "Saved from the first tab"
    saved = client.put("/api/project", json=project, headers=context)
    assert saved.status_code == 200
    assert saved.headers["X-FAT-Project-Revision"] != revision
    for path, method, payload in (
        ("/api/project", "put", original),
        ("/api/mapping", "post", {"csv": export_mapping(demo_project())}),
        ("/api/run/start", "post", {}),
    ):
        assert getattr(client, method)(path, json=payload, headers=context).status_code == 409
    assert client.get("/api/project").json()["name"] == project["name"]
    state = client.get("/api/state").json()
    assert state["status"] == "idle"
    assert state["project_revision"] == saved.headers["X-FAT-Project-Revision"]


@pytest.mark.parametrize("pointer", [None, [], {"id": 7}, {"id": "../other"}])
def test_malformed_startup_pointer_recovers_without_dropping_projects(tmp_path, pointer):
    (tmp_path / "projects").mkdir()
    saved = demo_project().model_dump_json()
    path = tmp_path / "projects" / f"{demo_project().id}.json"
    path.write_text(saved, encoding="utf-8")
    (tmp_path / "last-project.json").write_text(json.dumps(pointer), encoding="utf-8")
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        assert "illisible" in client.get("/api/state").json()["error"]
        assert client.get("/api/project").json()["id"].startswith("recovery-")
    assert path.read_text(encoding="utf-8") == saved


def test_startup_does_not_overwrite_previous_saved_revision(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        client.headers["X-FAT-Token"] = client.get("/api/session").json()["token"]
        project = client.get("/api/project").json()
        previous_name = project["name"]
        project["name"] = "A newer saved revision"
        assert client.put("/api/project", json=project).status_code == 200
    backup = tmp_path / "projects" / f"{project['id']}.previous.json"
    assert json.loads(backup.read_text(encoding="utf-8"))["name"] == previous_name
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        assert client.get("/api/project").json()["name"] == project["name"]
    assert json.loads(backup.read_text(encoding="utf-8"))["name"] == previous_name


def test_csv_parser_failure_is_a_validation_error_and_preserves_project(client):
    before = client.get("/api/project").json()
    exported = client.get("/api/mapping").text
    oversized = exported.replace("pump_cmd,", 'pump_cmd,"' + "x" * 140000 + '",', 1)
    response = client.post("/api/mapping", json={"csv": oversized})
    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]
    assert client.get("/api/project").json() == before


def test_annotation_storage_failure_is_visible_and_stops_the_active_run(client, monkeypatch):
    assert client.post("/api/run/start", json={}).status_code == 200
    def no_journal(*args, **kwargs):
        raise sqlite3.OperationalError("disk is full")
    monkeypatch.setattr(client.app.state.store, "event", no_journal)
    response = client.post("/api/markers", json={"message": "This must be recorded"})
    assert response.status_code == 503
    state = client.get("/api/state").json()
    assert state["status"] == "error"
    assert "disk is full" in state["error"]
    assert state["events"][-1]["details"]["persisted"] is False
    assert not client.app.state.runtime.adapter.connected
    assert client.app.state.runtime._task is None


def test_project_revision_is_returned_for_all_project_replacement_routes(client):
    for path, payload in (
        ("/api/project/import", demo_project().model_dump(mode="json")),
        ("/api/projects", {"name": "New project"}),
        ("/api/demo/load", None),
        (f"/api/projects/{demo_project().id}/load", None),
        ("/api/mapping", {"csv": export_mapping(demo_project())}),
    ):
        response = client.post(path, json=payload)
        assert response.status_code == 200
        assert response.headers["X-FAT-Project-Revision"] == client.get("/api/state").json()["project_revision"]
