import copy

import pytest

from fat_studio.demo import demo_project
from fat_studio.engine import DemoController, ProcessEngine
from fat_studio.models import Equipment, Project, Tag, validate_project


def commands(engine, **updates):
    values = {tag.id: tag.initial_value for tag in engine.project.tags if tag.direction == "output"}
    values.update(updates)
    return values


def run_demo(engine, controller, seconds):
    for _ in range(round(seconds * 10)):
        engine.step(controller.read_commands(engine.values, 0.1), 0.1)


def instantaneous_demo():
    project = demo_project()
    for item in project.equipment:
        if "response_s" in item.params:
            item.params["response_s"] = 0.0
    return project


def test_example_is_valid_and_contains_every_catalogue_type():
    project = demo_project()
    assert validate_project(project)["valid"]
    assert {item.type for item in project.equipment} == {"tank", "pump", "valve_onoff", "valve_control", "analog_sensor", "digital_sensor", "indicator"}


def test_series_devices_limit_flow_instead_of_adding():
    engine = ProcessEngine(instantaneous_demo())
    engine.step(commands(engine, pump_cmd=True, inlet_cmd=True), 1.0)
    assert engine.values["volume"] == pytest.approx(275.0)
    assert engine.equipment_state["P101"]["flow_l_s"] == pytest.approx(25.0)
    assert engine.equipment_state["XV101"]["flow_l_s"] == pytest.approx(25.0)


def test_parallel_circuits_add_and_mass_balance_is_exact():
    project = instantaneous_demo()
    project.tags.append(Tag(id="pump2_cmd", name="P2", direction="output", data_type="BOOL", initial_value=False))
    project.equipment.append(Equipment(id="P102", type="pump", name="P-102", params={"tank_id": "TK101", "role": "inlet", "flow_group": "second_feed", "max_flow_l_s": 7.0, "response_s": 0.0}, bindings={"command": "pump2_cmd"}))
    engine = ProcessEngine(project)
    engine.step(commands(engine, pump_cmd=True, inlet_cmd=True, pump2_cmd=True, outlet_cmd=50.0), 1.0)
    assert engine.values["volume"] == pytest.approx(250 + 25 + 7 - 6)
    assert engine.equipment_state["TK101"]["inflow_l_s"] == 32.0
    assert engine.equipment_state["TK101"]["outflow_l_s"] == 6.0


def test_empty_tank_cannot_deliver_nonexistent_liquid():
    project = instantaneous_demo()
    project.equipment[0].params["initial_level_pct"] = 0.0
    engine = ProcessEngine(project)
    engine.step(commands(engine, outlet_cmd=100.0), 1.0)
    assert engine.values["volume"] == 0.0
    assert engine.equipment_state["FCV101"]["flow_l_s"] == 0.0
    assert engine.values["low"] is True


def test_overflow_is_accounted_instead_of_disappearing():
    project = instantaneous_demo()
    project.equipment[0].params["initial_level_pct"] = 99.0
    engine = ProcessEngine(project)
    engine.step(commands(engine, pump_cmd=True, inlet_cmd=True), 1.0)
    state = engine.equipment_state["TK101"]
    assert state["volume_l"] == 1000.0
    assert state["overflow_l"] == 15.0
    assert 990 + state["inflow_l_s"] == state["volume_l"] + state["overflow_l"]
    assert engine.values["high"] is True


def test_plant_never_invents_a_controller():
    engine = ProcessEngine(demo_project())
    for _ in range(100):
        engine.step(commands(engine), 0.1)
    assert engine.values["level"] == 25.0
    assert engine.values["pump_cmd"] is False
    assert engine.values["pump_running"] is False


@pytest.mark.parametrize("bad", [{}, {"pump_cmd": True}, {"pump_cmd": True, "inlet_cmd": True, "outlet_cmd": 0.0, "level": 90.0}, {"pump_cmd": 1, "inlet_cmd": True, "outlet_cmd": 0.0}, {"pump_cmd": True, "inlet_cmd": True, "outlet_cmd": 101.0}])
def test_bad_command_image_is_rejected_before_any_state_change(bad):
    engine = ProcessEngine(demo_project())
    state, values = copy.deepcopy(engine.equipment_state), dict(engine.values)
    with pytest.raises(ValueError):
        engine.step(bad, 0.1)
    assert engine.time_s == 0
    assert engine.equipment_state == state
    assert engine.values == values


@pytest.mark.parametrize("dt", [0, -0.1, 3, float("inf"), float("nan"), True])
def test_bad_time_step_is_rejected(dt):
    engine = ProcessEngine(demo_project())
    with pytest.raises(ValueError):
        engine.step(commands(engine), dt)


def test_force_has_limits_is_visible_and_only_changes_sensor_signal():
    engine = ProcessEngine(demo_project())
    controller = DemoController(engine.project)
    engine.force("level", 95.0)
    assert engine.equipment_state["TK101"]["level"] == 25.0
    assert engine.values["level"] == 95.0
    assert engine.qualities["level"] == "forced"
    assert controller.read_commands(engine.values, 0.1)["pump_cmd"] is False
    with pytest.raises(ValueError):
        engine.force("level", 101.0)
    with pytest.raises(ValueError):
        engine.force("pump_cmd", True)
    with pytest.raises(ValueError):
        engine.force("pump_running", 1)
    engine.release("level")
    assert engine.values["level"] == 25.0
    assert engine.qualities["level"] == "good"


