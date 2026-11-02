import asyncio
import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from fat_studio.adapters.demo import DemoAdapter
from fat_studio.demo import demo_project
from fat_studio.reporting import csv_stream, html_report, json_stream
from fat_studio.runtime import RunConflict, Runtime
from fat_studio.security import MachinePolicy
from fat_studio.storage import Store


@pytest.fixture
def runtime(tmp_path):
    store = Store(tmp_path)
    instance = Runtime(store, demo_project(), MachinePolicy(tmp_path / "policy.json"))
    yield instance
    store.close()


@pytest.mark.parametrize("scenario", ["reference", "motor-trip", "sensor-freeze"])
async def test_reference_scenarios_execute_and_archive(runtime, scenario):
    await runtime.start(scenario, background=False)
    for _ in range(400):
        if runtime.status != "running":
            break
        await runtime.tick()
    assert runtime.status == "paused"
    assert runtime.scenario_state == "completed"
    assert runtime.assertions and all(result["passed"] for result in runtime.assertions)
    assert not runtime.connection["connected"]
    record = runtime.store.run(runtime.run_id)
    assert record["status"] == "completed" and record["ended_at"]
    assert record["result"]["verdict"] == "not_evaluated"
    assert record["sample_count"] >= 200
    with pytest.raises(RunConflict):
        await runtime.resume(background=False)
    await runtime.stop()
    assert runtime.store.run(runtime.run_id)["status"] == "completed"


async def test_pause_resume_preserves_model_and_demo_hysteresis(runtime):
    await runtime.start(background=False)
    for _ in range(250):
        await runtime.tick()
    assert runtime.engine.values["pump_cmd"] is False
    before = copy.deepcopy(runtime.engine.values)
    clock = runtime.engine.time_s
    await runtime.pause()
    await runtime.tick()
    assert runtime.engine.time_s == clock and runtime.engine.values == before
    await runtime.resume(background=False)
    await runtime.tick()
    assert runtime.engine.values["pump_cmd"] is False
    assert runtime.engine.time_s > clock


async def test_replay_determinism_and_evidence_survive_reset(runtime):
    traces = []
    ids = []
    for _ in range(2):
        await runtime.start("reference", background=False)
        ids.append(runtime.run_id)
        for _ in range(320):
            await runtime.tick()
        traces.append([sample["values"] for sample in runtime.store.samples(runtime.run_id)])
        await runtime.reset()
    assert traces[0] == traces[1]
    assert ids[0] != ids[1]
    assert len(runtime.store.runs()) == 2
    assert runtime.engine.time_s == 0 and runtime.engine.forces == {}


class FailingAdapter(DemoAdapter):
    async def read(self, values, dt):
        if self.write_count:
            raise ConnectionError("PLC link lost")
        return await super().read(values, dt)


async def test_read_loss_stops_all_further_writes_and_requires_explicit_restart(runtime):
    runtime.adapter_factory = FailingAdapter
    await runtime.start(background=False)
    await runtime.tick()
    count = runtime.write_count
    await runtime.tick()
    assert runtime.status == "error"
    assert runtime.write_count == count
    assert not runtime.connection["connected"]
    assert all(tag["quality"] == "bad" for tag in runtime.snapshot()["tags"].values())
    for _ in range(3):
        await runtime.tick()
    assert runtime.write_count == count
    assert runtime.store.run(runtime.run_id)["status"] == "error"
    assert "PLC link lost" in html_report(runtime.store, runtime.run_id)
    with pytest.raises(RunConflict):
        await runtime.resume(background=False)


async def test_active_run_cannot_be_edited_or_forced_on_plc_outputs(runtime):
    await runtime.start(background=False)
    with pytest.raises(RunConflict):
        runtime.set_project(demo_project())
    with pytest.raises(ValueError):
        await runtime.force("pump_cmd", True)
    with pytest.raises(ValueError):
        await runtime.force("level", 101)
    await runtime.force("level", 55)
    await runtime.tick()
    assert runtime.snapshot()["tags"]["level"]["forced"]
    assert runtime.engine.values["level"] == 55
    await runtime.release("level")
    await runtime.tick()
    assert runtime.engine.values["level"] != 55


async def test_reports_contain_original_project_and_safe_user_text(runtime):
    await runtime.start(background=False)
    await runtime.tick()
    runtime.event("marker", '<script>alert("x")</script>')
    runtime.store.set_result(runtime.run_id, "fail", '<img src=x onerror="alert(1)">')
    await runtime.stop()
    html = html_report(runtime.store, runtime.run_id)
    assert '<script>alert' not in html
    assert "&lt;script&gt;" in html
    assert "REFUSÉ" in html
    evidence = json.loads("".join(json_stream(runtime.store, runtime.run_id)))
    assert evidence["samples"] and evidence["project"]["name"] == runtime.project.name
    assert len(evidence["project_sha256"]) == 64
    csv = "".join(csv_stream(runtime.store, runtime.run_id))
    assert "timestamp_utc" in csv and "quality" in csv


async def test_background_pause_resume_stop_has_no_orphan_writer(runtime):
    await runtime.start()
    for _ in range(30):
        if runtime.write_count:
            break
        await asyncio.sleep(0.01)
    await runtime.pause()
    count = runtime.write_count
    await asyncio.sleep(0.15)
    assert runtime.write_count == count
    await runtime.resume()
    await asyncio.sleep(0.15)
    assert runtime.write_count > count
    await runtime.stop()
    count = runtime.write_count
    await asyncio.sleep(0.15)
    assert runtime.write_count == count
    assert runtime._task is None


