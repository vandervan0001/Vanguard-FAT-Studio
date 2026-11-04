"""Observable FAT interactions, electrical conversion and evidence boundaries."""

import copy
import csv
import io
import json

import pytest
from fastapi.testclient import TestClient

from fat_studio.adapters.demo import DemoAdapter
from fat_studio.app import create_app
from fat_studio.mapping import LEGACY_FIELDS, export_mapping, import_mapping
from fat_studio.models import PreparedAction, SignalScaling, Tag, prepared_value, validate_project
from fat_studio.demo_lab import demo_lab_project
from fat_studio.reporting import html_report, json_stream
from fat_studio.runtime import RunConflict, Runtime
from fat_studio.security import MachinePolicy
from fat_studio.storage import Store


@pytest.fixture
def runtime(tmp_path):
    store = Store(tmp_path)
    runtime = Runtime(store, demo_lab_project(), MachinePolicy(tmp_path / "policy.json"))
    yield runtime
    store.close()


def raw_tag(**patch):
    data = dict(id="temperature", name="Temperature", direction="input", data_type="INT", initial_value=0,
                min=0.0, max=27648.0, writable=True, plc_address="%IW172",
                signal=dict(kind="4-20mA", raw_min=0.0, raw_max=27648.0,
                            engineering_min=10.0, engineering_max=30.0, engineering_unit="°C",
                            underflow_raw=-32768.0, overflow_raw=32767.0))
    data.update(patch)
    return Tag.model_validate(data)


@pytest.mark.parametrize("unit,value,expected", [("mA", 12, 13824), ("engineering", 12, 2765),
    ("engineering", 20, 13824), ("percent", 25, 6912), ("percent", 50, 13824), ("percent", 100, 27648),
    ("native", 172, 172), ("mA", 4, 0), ("mA", 20, 27648)])
def test_electrical_engineering_percent_and_native_address_same_signal(unit, value, expected):
    tag = raw_tag()
    assert prepared_value(tag, PreparedAction(target=tag.id, unit=unit, value=value)) == expected
    assert tag.plc_address == "%IW172"


@pytest.mark.parametrize("unit,value", [("mA", 24), ("mA", 0), ("engineering", 40), ("percent", -1),
    ("percent", 101), ("V", 5), ("native", 32767), ("native", 32768), ("native", True), ("mA", "12")])
def test_normal_stimuli_never_bypass_declared_or_storage_limits(unit, value):
    with pytest.raises(ValueError):
        prepared_value(raw_tag(), PreparedAction(target="temperature", unit=unit, value=value))


def test_explicit_diagnostics_use_profile_codes_without_oversized_int_or_silent_clamp():
    tag = raw_tag()
    assert prepared_value(tag, PreparedAction(target=tag.id, unit="mA", value=0, diagnostic=True)) == -32768
    assert prepared_value(tag, PreparedAction(target=tag.id, unit="mA", value=24, diagnostic=True)) == 32767
    # Another module can define a different broken-transmitter code.
    tag.signal.underflow_raw = 32767.0
    assert prepared_value(tag, PreparedAction(target=tag.id, unit="mA", value=0, diagnostic=True)) == 32767
    tag.signal.overflow_raw = None
    with pytest.raises(ValueError, match="plage INT"):
        prepared_value(tag, PreparedAction(target=tag.id, unit="mA", value=24, diagnostic=True))
    for value in (32768, -32769):
        with pytest.raises(ValueError):
            prepared_value(tag, PreparedAction(target=tag.id, value=value, diagnostic=True))


def test_signal_profile_validates_spans_and_diagnostic_storage():
    for patch in (dict(raw_min=2.0, raw_max=2.0), dict(engineering_min=30.0, engineering_max=10.0),
                  dict(engineering_min=-1e308, engineering_max=1e308)):
        with pytest.raises(ValueError):
            SignalScaling(kind="linear", **patch)
    data = raw_tag().model_dump()
    data["signal"]["overflow_raw"] = 40000
    with pytest.raises(ValueError):
        Tag.model_validate(data)
    with pytest.raises(ValueError):
        raw_tag(data_type="BOOL", initial_value=False)


