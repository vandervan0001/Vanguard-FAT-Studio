"""Preview contracts: no persistence, no hidden replacement of used variables."""

from copy import deepcopy

from fastapi.testclient import TestClient
import pytest

from fat_studio.app import create_app
from fat_studio.demo import demo_project
from fat_studio.mapping import export_mapping, preview_mapping
from fat_studio.models import Project, Tag


def test_merge_preserves_other_tags_consumers_and_saved_input():
    project = demo_project()
    original = project.model_copy(deep=True)
    incoming = Project(id="csv", name="CSV", tags=[project.tags[0].model_copy(deep=True),
                       Tag(id="new_sensor", name="New sensor", direction="input", data_type="REAL", writable=True)])
    incoming.tags[0].name = "Renamed without changing identity"
    preview = preview_mapping(project, export_mapping(incoming))
    merged = preview["project"]
    assert merged.tags[0].name == incoming.tags[0].name
    assert [tag.id for tag in merged.tags] == [tag.id for tag in project.tags] + ["new_sensor"]
    assert merged.equipment == project.equipment and merged.scenarios == project.scenarios
    assert preview["errors"] == []
    assert [row["kind"] for row in preview["changes"]] == ["changed", "added"]
    assert project == original


@pytest.mark.parametrize("change", ["direction", "data_type", "unit", "signal", "removed"])
def test_import_explains_and_blocks_used_tag_contract_changes(change):
    project = demo_project()
    tag_id = next(tag.id for tag in project.tags if tag.direction == "input" and tag.data_type == "REAL")
    tag = next(tag for tag in project.tags if tag.id == tag_id).model_copy(deep=True)
    data = tag.model_dump()
    if change == "direction":
        data.update(direction="output", writable=False)
    elif change == "data_type":
        data.update(data_type="INT", initial_value=0)
    elif change == "unit":
        data["unit"] = "bar"
    elif change == "signal":
        data["signal"] = {"kind": "linear", "raw_min": 0., "raw_max": 100.}
    incoming = Project(id="csv", name="CSV", tags=[] if change == "removed" else [Tag.model_validate(data)])
    result = preview_mapping(project, export_mapping(incoming), "replace" if change == "removed" else "merge")
    row = next(row for row in result["changes"] if row["id"] == tag_id)
    assert row["blocked"] and row["reasons"] and result["errors"]
    assert result["project"].equipment == project.equipment


def test_mapping_keeps_literal_csv_encoding_and_limits():
    project = Project(id="base", name="base", tags=[Tag(id="one", name="'=literal", direction="input", data_type="REAL")])
    incoming = Project(id="csv", name="CSV", tags=[Tag(id="two", name="=Formula-looking literal", direction="input", data_type="REAL")])
    result = preview_mapping(project, export_mapping(incoming))
    assert [tag.name for tag in result["project"].tags] == ["'=literal", "=Formula-looking literal"]
    project.tags = [Tag(id=f"tag_{i}", name=f"Tag {i}", direction="input", data_type="REAL") for i in range(200)]
    with pytest.raises(ValueError, match="200"):
        preview_mapping(project, export_mapping(incoming))
    with pytest.raises(ValueError, match="colonnes|Colonnes"):
        preview_mapping(project, "id,invalid\nhello,world\n")


def scope(client):
    response = client.get("/api/project")
    state = client.get("/api/state").json()
    return response.json(), {"X-FAT-Token": client.get("/api/session").json()["token"],
                             "X-FAT-Project-ID": response.json()["id"],
                             "X-FAT-Project-Revision": response.headers["X-FAT-Project-Revision"],
                             "X-FAT-Run-ID": state["run_id"] or ""}


def test_preview_routes_require_context_preserve_state_and_never_save(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        original, headers = scope(client)
        before = client.get("/api/state").json()
        draft = deepcopy(original)
        draft["name"] = "Draft only"
        draft["equipment"][1]["bindings"] = {}
        validation = client.post("/api/validate/preview", json=draft, headers=headers)
        assert validation.status_code == 200 and not validation.json()["valid"]
        assert validation.json()["project"]["name"] == "Draft only"
        minimal = {"id": original["id"], "name": "Normalized draft"}
        normalized = client.post("/api/validate/preview", json=minimal, headers=headers)
        assert normalized.status_code == 200
        assert normalized.json()["project"]["tags"] == []
        assert normalized.json()["project"]["plc"]["mode"] == "demo"
        assert "X-FAT-Project-Revision" not in normalized.headers
        incoming = Project(id="csv", name="CSV", tags=[Tag(id="new_preview", name="Preview", direction="input", data_type="REAL")])
        body = {"project": draft, "csv": export_mapping(incoming), "mode": "merge"}
        result = client.post("/api/mapping/preview", json=body, headers=headers)
        assert result.status_code == 200 and result.json()["project"]["name"] == "Draft only"
        assert client.get("/api/project").json() == original
        after = client.get("/api/state").json()
        for key in ("run_id", "status", "project_revision", "write_count", "result"):
            assert after[key] == before[key]
        for path, payload in (("/api/validate/preview", draft), ("/api/mapping/preview", body)):
            assert client.post(path, json=payload).status_code == 403
            assert client.post(path, json=payload, headers={"X-FAT-Token": headers["X-FAT-Token"]}).status_code == 409
            stale = {**headers, "X-FAT-Project-Revision": "stale"}
            assert client.post(path, json=payload, headers=stale).status_code == 409
        wrong = {**draft, "id": "another_project"}
        assert client.post("/api/validate/preview", json=wrong, headers=headers).status_code == 409


def test_csv_and_browse_previews_refuse_running_and_paused_trials(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        project, headers = scope(client)
        assert client.post("/api/run/start", json={}, headers=headers).status_code == 200
        for paused in (False, True):
            project, headers = scope(client)
            if paused:
                assert client.post("/api/run/pause", headers=headers).status_code == 200
            for path, body in (("/api/mapping/preview", {"project": project, "csv": "", "mode": "merge"}),
                               ("/api/opcua/browse", {"project": project, "confirmation": "anything"})):
                result = client.post(path, json=body, headers=headers)
                assert result.status_code == 409 and "Arrêtez" in result.json()["detail"]
        assert client.post("/api/run/stop", headers=headers).status_code == 200


def test_readonly_browse_does_not_let_imported_project_authorize_target(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        project, headers = scope(client)
        project["plc"].update(mode="opcua", approved_virtual_target="Missing", expected_application_uri="urn:test")
        result = client.post("/api/opcua/browse", json={"project": project, "confirmation": "Missing @ " + project["plc"]["endpoint"]}, headers=headers)
        assert result.status_code == 403 and "politique" in result.json()["detail"]
        assert client.get("/api/project").json()["plc"]["mode"] == "demo"
        assert client.get("/api/state").json()["write_count"] == 0
