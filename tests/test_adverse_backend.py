"""Adverse backend behavior: preservation, atomic evidence and stale operators."""

import asyncio
import csv
import html
import io
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from fat_studio.adapters.demo import DemoAdapter
from fat_studio.app import create_app
from fat_studio.demo import demo_project
from fat_studio.mapping import FIELDS, export_mapping, import_mapping
from fat_studio.models import Project, Tag
from fat_studio.reporting import csv_stream, html_report
from fat_studio.runtime import Runtime
from fat_studio.security import MachinePolicy
from fat_studio.storage import Store


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        client.headers["X-FAT-Token"] = client.get("/api/session").json()["token"]
        yield client


@pytest.fixture
def runtime(tmp_path):
    store = Store(tmp_path)
    instance = Runtime(store, demo_project(), MachinePolicy(tmp_path / "policy.json"))
    yield instance
    store.close()


def test_reloading_saved_project_preserves_previous_revision(client, tmp_path):
    original = client.get("/api/project").json()
    updated = {**original, "name": "Reviewed new revision"}
    assert client.put("/api/project", json=updated).status_code == 200
    backup = tmp_path / "projects" / f"{original['id']}.previous.json"
    previous = backup.read_bytes()
    assert json.loads(previous) == original
    assert client.post("/api/projects", json={"name": "Another bench"}).status_code == 200
    assert client.post(f"/api/projects/{original['id']}/load").status_code == 200
    assert backup.read_bytes() == previous


def test_startup_without_pointer_preserves_existing_saved_demo(tmp_path):
    saved = demo_project()
    saved.name = "The user's modified and saved demo"
    projects = tmp_path / "projects"
    projects.mkdir()
    path = projects / f"{saved.id}.json"
    path.write_text(saved.model_dump_json(indent=2), encoding="utf-8")
    previous = path.read_bytes()
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        assert path.read_bytes() == previous
        assert client.get("/api/state").json()["error"]
    assert path.read_bytes() == previous


def test_project_listing_marks_internal_filename_mismatch_as_unloadable(tmp_path):
    store = Store(tmp_path)
    try:
        project = demo_project()
        store.save_project(project)
        wrong = store.projects_dir / "wrong-name.json"
        wrong.write_text(project.model_dump_json(), encoding="utf-8")
        entries = store.list_projects()
        assert len([entry for entry in entries if entry["id"] == project.id]) == 1
        damaged = next(entry for entry in entries if entry["id"] == "wrong-name")
        assert "identifiant interne" in damaged["error"]
        assert store.load_project(project.id) == project
    finally:
        store.close()


def test_result_is_exposed_and_resets_only_for_a_new_run(client):
    initial = {"verdict": "not_evaluated", "comment": ""}
    assert client.get("/api/state").json()["result"] == initial
    assert client.post("/api/run/start", json={}).status_code == 200
    assert client.post("/api/run/pause").status_code == 200
    result = {"verdict": "fail", "comment": "Observed by the operator"}
    assert client.post("/api/result", json=result).json()["result"] == result
    assert client.get("/api/state").json()["result"] == result
    assert client.post("/api/run/stop").json()["result"] == result
    run_id = client.get("/api/state").json()["run_id"]
    assert client.post("/api/run/reset").json()["result"] == initial
    assert client.get(f"/api/runs/{run_id}/json").json()["result"] == result
    assert client.post("/api/run/start", json={}).json()["result"] == initial


def test_failed_result_journal_does_not_commit_a_verdict(client):
    assert client.post("/api/run/start", json={}).status_code == 200
    assert client.post("/api/run/pause").status_code == 200
    store = client.app.state.store
    store.db.execute("""
        CREATE TRIGGER reject_result_event BEFORE INSERT ON events
        WHEN NEW.kind = 'user_result'
        BEGIN SELECT RAISE(ABORT, 'injected journal failure'); END
    """)
    response = client.post("/api/result", json={"verdict": "pass", "comment": "Must be atomic"})
    assert response.status_code == 503
    exported = client.get("/api/export/json").json()
    assert exported["result"] == {"verdict": "not_evaluated", "comment": ""}
    assert not any(event["kind"] == "user_result" for event in exported["events"])


def test_actions_from_a_previous_run_cannot_target_a_replacement_run(client):
    assert client.post("/api/run/start", json={}).status_code == 200
    first = client.get("/api/state").json()["run_id"]
    assert client.post("/api/run/stop").status_code == 200
    assert client.post("/api/run/start", json={}).status_code == 200
    replacement = client.get("/api/state").json()["run_id"]
    assert replacement != first
    for path, payload in (
        ("/api/result", {"verdict": "pass", "comment": "Old run conclusion"}),
        ("/api/markers", {"message": "Old run annotation"}),
        ("/api/force", {"tag_id": "level", "value": 55.0}),
        ("/api/run/stop", None),
    ):
        response = client.post(path, json=payload, headers={"X-FAT-Run-ID": first})
        assert response.status_code == 409, (path, response.text)
    assert client.get("/api/state").json()["status"] == "running"
    assert client.post("/api/run/pause", headers={"X-FAT-Run-ID": ""}).status_code == 409
    assert client.post("/api/run/pause", headers={"X-FAT-Run-ID": replacement}).status_code == 200


