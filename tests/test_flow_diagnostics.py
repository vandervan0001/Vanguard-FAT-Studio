import copy

import pytest

from fat_studio.demo import demo_project
from fat_studio.engine import ProcessEngine
from fat_studio.models import Equipment, Tag


def fixture():
    project = demo_project()
    for item in project.equipment:
        if "response_s" in item.params:
            item.params["response_s"] = 0.0
    return project


def commands(engine, **changes):
    return {**{tag.id: tag.initial_value for tag in engine.project.tags if tag.direction == "output"}, **changes}


def test_series_diagnostic_exposes_actual_minimum_and_received_commands():
    engine = ProcessEngine(fixture())
    engine.step(commands(engine, pump_cmd=True, inlet_cmd=True), 1.0)
    pump = engine.equipment_state["P101"]["flow_diagnostic"]
    valve = engine.equipment_state["XV101"]["flow_diagnostic"]
    assert pump["actual_flow_l_s"] == valve["actual_flow_l_s"] == 25
    assert pump["requested_flow_l_s"] == 25
    assert pump["limiting_equipment_ids"] == ["XV101"]
    assert pump["command"] is True and pump["actual_pct"] == 100
    assert valve["available_flow_l_s"] == 25 and pump["available_flow_l_s"] == 30
    assert pump["calculated_at_s"] == engine.time_s == 1
    assert pump["source_volume_l"] is None and pump["source_factor"] == 1
    assert engine.equipment_state["TK101"]["volume_l"] == 275


def test_closed_valve_and_motor_trip_are_distinct_facts_and_fault_changes_invalidate():
    engine = ProcessEngine(fixture())
    command = commands(engine, pump_cmd=True, inlet_cmd=False)
    engine.step(command, 1.0)
    valve = engine.equipment_state["XV101"]["flow_diagnostic"]
    assert set(valve["reasons"]) == {"command_off", "valve_closed"}
    assert valve["limiting_equipment_ids"] == ["XV101"]
    engine.set_fault("P101", "motor_trip")
    assert all("flow_diagnostic" not in state for state in engine.equipment_state.values())
    engine.step(commands(engine, pump_cmd=True, inlet_cmd=True), 1.0)
    assert engine.equipment_state["P101"]["flow_diagnostic"]["reasons"] == ["motor_trip"]
    assert engine.equipment_state["P101"]["flow_diagnostic"]["actual_flow_l_s"] == 0
    engine.clear_fault("P101")
    assert all("flow_diagnostic" not in state for state in engine.equipment_state.values())


def test_source_stock_and_external_supply_are_start_of_cycle_facts():
    project = fixture()
    project.equipment[0].params["initial_level_pct"] = 0
    engine = ProcessEngine(project)
    engine.step(commands(engine, outlet_cmd=100.0), 1.0)
    fact = engine.equipment_state["FCV101"]["flow_diagnostic"]
    assert fact["source_tank_id"] == "TK101"
    assert fact["source_volume_l"] == fact["external_supply_l"] == fact["source_factor"] == 0
    assert fact["requested_flow_l_s"] == 12 and fact["actual_flow_l_s"] == 0
    engine.step(commands(engine, pump_cmd=True, inlet_cmd=True, outlet_cmd=100.0), 1.0)
    fact = engine.equipment_state["FCV101"]["flow_diagnostic"]
    assert fact["source_volume_l"] == 0 and fact["external_supply_l"] == 25
    assert fact["source_factor"] == 1 and fact["actual_flow_l_s"] == 12
    assert engine.equipment_state["TK101"]["volume_l"] == 13


def test_transfer_diagnostic_matches_limited_volume_without_creating_liquid():
    project = fixture()
    project.equipment.append(Equipment(id="TK102", name="Source", type="tank", params={"capacity_l": 100.0, "initial_level_pct": 5.0}))
    for item in project.equipment:
        if item.id in ("P101", "XV101"):
            item.params["source_tank_id"] = "TK102"
    engine = ProcessEngine(project)
    engine.step(commands(engine, pump_cmd=True, inlet_cmd=True), 1.0)
    fact = engine.equipment_state["P101"]["flow_diagnostic"]
    assert fact["source_tank_id"] == "TK102" and fact["source_volume_l"] == 5
    assert fact["source_factor"] == pytest.approx(.2) and fact["actual_flow_l_s"] == 5
    assert engine.equipment_state["TK101"]["volume_l"] == 255
    assert engine.equipment_state["TK102"]["volume_l"] == 0


def test_vfd_setpoint_and_response_are_reported_without_inventing_interlock():
    project = fixture()
    project.tags.append(Tag(id="speed_cmd", name="Speed", direction="output", data_type="REAL", initial_value=0.0))
    pump = next(item for item in project.equipment if item.id == "P101")
    pump.type = "pump_vfd"
    pump.bindings["speed_command"] = "speed_cmd"
    pump.params["response_s"] = 1.0
    engine = ProcessEngine(project)
    engine.step(commands(engine, pump_cmd=True, inlet_cmd=True, speed_cmd=50.0), .1)
    fact = engine.equipment_state["P101"]["flow_diagnostic"]
    assert set(fact["reasons"]) == {"speed_setpoint", "response_pending"}
    assert fact["target_pct"] == 50 and 0 < fact["actual_pct"] < 50
    assert fact["available_flow_l_s"] == pytest.approx(30 * fact["actual_pct"] / 100)


def test_failed_cycle_and_reset_never_publish_new_diagnostic():
    engine = ProcessEngine(fixture())
    engine.step(commands(engine, pump_cmd=True, inlet_cmd=True), .1)
    previous = copy.deepcopy(engine.equipment_state)
    with pytest.raises(ValueError):
        engine.step({}, .1)
    assert engine.equipment_state == previous
    engine.reset()
    assert all("flow_diagnostic" not in state for state in engine.equipment_state.values())