def test_real_stimuli_remain_float32_and_voltage_profile_is_distinct():
    tag = raw_tag(data_type="REAL", initial_value=0.0)
    assert prepared_value(tag, PreparedAction(target=tag.id, unit="native", value=.1)) == 0.10000000149011612
    tag.signal.kind = "0-10V"
    assert prepared_value(tag, PreparedAction(target=tag.id, unit="V", value=5)) == 13824.0
    with pytest.raises(ValueError):
        prepared_value(tag, PreparedAction(target=tag.id, unit="mA", value=12))


@pytest.mark.parametrize("address", ["%I1.0", "%IW264", "%Q3.7", "%MD20", "%DB43.DBX1.2", "%DB43.DBW4", "%DB43.DBD8"])
def test_siemens_address_metadata_round_trips_without_becoming_a_node_id(address):
    project = demo_lab_project()
    project.tags[0].plc_address = address.lower()
    assert import_mapping(project, export_mapping(project)) == project
    assert project.tags[0].plc_address == address and project.tags[0].node_id == ""


def test_legacy_csv_without_new_columns_remains_importable():
    project = demo_lab_project()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=LEGACY_FIELDS)
    writer.writeheader()
    for tag in project.tags:
        row = {key: tag.model_dump()[key] for key in LEGACY_FIELDS}
        row["initial_value"] = json.dumps(row["initial_value"])
        row["writable"] = "true" if row["writable"] else "false"
        writer.writerow(row)
    imported = import_mapping(project, output.getvalue())
    assert len(imported.tags) == len(project.tags)
    assert all(tag.signal is None and tag.plc_address == "" for tag in imported.tags)


async def test_pulse_returns_without_a_browser_and_preserves_previous_maintained_contact(runtime):
    await runtime.start(background=False)
    await runtime.pulse("p101_request", True, 300)
    assert runtime.snapshot()["pulses"]["p101_request"]["expires_s"] == .3
    for _ in range(5):
        await runtime.tick()
    assert "p101_request" not in runtime.engine.forces and not runtime.engine.values["p101_request"]
    assert not runtime.pulses
    await runtime.force("stop_healthy", False)
    await runtime.pulse("stop_healthy", True)
    for _ in range(5):
        await runtime.tick()
    assert runtime.engine.forces["stop_healthy"] is False
    assert sum(event["kind"] == "pulse_release" for event in runtime.events) == 2
    await runtime.stop()


async def test_pulse_cannot_overwrite_a_later_operator_command_or_survive_pause(runtime):
    await runtime.start(background=False)
    await runtime.pulse("p101_request", True)
    await runtime.force("p101_request", False)
    for _ in range(5):
        await runtime.tick()
    assert runtime.engine.forces["p101_request"] is False
    await runtime.pulse("xv101_request", True)
    await runtime.pause()
    assert not runtime.pulses and "xv101_request" not in runtime.engine.forces
    with pytest.raises(RunConflict):
        await runtime.pulse("p101_request", True)
    await runtime.stop()


async def test_pulse_and_stimulus_never_write_plc_outputs(runtime):
    await runtime.start(background=False)
    for tag_id in ("p101_command", "lt201_percent"):
        with pytest.raises(ValueError):
            await runtime.pulse(tag_id, True)
        with pytest.raises(ValueError):
            await runtime.stimulus(tag_id, PreparedAction(target=tag_id, value=0, diagnostic=True))
    assert not runtime.engine.forces
    await runtime.stop()


