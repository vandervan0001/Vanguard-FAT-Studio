import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from fat_studio.app import create_app
from fat_studio.demo_lab import demo_lab_project
from fat_studio.exchange import ProjectPackage, ScenarioPackage, import_scenarios, project_package, read_project, scenarios_package


def test_project_json_round_trip_and_unsupported_versions_preserve_the_original():
    project = demo_lab_project()
    assert read_project(json.loads(project_package(project).model_dump_json())) == project
    assert read_project(project.model_dump(mode="json")) == project
    payload = project_package(project).model_dump(mode="json")
    payload["version"] = "99.0"
    with pytest.raises(ValidationError):
        read_project(payload)
    assert ProjectPackage.model_json_schema()["properties"]["version"]["const"] == "1.0"


def test_scenario_packages_keep_units_false_values_and_refuse_contract_or_id_collisions():
    project = demo_lab_project()
    package = scenarios_package(project, "demo-guided-io")
    assert ScenarioPackage.model_validate_json(package.model_dump_json()) == package
    assert package.scenarios[0].fat_steps[0].actions[0].value is False
    assert package.scenarios[0].fat_steps[0].actions[-1].unit == "mA"
    before = project.model_dump_json()
    with pytest.raises(ValueError, match="existe déjà"):
        import_scenarios(project, package)
    package.scenarios[0].id = "new-guided"
    assert len(import_scenarios(project, package).scenarios) == 10
    package.tag_contracts[0].direction = "output" if package.tag_contracts[0].direction == "input" else "input"
    with pytest.raises(ValueError, match="incompatible"):
        import_scenarios(project, package)
    assert project.model_dump_json() == before


def test_pause_edit_archive_restore_and_cross_workspace_context_are_observable(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        client.headers["X-FAT-Token"] = client.get("/api/session").json()["token"]
        project_response = client.get("/api/project")
        project = project_response.json()
        assert project["id"] == "public-io-lab"
        started = client.post("/api/run/start", json={"scenario_id": "demo-guided-io"}).json()
        run_id = started["run_id"]
        assert client.put("/api/project", json=project).status_code == 409
        assert client.post("/api/run/pause").status_code == 200
        project["name"] = "Builder draft committed during pause"
        saved = client.put("/api/project", json=project)
        assert saved.status_code == 200
        state = client.get("/api/state").json()
        assert state["status"] == "idle" and state["run_id"] is None
        assert client.post("/api/run/resume").status_code == 409
        old_evidence = client.get(f"/api/runs/{run_id}/json").json()
        assert old_evidence["status"] == "stopped"
        assert old_evidence["project"]["name"] != project["name"]
        assert old_evidence["result"]["verdict"] == "not_evaluated"
        expected = {"X-FAT-Project-ID": project["id"], "X-FAT-Project-Revision": saved.headers["X-FAT-Project-Revision"], "X-FAT-Run-ID": ""}
        archive = client.get("/api/project/archive", headers=expected)
        assert archive.status_code == 200
        imported = client.post("/api/project/archive/import", content=archive.content, headers={**expected, "Content-Type": "application/zip"})
        assert imported.status_code == 200
        assert imported.json() == project
        assert imported.headers["X-FAT-Project-Revision"] != expected["X-FAT-Project-Revision"]
        assert client.post("/api/run/start", json={}, headers=expected).status_code == 409
        assert client.get("/api/project/download", headers=expected).status_code == 409
        for kind in ("json", "csv", "report"):
            assert client.get(f"/api/runs/{run_id}/{kind}", headers=expected).status_code == 409
        assert len(client.get("/api/workspaces").json()) == 2
        assert client.get("/api/state").json()["status"] == "idle"
        assert client.get(f"/api/runs/{run_id}/json").json()["samples"] == old_evidence["samples"]
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as restarted:
        assert restarted.get("/api/project").json() == project
        assert restarted.get("/api/state").json()["status"] == "idle"
        assert len(restarted.get("/api/runs").json()) == 1


async def test_failed_paused_edit_cannot_rewrite_an_already_completed_run(tmp_path, monkeypatch):
    from fat_studio.runtime import Runtime
    from fat_studio.security import MachinePolicy
    from fat_studio.storage import Store

    store = Store(tmp_path)
    runtime = Runtime(store, demo_lab_project(), MachinePolicy(tmp_path / "policy.json"))
    try:
        await runtime.start("demo-fill-source", background=False)
        for _ in range(100):
            if runtime.status != "running":
                break
            await runtime.tick()
        assert runtime._run_finished and runtime.scenario_state == "completed"
        def rows():
            return [dict(row) for table in ("runs", "samples", "events") for row in store.db.execute(f"SELECT * FROM {table}")]
        before = rows()
        candidate = runtime.project.model_copy(deep=True)
        candidate.name = "Uncommitted draft"
        def fail_save(project):
            raise OSError("Deliberate project storage failure after completed FAT")
        monkeypatch.setattr(store, "save_project", fail_save)
        with pytest.raises(OSError):
            await runtime.replace_project(candidate)
        assert runtime.status == "error" and not runtime.connection["connected"]
        assert all(quality == "bad" for quality in runtime.engine.qualities.values())
        assert rows() == before
        assert runtime.project.name != candidate.name
    finally:
        await runtime.close()
        store.close()


def test_archive_compression_allows_health_and_stop_without_changing_its_snapshot(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from fat_studio import app as app_module
    from fat_studio.archive import prepare_archive

    entered, release = Event(), Event()
    original_export = app_module.export_archive
    def delayed_export(store, project):
        entered.set()
        assert release.wait(5), "Archive test worker was not released"
        return original_export(store, project)
    monkeypatch.setattr(app_module, "export_archive", delayed_export)
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client, ThreadPoolExecutor(max_workers=3) as pool:
        client.headers["X-FAT-Token"] = client.get("/api/session").json()["token"]
        started = client.post("/api/run/start", json={"scenario_id": "demo-guided-io"}).json()
        pending = pool.submit(client.get, "/api/project/archive")
        assert entered.wait(2)
        try:
            assert pool.submit(client.get, "/api/health").result(timeout=2).status_code == 200
            stopped = pool.submit(client.post, "/api/run/stop", json={}).result(timeout=2)
            assert stopped.status_code == 200 and stopped.json()["status"] == "stopped"
            assert not pending.done()
        finally:
            release.set()
        exported = pending.result(timeout=5)
        assert exported.status_code == 200
        plan = prepare_archive(exported.content)
        document = json.loads(dict(plan.files)[f"runs/{started['run_id']}/evidence.json"])
        assert document["status"] == "running" and document["ended_at"] is None
        assert not any(event["kind"] == "stop" for event in document["events"])
        current = client.get(f"/api/runs/{started['run_id']}/json").json()
        assert current["status"] == "stopped" and current["ended_at"] is not None
