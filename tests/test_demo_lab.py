"""Public passive demo and the bounded multi-tank material balance."""
import pytest

from fat_studio.demo_contract import DEMO_TAGS
from fat_studio.demo_lab import demo_lab_project
from fat_studio.engine import ProcessEngine
from fat_studio.models import Animation, validate_project
from fat_studio.runtime import Runtime
from fat_studio.security import MachinePolicy
from fat_studio.storage import Store


def test_public_demo_has_only_declared_manual_io_and_no_invented_addresses():
    project = demo_lab_project()
    assert validate_project(project)["valid"]
    assert len(project.tags) == len(DEMO_TAGS) == 75
    assert len(project.equipment) == 36
    assert len(project.scenarios) == 9
    assert all(not tag.node_id and not tag.plc_address for tag in project.tags)
    assert sum(item.type == "tank" for item in project.equipment) == 3
    assert sum(item.type == "pump_vfd" for item in project.equipment) == 4
    assert all(not tag.writable for tag in project.tags if tag.direction == "output")


@pytest.mark.parametrize("scenario_id", [scenario.id for scenario in demo_lab_project().scenarios if scenario.execution_mode == "timed"])
async def test_public_scenario_oracles_are_exercised_without_human_acceptance(tmp_path, scenario_id):
    store = Store(tmp_path)
    runtime = Runtime(store, demo_lab_project(), MachinePolicy(tmp_path / "policy.json"))
    try:
        await runtime.start(scenario_id, background=False)
        for _ in range(150):
            if runtime.status != "running":
                break
            await runtime.tick()
        assert runtime.scenario_state == "completed", runtime.error
        assert runtime.assertions and all(row["passed"] for row in runtime.assertions)
        assert runtime.result["verdict"] == "not_evaluated"
    finally:
        await runtime.close()
        store.close()


def test_transfer_conserves_volume_and_cannot_create_fluid_from_empty_source():
    project = demo_lab_project()
    engine = ProcessEngine(project)
    commands = {tag.id: tag.initial_value for tag in project.tags if tag.direction == "output"}
    commands.update(p201_command=True, p201_speed_command=100.0, xv201_command=True)
    initial = sum(engine.equipment_state[id]["volume_l"] for id in ("TK101", "TK201", "TK301"))
    for _ in range(400):
        engine.step(commands, .1)
        total = sum(engine.equipment_state[id]["volume_l"] + engine.equipment_state[id]["overflow_l"] for id in ("TK101", "TK201", "TK301"))
        assert total == pytest.approx(initial, abs=1e-8)
        assert all(engine.equipment_state[id]["volume_l"] >= 0 for id in ("TK101", "TK201", "TK301"))
    assert engine.equipment_state["TK101"]["volume_l"] == 0
    assert engine.equipment_state["P201"]["flow_l_s"] == 0


def test_visual_binding_is_validated_but_never_changes_physical_commands():
    project = demo_lab_project()
    pump = next(item for item in project.equipment if item.id == "P101")
    pump.animation = Animation(tag_id="p101_command", value=False, effect="rotate")
    assert validate_project(project)["valid"]
    engine = ProcessEngine(project)
    commands = {tag.id: tag.initial_value for tag in project.tags if tag.direction == "output"}
    engine.step(commands, .1)
    assert not engine.equipment_state["P101"]["running"]
    pump.animation.tag_id = "missing"
    assert not validate_project(project)["valid"]
    pump.animation = Animation(tag_id="p101_command", operator="gt", value=0.0)
    assert not validate_project(project)["valid"]


def test_transfer_source_conflicts_are_refused_before_communication():
    project = demo_lab_project()
    next(item for item in project.equipment if item.id == "XV201").params["source_tank_id"] = "TK301"
    assert any("plusieurs cuves" in row["message"] for row in validate_project(project)["errors"])