async def test_guided_cycle_waits_for_operator_and_archives_five_observations(runtime):
    scenario = next(scenario for scenario in runtime.project.scenarios if scenario.execution_mode == "guided")
    await runtime.start(scenario.id, background=False)
    # There is no timed auto-completion or automatic triggering of a prepared input.
    runtime.engine.time_s = scenario.duration_s + 1
    await runtime.tick()
    assert runtime.status == "running" and not runtime.guided_results and not runtime.engine.forces
    for index, step in enumerate(scenario.fat_steps):
        await runtime.execute_fat_step(step.id)
        assert runtime.snapshot()["guided_steps"][-1]["state"] == "queued"
        with pytest.raises(RunConflict):
            await runtime.execute_fat_step(step.id)
        with pytest.raises(RunConflict):
            await runtime.observe_fat_step(step.id, "pass", "Trop tôt")
        for _ in range(5):
            await runtime.tick()
        assert runtime.guided_results[-1]["state"] == "applied"
        assert all(result["passed"] for result in runtime._guided_checks(step))
        await runtime.observe_fat_step(step.id, "pass", f"Observation explicite du testeur {index + 1}")
    assert runtime.scenario_state == "completed" and runtime.status == "paused"
    assert not runtime.connection["connected"] and not runtime.engine.forces
    report = runtime.store.run(runtime.run_id)
    assert report["result"]["verdict"] == "not_evaluated"
    observations = [event for event in report["events"] if event["kind"] == "fat_step_observed"]
    assert len(observations) == 5 and all(event["details"]["verdict"] == "pass" for event in observations)
    assert len(json.loads("".join(json_stream(runtime.store, runtime.run_id)))["scenario"]["fat_steps"]) == 5
    assert "Observation explicite du testeur 5" in html_report(runtime.store, runtime.run_id)
    assert "FAT pas à pas" in html_report(runtime.store, runtime.run_id)
    assert "Conforme saisi par le testeur" in html_report(runtime.store, runtime.run_id)
    # Requested-event records are immutable even when the active step advances.
    first_request = next(event for event in runtime.events if event["kind"] == "fat_step_requested")
    assert first_request["details"]["state"] == "queued"
    await runtime.stop()


async def test_guided_step_rejects_out_of_order_and_does_not_prejudge_failed_expectations(runtime):
    scenario = next(scenario for scenario in runtime.project.scenarios if scenario.execution_mode == "guided")
    await runtime.start(scenario.id, background=False)
    with pytest.raises(RunConflict):
        await runtime.execute_fat_step(scenario.fat_steps[1].id)
    await runtime.execute_fat_step(scenario.fat_steps[0].id)
    for _ in range(3):
        await runtime.tick()
    await runtime.force("lt101_raw", 0)
    for _ in range(3):
        await runtime.tick()
    with pytest.raises(RunConflict, match="écart"):
        await runtime.observe_fat_step(scenario.fat_steps[0].id, "pass", "")
    await runtime.observe_fat_step(scenario.fat_steps[0].id, "fail", "Écart de mesure explicitement constaté.")
    assert runtime.guided_results[0]["verdict"] == "fail"
    assert runtime.result["verdict"] == "not_evaluated"
    await runtime.stop()


async def test_prepared_group_is_validated_entirely_before_any_force(runtime):
    scenario = next(scenario for scenario in runtime.project.scenarios if scenario.execution_mode == "guided")
    await runtime.start(scenario.id, background=False)
    # Inject a corrupted in-memory plan after start to exercise the action boundary itself.
    runtime.scenario.fat_steps[0].actions[-1].value = 30
    before = copy.deepcopy(runtime.engine.values)
    with pytest.raises(ValueError):
        await runtime.execute_fat_step(scenario.fat_steps[0].id)
    assert runtime.engine.values == before and not runtime.engine.forces and not runtime.guided_results
    await runtime.stop()


class WriteFailure(DemoAdapter):
    async def write(self, inputs):
        raise ConnectionError("Deliberate write failure during a prepared step")


async def test_guided_step_is_not_applied_after_communication_error(runtime):
    runtime.adapter_factory = WriteFailure
    await runtime.start("demo-guided-io", background=False)
    await runtime.execute_fat_step("guided-initial")
    await runtime.tick()
    assert runtime.status == "error" and runtime.guided_results[-1]["state"] == "error"
    assert not any(event["kind"] == "fat_step_applied" for event in runtime.events)
    with pytest.raises(RunConflict):
        await runtime.observe_fat_step("guided-initial", "pass", "")
    writes = runtime.write_count
    await runtime.tick()
    assert runtime.write_count == writes
    await runtime.stop()