def test_mapping_export_rejects_a_stale_project_context(client):
    opened = client.get("/api/project")
    project = opened.json()
    context = {"X-FAT-Project-ID": project["id"],
               "X-FAT-Project-Revision": opened.headers["X-FAT-Project-Revision"]}
    project["tags"][0]["name"] = "Changed in another tab"
    saved = client.put("/api/project", json=project, headers=context)
    assert saved.status_code == 200
    assert client.get("/api/mapping", headers=context).status_code == 409
    context["X-FAT-Project-Revision"] = saved.headers["X-FAT-Project-Revision"]
    exported = client.get("/api/mapping", headers=context)
    assert exported.status_code == 200
    assert exported.headers["X-FAT-Project-Revision"] == context["X-FAT-Project-Revision"]
    context["X-FAT-Project-ID"] = "another-project"
    assert client.get("/api/mapping", headers=context).status_code == 409


@pytest.mark.parametrize("action", ["force", "release", "fault", "clear_fault"])
async def test_unrecorded_model_change_stops_before_another_plc_write(runtime, monkeypatch, action):
    await runtime.start(background=False)
    await runtime.force("level", 55.0)
    await runtime.fault("P101", "motor_trip")
    count = runtime.write_count

    def no_journal(*args, **kwargs):
        raise sqlite3.OperationalError("injected disk failure")

    monkeypatch.setattr(runtime.store, "event", no_journal)
    calls = {"force": ("level", 60.0), "release": ("level",),
             "fault": ("P101", "motor_trip"), "clear_fault": ("P101",)}
    with pytest.raises(sqlite3.OperationalError, match="injected disk failure"):
        await getattr(runtime, action)(*calls[action])
    assert runtime.status == "error"
    assert not runtime.adapter.connected
    await runtime.tick()
    assert runtime.write_count == count


async def test_cancelled_connection_is_closed_and_recorded_as_error(runtime):
    connected = asyncio.Event()

    class WaitingConnection(DemoAdapter):
        async def connect(self):
            await super().connect()
            connected.set()
            await asyncio.Event().wait()

    runtime.adapter_factory = WaitingConnection
    startup = asyncio.create_task(runtime.start(background=False))
    await asyncio.wait_for(connected.wait(), timeout=1)
    startup.cancel()
    with pytest.raises(asyncio.CancelledError):
        await startup
    assert not runtime.adapter.connected
    assert runtime.status == "error"
    assert runtime.store.run(runtime.run_id)["status"] == "error"
    assert runtime._task is None


