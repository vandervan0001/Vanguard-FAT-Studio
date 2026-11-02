"""Adversarial process/PLC boundary cases derived independently of implementation."""

import copy
import struct

import pytest

from fat_studio.demo import demo_project
from fat_studio.engine import DemoController, ProcessEngine
from fat_studio.models import Equipment, Project, Tag, validate_project, validate_tag_value


def wire_float(value):
    return struct.unpack("!f", struct.pack("!f", value))[0]


def test_real_measurement_and_force_are_the_value_a_plc_receives():
    project = Project(id="real", name="REAL wire values", tags=[
        Tag(id="signal", name="Signal", direction="input", data_type="REAL",
            initial_value=16_777_217.0, writable=True),
    ])
    engine = ProcessEngine(project)
    assert engine.step({}, .1)["signal"] == wire_float(16_777_217.0)
    engine.force("signal", .1)
    assert engine.values["signal"] == wire_float(.1)
    engine.release("signal")
    assert engine.values["signal"] == wire_float(16_777_217.0)


def test_decimal_real_limit_accepts_its_wire_representation_but_not_next_float():
    tag = Tag(id="signal", name="Signal", direction="input", data_type="REAL",
              initial_value=0.0, min=-.1, max=.1, writable=True)
    assert validate_tag_value(tag, wire_float(.1)) == wire_float(.1)
    assert validate_tag_value(tag, wire_float(-.1)) == wire_float(-.1)
    with pytest.raises(ValueError):
        validate_tag_value(tag, .10000001)
    engine = ProcessEngine(Project(id="real", name="REAL bounds", tags=[tag]))
    engine.force("signal", .1)
    assert engine.qualities["signal"] == "forced"


@pytest.mark.parametrize("value", [2**63 - 1, -(2**63), 3.4028234663852886e38, -3.4028234663852886e38, 1e-45])
def test_real_boundary_quantization_matches_wire_for_finite_values(value):
    tag = Tag(id="signal", name="Signal", direction="input", data_type="REAL", initial_value=0., writable=True)
    assert validate_tag_value(tag, value) == wire_float(value)


@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"), -float("inf"), 3.402824e38, 10**400])
def test_real_quantization_never_accepts_boolean_or_nonfinite_storage(value):
    tag = Tag(id="signal", name="Signal", direction="input", data_type="REAL", initial_value=0., writable=True)
    with pytest.raises(ValueError, match="REAL fini"):
        validate_tag_value(tag, value)


def test_out_of_range_fault_must_remain_outside_the_real_wire_limits():
    project = demo_project()
    level = next(tag for tag in project.tags if tag.id == "level")
    level.max = 100.1
    engine = ProcessEngine(project)
    with pytest.raises(ValueError, match="hors des limites"):
        engine.set_fault("LT101", "out_of_range", 100.10000001)
    engine.set_fault("LT101", "out_of_range", 100.2)
    assert engine.qualities["level"] == "out_of_range"


@pytest.mark.parametrize("field", ["inflow_l_s", "outflow_l_s", "overflow_l"])
def test_sensor_initial_offset_is_validated_even_for_aggregate_or_cumulative_fields(field):
    project = demo_project()
    project.scenarios = []
    sensor = next(item for item in project.equipment if item.id == "LT101")
    sensor.params.update(source_field=field, scale=1., offset=40_000.)
    project.tags = [Tag(id=tag.id, name=tag.name, direction="input", data_type="INT",
                        initial_value=0, writable=True) if tag.id == "level" else tag
                    for tag in project.tags]
    result = validate_project(project)
    assert not result["valid"], "A project accepted for execution must not fail constructing its initial sensor image"
    engine = ProcessEngine(project)
    with pytest.raises(ValueError, match="Projet de simulation invalide"):
        engine.step({}, .1)


def test_aggregate_flow_range_is_validated_before_start():
    project = demo_project()
    project.scenarios = []
    sensor = next(item for item in project.equipment if item.id == "LT101")
    sensor.params.update(source_field="inflow_l_s", scale=2_000., offset=0.)
    project.tags = [Tag(id=tag.id, name=tag.name, direction="input", data_type="INT",
                        initial_value=0, writable=True) if tag.id == "level" else tag
                    for tag in project.tags]
    # The series inlet can deliver 25 L/s; 25 * 2,000 exceeds signed INT.
    assert not validate_project(project)["valid"]


def test_dynamic_sensor_overflow_does_not_commit_a_partial_process_step():
    project = outlet_project(initial=100.)
    project.equipment[1].params.update(role="inlet", max_flow_l_s=40_000.)
    project.equipment.append(Equipment(id="total", name="Overflow total", type="analog_sensor",
        params={"source_equipment": "tank", "source_field": "overflow_l"}, bindings={"value": "total"}))
    project.tags.append(Tag(id="total", name="Overflow total", direction="input", data_type="INT",
                            initial_value=0, writable=True))
    # Cumulative overflow is intentionally unbounded. The first failing cycle
    # must leave one coherent previous image, not a half-committed model.
    assert validate_project(project)["valid"]
    engine = ProcessEngine(project)
    before = copy.deepcopy((engine.equipment_state, engine.values, engine.qualities))
    with pytest.raises(ValueError, match="plage INT"):
        engine.step({"cmd": True}, 1.)
    assert engine.time_s == 0.
    assert (engine.equipment_state, engine.values, engine.qualities) == before


def outlet_project(initial=20.):
    return Project(id="drain", name="Outlet control", equipment=[
        Equipment(id="tank", name="Tank", type="tank",
                  params={"initial_level_pct": initial}, bindings={"level": "level"}),
        Equipment(id="pump", name="Drain", type="pump",
                  params={"tank_id": "tank", "role": "outlet", "response_s": 0.},
                  bindings={"command": "cmd"}),
    ], tags=[
        Tag(id="level", name="Level", direction="input", data_type="REAL", initial_value=initial, writable=True),
        Tag(id="cmd", name="Drain", direction="output", data_type="BOOL", initial_value=False),
    ])


def test_demo_outlet_level_control_drains_at_high_level_and_stops_at_low_level():
    project = outlet_project()
    engine, controller = ProcessEngine(project), DemoController(project)
    assert controller.read_commands(engine.values, .1)["cmd"] is False
    engine.force("level", 80.)
    assert controller.read_commands(engine.values, .1)["cmd"] is True
    engine.force("level", 50.)
    assert controller.read_commands(engine.values, .1)["cmd"] is True
    engine.force("level", 20.)
    assert controller.read_commands(engine.values, .1)["cmd"] is False


def test_demo_outlet_constant_command_stays_explicit_and_plant_has_no_controller():
    project = outlet_project()
    project.equipment[1].params.update(demo_control="constant", demo_command=True)
    engine, controller = ProcessEngine(project), DemoController(project)
    assert controller.read_commands(engine.values, .1)["cmd"] is True
    engine.step({"cmd": False}, 1.)
    assert engine.equipment_state["tank"]["volume_l"] == 200.