@pytest.mark.parametrize("operation", ["force", "release", "stimulus", "pulse", "fault", "clear_fault"])
async def test_prepared_step_cannot_be_overwritten_before_its_first_wire_exchange(runtime, operation):
    await runtime.start("demo-guided-io", background=False)
    await runtime.execute_fat_step("guided-initial")
    before = copy.deepcopy(runtime.engine.values)
    with pytest.raises(RunConflict, match="Attendre l'application"):
        if operation == "force":
            await runtime.force("lt101_raw", 0)
        elif operation == "release":
            await runtime.release("lt101_raw")
        elif operation == "stimulus":
            await runtime.stimulus("lt101_raw", PreparedAction(target="lt101_raw", value=4, unit="mA"))
        elif operation == "pulse":
            await runtime.pulse("p101_request", True)
        elif operation == "fault":
            await runtime.fault("LT101", "out_of_range", 30000)
        else:
            await runtime.clear_fault("LT101")
    assert runtime.engine.values == before and not runtime.engine.faults
    await runtime.tick()
    record = runtime.guided_results[0]
    assert record["state"] == "applied"
    level_action = next(action for action in record["actions"] if action["target"] == "lt101_raw")
    assert level_action["raw_value"] == level_action["actual_wire_value"] == 13824
    await runtime.stop()


async def test_proof_rejects_a_wire_image_that_did_not_apply_the_prepared_group(runtime):
    await runtime.start("demo-guided-io", background=False)
    await runtime.execute_fat_step("guided-initial")
    # Simulate an internal corruption not reachable through the guarded API.
    runtime.engine.force("lt101_raw", 0)
    await runtime.tick()
    assert runtime.status == "error" and runtime.guided_results[0]["state"] == "error"
    assert not any(event["kind"] == "fat_step_applied" for event in runtime.events)
    mismatch = next(event for event in runtime.events if event["kind"] == "fat_step_not_applied")
    assert mismatch["details"]["expected"] == 13824 and mismatch["details"]["actual_wire_value"] == 0
    await runtime.stop()


async def test_storage_error_cannot_leave_a_new_prepared_image_or_verdict(runtime, monkeypatch):
    await runtime.start("demo-guided-io", background=False)
    original_event = runtime.store.event

    def fail_requested(run_id, sim_time_s, kind, message, details):
        if kind == "fat_step_requested":
            raise OSError("Read-only evidence store")
        return original_event(run_id, sim_time_s, kind, message, details)

    monkeypatch.setattr(runtime.store, "event", fail_requested)
    with pytest.raises(OSError, match="Read-only"):
        await runtime.execute_fat_step("guided-initial")
    assert runtime.status == "error" and not runtime.engine.forces and not runtime.guided_results
    assert runtime.result["verdict"] == "not_evaluated"
    await runtime.stop()


async def test_diagnostic_stimulus_preserves_wire_bounds_and_is_traceable(runtime):
    await runtime.start(background=False)
    await runtime.stimulus("lt101_raw", PreparedAction(target="lt101_raw", unit="mA", value=24, diagnostic=True))
    assert runtime.engine.values["lt101_raw"] == 32767
    assert runtime.snapshot()["tags"]["lt101_raw"]["quality"] == "out_of_range"
    for _ in range(3):
        await runtime.tick()
    assert runtime.engine.values["lt101_percent"] > 100.0
    event = next(event for event in runtime.events if event["kind"] == "stimulus")
    assert event["details"]["value"] == 24 and event["details"]["raw_value"] == 32767
    assert event["details"]["diagnostic"] is True
    await runtime.release("lt101_raw")
    assert "lt101_raw" not in runtime.engine.forces
    await runtime.stop()