async def test_cancelled_cycle_after_a_write_cannot_leave_a_silent_running_run(runtime):
    written = asyncio.Event()

    class WaitingWrite(DemoAdapter):
        async def write(self, inputs):
            await super().write(inputs)
            written.set()
            await asyncio.Event().wait()

    runtime.adapter_factory = WaitingWrite
    await runtime.start()
    task = runtime._task
    await asyncio.wait_for(written.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert runtime.status == "error"
    assert not runtime.adapter.connected
    assert runtime._task is None
    evidence = runtime.store.run(runtime.run_id)
    assert evidence["status"] == "error" and evidence["ended_at"]
    assert evidence["sample_count"] == 1
    sample = next(runtime.store.samples(runtime.run_id))
    assert set(sample["qualities"].values()) == {"bad"}
    count = runtime.write_count
    await runtime.tick()
    assert runtime.write_count == count


@pytest.mark.parametrize("operation", ["pause", "resume", "stop", "reset"])
async def test_cancelled_lifecycle_transition_is_recorded_and_cannot_resume(runtime, operation):
    waiting = asyncio.Event()

    class WaitingLifecycle(DemoAdapter):
        block_connect = False
        block_disconnect = False

        async def connect(self):
            await super().connect()
            if self.block_connect:
                self.block_connect = False
                waiting.set()
                await asyncio.Event().wait()

        async def disconnect(self):
            await super().disconnect()
            if self.block_disconnect:
                self.block_disconnect = False
                waiting.set()
                await asyncio.Event().wait()

    runtime.adapter_factory = WaitingLifecycle
    await runtime.start(background=False)
    if operation in ("resume", "reset"):
        await runtime.pause()
    if operation == "resume":
        runtime.adapter.block_connect = True
    else:
        runtime.adapter.block_disconnect = True
    transition = asyncio.create_task(getattr(runtime, operation)())
    await asyncio.wait_for(waiting.wait(), timeout=1)
    transition.cancel()
    with pytest.raises(asyncio.CancelledError):
        await transition
    assert runtime.status == "error"
    assert not runtime.adapter.connected
    assert runtime.store.run(runtime.run_id)["status"] == "error"
    assert runtime._task is None


def test_mapping_export_is_formula_safe_and_exactly_reversible():
    values = ["=1+1", "+SUM(1,2)", "-2+3", "@SUM(1,2)", "\t=1+1", "\r=1+1",
              "  =1+1", "'=literal", "''already quoted", "normal text"]
    project = Project(id="mapping", name="Mapping review", tags=[
        Tag(id=f"t{index}", name=value, unit=value, node_id=value, direction="input", data_type="REAL",
            initial_value=-2.5, min=-10.0, max=10.0, writable=True)
        for index, value in enumerate(values)
    ])
    exported = export_mapping(project)
    rows = list(csv.DictReader(io.StringIO(exported)))
    for original, row in zip(values, rows, strict=True):
        assert row["_fat_csv_encoding"] == "apostrophe-v1"
        expected = "'" + original if original.startswith("'") or original.lstrip().startswith(("=", "+", "-", "@")) else original
        assert row["name"] == row["unit"] == row["node_id"] == expected
        assert row["initial_value"] == "-2.5"
        assert row["min"] == "-10.0"
    assert import_mapping(project, exported) == project
    with pytest.raises(ValueError, match="encodage"):
        import_mapping(project, exported.replace("apostrophe-v1", "unknown-v2"))


def test_legacy_mapping_import_keeps_literal_apostrophes_and_formulas():
    project = Project(id="mapping", name="Legacy mapping", tags=[
        Tag(id="legacy", name="'=literal", unit="-custom", node_id="=node", direction="input",
            data_type="REAL", initial_value=-2.5, min=-10.0, max=10.0, writable=True)
    ])
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    row = project.tags[0].model_dump()
    row["initial_value"] = json.dumps(row["initial_value"])
    row["writable"] = "true"
    writer.writerow(row)
    assert import_mapping(project, stream.getvalue()) == project


async def test_evidence_exports_escape_formula_and_html_metadata(runtime):
    project = demo_project()
    payloads = ["=1+1", "+SUM(1,2)", "-2+3", "@SUM(1,2)", "\t=1+1", "\r=1+1", " \n@SUM(1,2)"]
    for tag, text in zip(project.tags, payloads, strict=False):
        tag.name = text
        tag.unit = text
    # Mapping is a machine exchange format, including the exact original text.
    assert import_mapping(project, export_mapping(project)) == project
    runtime.set_project(project)
    await runtime.start(background=False)
    await runtime.tick()
    user_text = '<script>alert("x")</script> & <img src=x onerror="alert(2)">'
    await runtime.marker(user_text)
    await runtime.set_result("fail", user_text)
    await runtime.stop()
    rows = list(csv.DictReader(io.StringIO("".join(csv_stream(runtime.store, runtime.run_id)).lstrip("\ufeff"))))
    by_id = {row["tag_id"]: row for row in rows}
    for tag, text in zip(project.tags, payloads, strict=False):
        assert by_id[tag.id]["tag_name"] == "'" + text
        assert by_id[tag.id]["unit"] == "'" + text
    report = html_report(runtime.store, runtime.run_id)
    assert user_text not in report
    assert html.escape(user_text) in report


def test_archived_exports_are_isolated_from_the_running_trial(client):
    assert client.post("/api/run/start", json={}).status_code == 200
    first = client.get("/api/state").json()["run_id"]
    assert client.post("/api/markers", json={"message": "First trial marker"}).status_code == 200
    assert client.post("/api/result", json={"verdict": "fail", "comment": "First conclusion"}).status_code == 200
    assert client.post("/api/run/stop").status_code == 200
    assert client.post("/api/run/start", json={}).status_code == 200
    second = client.get("/api/state").json()["run_id"]
    assert client.post("/api/markers", json={"message": "Second trial marker"}).status_code == 200
    exported = client.get(f"/api/runs/{first}/json").json()
    assert exported["id"] == first
    assert exported["result"]["comment"] == "First conclusion"
    assert all(event["message"] != "Second trial marker" for event in exported["events"])
    for kind in ("csv", "report"):
        response = client.get(f"/api/runs/{first}/{kind}")
        assert response.status_code == 200
        assert second not in response.text
    state = client.get("/api/state").json()
    assert state["run_id"] == second and state["status"] == "running"