def test_manual_input_release_restores_baseline():
    project = Project(id="manual", name="Manual", tags=[Tag(id="x", name="X", direction="input", data_type="INT", initial_value=7, writable=True, min=0, max=100)])
    engine = ProcessEngine(project)
    engine.force("x", 40)
    assert engine.step({}, 0.1)["x"] == 40
    engine.release("x")
    assert engine.values["x"] == 7


def test_motor_trip_cuts_flow_and_reports_fault():
    engine = ProcessEngine(instantaneous_demo())
    command = commands(engine, pump_cmd=True, inlet_cmd=True)
    engine.step(command, 0.1)
    volume = engine.values["volume"]
    engine.set_fault("P101", "motor_trip")
    engine.step(command, 0.1)
    assert engine.values["volume"] == volume
    assert engine.values["pump_fault"] is True
    assert engine.values["pump_running"] is False
    assert engine.equipment_state["P101"]["flow_l_s"] == 0
    engine.clear_fault("P101")
    engine.step(command, 0.1)
    assert engine.values["volume"] > volume
    assert engine.values["pump_fault"] is False


def test_sensor_freeze_holds_measurement_while_volume_changes():
    engine = ProcessEngine(instantaneous_demo())
    engine.set_fault("LT101", "sensor_stuck")
    engine.step(commands(engine, pump_cmd=True, inlet_cmd=True), 1.0)
    assert engine.values["level"] == 25.0
    assert engine.equipment_state["TK101"]["level"] == pytest.approx(27.5)
    assert engine.qualities["level"] == "fault"
    engine.clear_fault("LT101")
    assert engine.values["level"] == pytest.approx(27.5)


def test_out_of_range_is_explicit_and_preserves_wire_type():
    engine = ProcessEngine(demo_project())
    with pytest.raises(ValueError):
        engine.set_fault("LT101", "out_of_range", 90.0)
    with pytest.raises(ValueError):
        engine.set_fault("LT101", "out_of_range", float("nan"))
    engine.set_fault("LT101", "out_of_range", 125.0)
    assert engine.values["level"] == 125.0
    assert engine.qualities["level"] == "out_of_range"
    with pytest.raises(ValueError):
        engine.set_fault("LT101", "sensor_stuck")


def test_stuck_valve_blocks_series_pump_flow_despite_open_command():
    engine = ProcessEngine(instantaneous_demo())
    engine.set_fault("XV101", "valve_stuck", 0.0)
    engine.step(commands(engine, pump_cmd=True, inlet_cmd=True), 1.0)
    assert engine.values["volume"] == 250.0
    assert engine.values["inlet_closed"] is True
    assert engine.equipment_state["P101"]["flow_l_s"] == 0.0


def test_equal_percentage_has_explicit_tight_shutoff():
    project = instantaneous_demo()
    next(item for item in project.equipment if item.id == "FCV101").params["characteristic"] = "equal_percentage"
    engine = ProcessEngine(project)
    engine.step(commands(engine, outlet_cmd=0.0), 1.0)
    assert engine.equipment_state["FCV101"]["flow_l_s"] == 0.0
    engine.step(commands(engine, outlet_cmd=50.0), 1.0)
    assert engine.equipment_state["FCV101"]["flow_l_s"] == pytest.approx(12 * 50 ** -0.5)


def test_replay_is_exact_after_reset_including_faults_and_forces():
    engine = ProcessEngine(demo_project())
    controller = DemoController(engine.project)
    trajectory = []
    for _ in range(150):
        engine.step(controller.read_commands(engine.values, 0.1), 0.1)
        trajectory.append(dict(engine.values))
    engine.force("level", 90.0)
    engine.set_fault("P101", "motor_trip")
    engine.reset()
    controller.reset()
    assert not engine.forces and not engine.faults
    for expected in trajectory:
        engine.step(controller.read_commands(engine.values, 0.1), 0.1)
        assert engine.values == expected


def test_reference_cycle_reaches_hysteresis_stop():
    engine = ProcessEngine(demo_project())
    controller = DemoController(engine.project)
    run_demo(engine, controller, 10)
    assert engine.values["level"] > 35
    assert engine.values["pump_running"] is True
    run_demo(engine, controller, 15)
    assert engine.values["pump_cmd"] is False
    assert 60 < engine.values["level"] < 75


def test_incomplete_editor_document_does_not_crash_but_cannot_run():
    project = Project(id="new", name="Draft", equipment=[Equipment(id="P1", name="Pump", type="pump", params={"response_s": "invalid"})])
    engine = ProcessEngine(project)
    assert engine.equipment_state == {}
    with pytest.raises(ValueError):
        engine.step({}, 0.1)


def test_analog_int_sensor_rounds_without_breaking_wire_type():
    project = demo_project()
    level = next(tag for tag in project.tags if tag.id == "level")
    replacement = level.model_dump()
    replacement.update(data_type="INT", initial_value=25)
    project.tags = [Tag.model_validate(replacement) if tag.id == "level" else tag for tag in project.tags]
    project.scenarios = []  # Those reference scenarios deliberately contain REAL expectations.
    engine = ProcessEngine(project)
    engine.step(commands(engine, pump_cmd=True, inlet_cmd=True), 0.1)
    assert type(engine.values["level"]) is int