async def test_guided_diagnostic_can_check_the_intended_fault_value_without_claiming_good_process(runtime):
    project = demo_lab_project()
    scenario = project.scenarios[-1]
    scenario.fat_steps = scenario.fat_steps[:1]
    from fat_studio.models import PreparedCheck
    scenario.fat_steps[0].actions = [PreparedAction(target="lt101_raw", value=24, unit="mA", diagnostic=True)]
    scenario.fat_steps[0].checks = [PreparedCheck(target="lt101_raw", value=32767),
                                   PreparedCheck(target="lt101_percent", operator="gt", value=100.0)]
    runtime.set_project(project)
    await runtime.start(scenario.id, background=False)
    await runtime.execute_fat_step(scenario.fat_steps[0].id)
    for _ in range(3):
        await runtime.tick()
    results = runtime._guided_checks(scenario.fat_steps[0])
    assert results[0]["quality"] == "out_of_range" and all(result["passed"] for result in results)
    await runtime.observe_fat_step(scenario.fat_steps[0].id, "pass", "Parcours de test : diagnostic injecté et réaction contrôlée.")
    assert runtime.result["verdict"] == "not_evaluated"
    await runtime.stop()


def test_guided_metadata_references_and_duplicate_actions_are_validated():
    project = demo_lab_project()
    scenario = project.scenarios[-1]
    scenario.focus_equipment = ["missing"]
    scenario.trend_tags = ["missing"]
    scenario.fat_steps[0].actions.append(scenario.fat_steps[0].actions[0].model_copy())
    errors = validate_project(project)["errors"]
    assert any("focus_equipment" in error["path"] for error in errors)
    assert any("trend_tags" in error["path"] for error in errors)
    assert any("qu'une action" in error["message"] for error in errors)


def test_extreme_prepared_numbers_cannot_persist_an_unloadable_project(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        client.headers["X-FAT-Token"] = client.get("/api/session").json()["token"]
        original = client.get("/api/project").json()
        project = demo_lab_project().model_dump(mode="json")
        project["scenarios"][-1]["fat_steps"][0]["actions"][-1]["value"] = 10 ** 400
        response = client.post("/api/project/import", json=project)
        assert response.status_code == 422
        assert client.get("/api/project").json() == original
        assert client.get("/api/validate").status_code == 200
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as restarted:
        assert restarted.get("/api/project").json() == original
        assert restarted.get("/api/validate").json()["valid"]


def test_prepared_conversion_defensively_rejects_an_extreme_legacy_integer():
    action = PreparedAction.model_construct(target="temperature", unit="mA", value=10 ** 400, action="force", diagnostic=True)
    with pytest.raises(ValueError):
        prepared_value(raw_tag(), action)


def test_api_pulse_stimulus_and_guided_actions_enforce_run_context(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        client.headers["X-FAT-Token"] = client.get("/api/session").json()["token"]
        client.post("/api/pilot/load")
        project_response = client.get("/api/project")
        client.headers.update({"X-FAT-Project-ID": project_response.json()["id"],
                               "X-FAT-Project-Revision": project_response.headers["X-FAT-Project-Revision"]})
        state = client.post("/api/run/start", json={"scenario_id": "demo-guided-io"}).json()
        run_id = state["run_id"]
        client.headers["X-FAT-Run-ID"] = "stale-run"
        for endpoint, body in (("/api/force/pulse", {"tag_id": "p101_request", "value": True}),
                               ("/api/force/stimulus", {"tag_id": "lt101_raw", "value": 12, "unit": "mA"}),
                               ("/api/run/steps/guided-initial/execute", {})):
            assert client.post(endpoint, json=body).status_code == 409
        assert not client.get("/api/state").json()["guided_steps"]
        client.headers["X-FAT-Run-ID"] = run_id
        assert client.post("/api/force/pulse", json={"tag_id": "p101_request", "value": "true"}).status_code == 422
        assert client.post("/api/force/stimulus", json={"tag_id": "lt101_raw", "value": 24, "unit": "mA"}).status_code == 400
        assert client.post("/api/run/steps/guided-initial/execute", json={}).status_code == 200
        assert client.post("/api/run/stop").status_code == 200