async def test_live_mode_rejects_accelerated_clock_before_connection(runtime):
    runtime.project.plc.mode = "opcua"
    runtime.project.simulation.speed = 2
    # Policy is not consulted: incompatible timing is rejected before adapter creation.
    runtime.project.plc.expected_application_uri = "urn:test"
    runtime.project.plc.approved_virtual_target = "fixture"
    with pytest.raises(ValueError, match="vitesse"):
        await runtime.start(background=False)


async def test_scenario_terminal_action_is_recorded_without_extra_write(runtime):
    from fat_studio.models import Scenario, ScenarioStep
    runtime.project.scenarios = [Scenario(id="short", name="Short", duration_s=0.2,
        steps=[ScenarioStep(at_s=0.2, action="marker", message="Final boundary")])]
    await runtime.start("short", background=False)
    await runtime.tick()
    await runtime.tick()
    assert runtime.scenario_state == "completed"
    assert any(event["message"] == "Final boundary" for event in runtime.events)
    assert runtime.engine.time_s == pytest.approx(0.2)


def test_recovery_marks_unclosed_runs_interrupted(tmp_path):
    store = Store(tmp_path)
    store.start_run("run-interrupted", demo_project(), None, {"target": "demo"})
    store.close()
    store = Store(tmp_path)
    assert store.run("run-interrupted")["status"] == "interrupted"
    assert store.run("run-interrupted")["ended_at"]
    store.close()


def test_second_process_cannot_open_the_same_evidence_store(tmp_path):
    first = Store(tmp_path)
    try:
        with pytest.raises(ValueError, match="autre processus"):
            Store(tmp_path)
    finally:
        first.close()
    reopened = Store(tmp_path)
    reopened.close()


async def test_streaming_export_is_a_frozen_prefix_while_run_continues(runtime):
    await runtime.start(background=False)
    await runtime.tick()
    stream = json_stream(runtime.store, runtime.run_id)
    await runtime.tick()
    runtime.event("marker", "Added after export snapshot")
    exported = json.loads("".join(stream))
    assert exported["sample_count"] == len(exported["samples"]) == 1
    assert all(event["message"] != "Added after export snapshot" for event in exported["events"])
    assert runtime.store.run(runtime.run_id)["sample_count"] == 2


async def test_sample_iterator_can_move_between_streaming_worker_threads(runtime):
    await runtime.start(background=False)
    await runtime.tick()
    await runtime.tick()
    samples = runtime.store.samples(runtime.run_id)
    with ThreadPoolExecutor(max_workers=1) as first, ThreadPoolExecutor(max_workers=1) as second:
        assert first.submit(next, samples).result()["sim_time_s"] == pytest.approx(0.1)
        assert second.submit(next, samples).result()["sim_time_s"] == pytest.approx(0.2)
        second.submit(samples.close).result()


def test_export_data_directory_with_uri_reserved_characters(tmp_path):
    # '#' and '%' are valid on both Windows and Linux and require URI encoding.
    store = Store(tmp_path / "FAT # evidence %20")
    try:
        store.start_run("run-reserved-path", demo_project(), None, {"target": "demo"})
        store.sample("run-reserved-path", 0.1, {"level": 42}, {"level": "good"})
        assert list(store.samples("run-reserved-path"))[0]["values"] == {"level": 42}
    finally:
        store.close()


async def test_evidence_write_failure_stops_and_remains_visible_when_logging_also_fails(runtime, monkeypatch):
    await runtime.start(background=False)
    def no_storage(*args, **kwargs):
        raise sqlite3.OperationalError("disk is full")
    monkeypatch.setattr(runtime.store, "sample", no_storage)
    monkeypatch.setattr(runtime.store, "event", no_storage)
    monkeypatch.setattr(runtime.store, "set_status", no_storage)
    await runtime.tick()
    assert runtime.status == "error"
    count = runtime.write_count
    await runtime.tick()
    assert runtime.write_count == count
    assert not runtime.adapter.connected
    assert "disk is full" in runtime.snapshot()["error"]
    assert runtime.events[-1]["kind"] == "error"
    assert runtime.events[-1]["details"]["persisted"] is False


async def test_csv_empty_snapshot_does_not_include_later_samples(runtime):
    await runtime.start(background=False)
    exported = csv_stream(runtime.store, runtime.run_id)
    await runtime.tick()
    assert len("".join(exported).splitlines()) == 1


async def test_pause_storage_failure_cancels_loop_and_cannot_resume(runtime, monkeypatch):
    await runtime.start()
    def no_status(*args, **kwargs):
        raise sqlite3.OperationalError("disk is full")
    monkeypatch.setattr(runtime.store, "set_status", no_status)
    with pytest.raises(ValueError, match="disk is full"):
        await runtime.pause()
    assert runtime.status == "error"
    assert runtime._task is None
    assert not runtime.adapter.connected
    with pytest.raises(RunConflict):
        await runtime.resume(background=False)


def test_corrupt_history_is_preserved_and_constructor_releases_lock(tmp_path):
    path = tmp_path / "history.sqlite3"
    original = b"This is a damaged SQLite database; preserve it."
    path.write_bytes(original)
    with pytest.raises(sqlite3.DatabaseError):
        Store(tmp_path)
    assert path.read_bytes() == original
    path.rename(tmp_path / "history.recovery.sqlite3")
    store = Store(tmp_path)
    store.close()


def test_project_filename_mismatch_cannot_replace_another_saved_project(tmp_path):
    store = Store(tmp_path)
    try:
        source = demo_project()
        store.save_project(source)
        path = store.projects_dir / "incorrect-id.json"
        path.write_text(source.model_dump_json(), encoding="utf-8")
        with pytest.raises(ValueError, match="identifiant interne"):
            store.load_project("incorrect-id")
        assert store.load_project(source.id) == source
    finally:
        store.close()
