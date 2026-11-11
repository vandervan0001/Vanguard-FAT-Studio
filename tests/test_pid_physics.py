"""Conservation and boundary tests for the explicitly selected FAT models."""

from copy import deepcopy
import math
import struct

import pytest

from fat_studio.catalog import parameters
from fat_studio.demo import demo_project
from fat_studio.engine import DemoController, ProcessEngine
from fat_studio.models import Connection, Equipment, Project, Tag, validate_project


def _tag(identifier, direction="input", data_type="REAL", initial=0.0):
    return Tag(id=identifier, name=identifier, direction=direction, data_type=data_type,
               initial_value=initial, writable=direction == "input",
               **({"min": -1e9, "max": 1e9} if data_type == "REAL" else {}))


def heat_project(**params):
    ports = ("primary_temperature", "secondary_temperature", "heat", "primary_flow", "secondary_flow")
    return Project(id="heat_lab", name="Thermal boundaries", equipment=[Equipment(
        id="HX", name="HX", type="heat_exchanger", params=params,
        bindings={port: port for port in ports},
    )], tags=[_tag(port) for port in ports])


def valve_project(mode="diverting", position=25.0, common=100.0, a=0.0, b=0.0):
    tanks = [Equipment(id=identifier, name=identifier, type="tank", params={"capacity_l": 100.0, "initial_level_pct": initial})
             for identifier, initial in (("common", common), ("a", a), ("b", b))]
    ports = {"position": "position", "flow_a": "flow_a", "flow_b": "flow_b", "feedback_a": "feedback_a", "feedback_b": "feedback_b"}
    valve = Equipment(id="V3", name="V3", type="valve_three_way", params={
        "mode": mode, "common_tank_id": "common", "branch_a_tank_id": "a", "branch_b_tank_id": "b",
        "max_flow_l_s": 20.0, "response_s": 0.0, "initial_position_pct": position,
    }, bindings={"command": "command", **ports})
    tags = [_tag("command", "output", initial=position)] + [_tag(port) for port in ("position", "flow_a", "flow_b")]
    tags += [_tag(port, data_type="BOOL", initial=False) for port in ("feedback_a", "feedback_b")]
    return Project(id="three_way_lab", name="Three declared tanks", equipment=[*tanks, valve], tags=tags)


def _commands(engine, **updates):
    return {**{tag.id: tag.initial_value for tag in engine.project.tags if tag.direction == "output"}, **updates}


def _valid_engine(project):
    validation = validate_project(project)
    assert validation["valid"], validation["errors"]
    return ProcessEngine(project)


def _stock(engine):
    return sum(state.get("volume_l", 0) + state.get("overflow_l", 0) for state in engine.equipment_state.values())


def test_coupled_heat_step_satisfies_each_energy_equation_including_storage():
    engine = _valid_engine(heat_project(primary_volume_l=10.0, secondary_volume_l=20.0,
        primary_density_kg_l=2.0, secondary_density_kg_l=0.5, primary_cp_kj_kg_k=3.0, secondary_cp_kj_kg_k=4.0,
        primary_flow_l_s=1.0, secondary_flow_l_s=2.0, primary_inlet_temperature_c=100.0,
        secondary_inlet_temperature_c=10.0, ua_kw_k=5.0))
    old = dict(engine.equipment_state["HX"])
    engine.step({}, 2.0)
    state = engine.equipment_state["HX"]
    tp, ts, heat = state["primary_outlet_temperature_c"], state["secondary_outlet_temperature_c"], state["heat_kw"]
    assert 60 * (tp - old["primary_outlet_temperature_c"]) / 2 == pytest.approx(6 * (100 - tp) - heat)
    assert 40 * (ts - old["secondary_outlet_temperature_c"]) / 2 == pytest.approx(4 * (10 - ts) + heat)
    assert heat == pytest.approx(5 * (tp - ts))
    assert 60 * (tp - 80) + 40 * (ts - 20) == pytest.approx(2 * (6 * (100 - tp) + 4 * (10 - ts)))


def test_closed_zero_flow_exchanger_uses_stored_energy_without_creating_heat():
    engine = _valid_engine(heat_project(primary_volume_l=10.0, secondary_volume_l=20.0,
        primary_cp_kj_kg_k=1.0, secondary_cp_kj_kg_k=1.0, primary_flow_l_s=0.0, secondary_flow_l_s=0.0, ua_kw_k=4.0))
    expected_difference = 60 / (1 + 2 * 4 * (1 / 10 + 1 / 20))
    engine.step({}, 2.0)
    state = engine.equipment_state["HX"]
    assert state["primary_outlet_temperature_c"] == pytest.approx(40 + 20 / 30 * expected_difference)
    assert state["secondary_outlet_temperature_c"] == pytest.approx(40 - 10 / 30 * expected_difference)
    for _ in range(100):
        engine.step({}, 2.0)
    state = engine.equipment_state["HX"]
    assert 10 * state["primary_outlet_temperature_c"] + 20 * state["secondary_outlet_temperature_c"] == pytest.approx(1200)
    assert state["primary_outlet_temperature_c"] == pytest.approx(40)
    assert state["secondary_outlet_temperature_c"] == pytest.approx(40)


@pytest.mark.parametrize("loss", [0.0, 50.0, 100.0])
def test_fouling_reduces_only_declared_ua_and_preserves_energy(loss):
    engine = _valid_engine(heat_project(primary_flow_l_s=0.0, secondary_flow_l_s=0.0))
    engine.set_fault("HX", "fouling", loss)
    assert engine.time_s == 0
    assert engine.equipment_state["HX"]["ua_effective_kw_k"] == 5 * (1 - loss / 100)
    assert engine.equipment_state["HX"]["fouled"] is (loss > 0)
    engine.step({}, 1.0)
    state = engine.equipment_state["HX"]
    assert state["primary_outlet_temperature_c"] + state["secondary_outlet_temperature_c"] == pytest.approx(100)
    if loss == 100:
        assert state["primary_outlet_temperature_c"] == pytest.approx(80)
        assert state["secondary_outlet_temperature_c"] == pytest.approx(20)
        assert state["heat_kw"] == 0
    engine.clear_fault("HX", "fouling")
    assert engine.equipment_state["HX"]["ua_effective_kw_k"] == 5
    assert engine.equipment_state["HX"]["fouled"] is False


@pytest.mark.parametrize("invalid", [None, -0.1, 100.1, True, "50", float("nan"), float("inf")])
def test_invalid_fouling_is_rejected_without_changing_state(invalid):
    engine = _valid_engine(heat_project())
    before = deepcopy(engine.equipment_state)
    with pytest.raises(ValueError):
        engine.set_fault("HX", "fouling", invalid)
    assert engine.faults == {} and engine.equipment_state == before and engine.time_s == 0


def test_heat_can_flow_from_secondary_to_primary():
    engine = _valid_engine(heat_project(initial_primary_temperature_c=20.0, initial_secondary_temperature_c=80.0,
        primary_inlet_temperature_c=20.0, secondary_inlet_temperature_c=80.0))
    assert engine.equipment_state["HX"]["heat_kw"] == -300
    engine.step({}, 2.0)
    state = engine.equipment_state["HX"]
    assert state["heat_kw"] < 0
    assert 20 < state["primary_outlet_temperature_c"] < state["secondary_outlet_temperature_c"] < 80


def test_zero_ua_keeps_circuits_independent_with_backward_euler_flush():
    engine = _valid_engine(heat_project(ua_kw_k=0.0, primary_volume_l=10.0, secondary_volume_l=20.0,
        primary_flow_l_s=5.0, secondary_flow_l_s=0.0, primary_inlet_temperature_c=100.0))
    engine.step({}, 2.0)
    state = engine.equipment_state["HX"]
    assert state["primary_outlet_temperature_c"] == pytest.approx((10 * 80 + 2 * 5 * 100) / (10 + 2 * 5))
    assert state["secondary_outlet_temperature_c"] == 20
    assert state["heat_kw"] == 0


@pytest.mark.parametrize("dt", [1e-300, 0.1, 2.0])
def test_extreme_valid_thermal_coefficients_are_stable_and_bounded(dt):
    engine = _valid_engine(heat_project(primary_volume_l=0.001, secondary_volume_l=0.001,
        primary_density_kg_l=0.01, secondary_density_kg_l=0.01, primary_cp_kj_kg_k=0.01, secondary_cp_kj_kg_k=0.01,
        primary_flow_l_s=0.0, secondary_flow_l_s=0.0, ua_kw_k=1e6,
        initial_primary_temperature_c=500.0, initial_secondary_temperature_c=-100.0))
    engine.step({}, dt)
    state = engine.equipment_state["HX"]
    assert all(math.isfinite(value) for value in state.values() if isinstance(value, (int, float)))
    assert -100 - 1e-9 <= state["secondary_outlet_temperature_c"] <= state["primary_outlet_temperature_c"] <= 500 + 1e-9
    assert state["primary_outlet_temperature_c"] + state["secondary_outlet_temperature_c"] == pytest.approx(400)


@pytest.mark.parametrize("side", ["primary", "secondary"])
@pytest.mark.parametrize("quantity,valid,invalid", [("flow", 0.0, -1.0), ("flow", 100000.0, 100001.0),
                                                     ("inlet", -100.0, -101.0), ("inlet", 500.0, 501.0)])
def test_all_runtime_boundary_commands_override_constants_and_reject_outside_domain_atomically(side, quantity, valid, invalid):
    project = heat_project()
    project.tags.append(_tag("boundary", "output", initial=valid))
    project.equipment[0].bindings[f"{side}_{quantity}_command"] = "boundary"
    engine = _valid_engine(project)
    engine.step({"boundary": valid}, 0.1)
    state = engine.equipment_state["HX"]
    assert state[f"{side}_" + ("flow_l_s" if quantity == "flow" else "inlet_temperature_c")] == valid
    before = deepcopy((engine.values, engine._raw_values, engine.qualities, engine.equipment_state, engine.time_s))
    with pytest.raises(ValueError, match="échangeur"):
        engine.step({"boundary": invalid}, 0.1)
    assert (engine.values, engine._raw_values, engine.qualities, engine.equipment_state, engine.time_s) == before


def test_thermal_signals_are_float32_while_internal_temperature_retains_double_precision():
    engine = _valid_engine(heat_project())
    engine.step({}, 0.123456789)
    state = engine.equipment_state["HX"]
    for port, field in (("primary_temperature", "primary_outlet_temperature_c"),
                        ("secondary_temperature", "secondary_outlet_temperature_c"), ("heat", "heat_kw")):
        wire = struct.unpack("!f", struct.pack("!f", state[field]))[0]
        assert engine.values[port] == wire
    assert engine.values["primary_temperature"] != state["primary_outlet_temperature_c"]


@pytest.mark.parametrize("position,flow_a,flow_b", [(0.0, 0.0, 20.0), (25.0, 5.0, 15.0), (100.0, 20.0, 0.0)])
def test_diverting_valve_preserves_total_volume_and_complementary_branch_flows(position, flow_a, flow_b):
    engine = _valid_engine(valve_project(position=position))
    engine.step({"command": position}, 1.0)
    state = engine.equipment_state["V3"]
    assert state["flow_a_l_s"] == pytest.approx(flow_a) and state["flow_b_l_s"] == pytest.approx(flow_b)
    assert state["flow_l_s"] == pytest.approx(flow_a + flow_b)
    assert engine.equipment_state["common"]["volume_l"] == pytest.approx(80)
    assert engine.equipment_state["a"]["volume_l"] == pytest.approx(flow_a)
    assert engine.equipment_state["b"]["volume_l"] == pytest.approx(flow_b)
    assert state["to_a"] is (position == 100) and state["to_b"] is (position == 0)
    assert _stock(engine) == pytest.approx(100)


def test_mixing_valve_does_not_invent_missing_branch_supply_or_redistribute_it():
    engine = _valid_engine(valve_project(mode="mixing", common=0.0, a=2.0, b=100.0))
    engine.step({"command": 25.0}, 1.0)
    state = engine.equipment_state["V3"]
    assert state["flow_a_l_s"] == 2 and state["flow_b_l_s"] == 15 and state["flow_l_s"] == 17
    assert engine.equipment_state["a"]["volume_l"] == 0
    assert engine.equipment_state["b"]["volume_l"] == 85
    assert engine.equipment_state["common"]["volume_l"] == 17
    assert _stock(engine) == pytest.approx(102)


def test_empty_diverter_source_has_zero_flow_and_partial_stock_is_shared_proportionally():
    engine = _valid_engine(valve_project(common=5.0))
    engine.step({"command": 25.0}, 1.0)
    state = engine.equipment_state["V3"]
    assert state["flow_a_l_s"] == 1.25 and state["flow_b_l_s"] == 3.75
    engine.step({"command": 25.0}, 1.0)
    assert state is not engine.equipment_state["V3"]
    assert engine.equipment_state["V3"]["flow_l_s"] == 0
    assert _stock(engine) == 5


def _add_pump(project, source="common", target="a", rate=20.0):
    project.equipment.append(Equipment(id="pump", name="pump", type="pump", params={
        "tank_id": target, "source_tank_id": source, "role": "inlet", "flow_group": "pump_route",
        "max_flow_l_s": rate, "response_s": 0.0,
    }, bindings={"command": "pump_command"}))
    project.tags.append(_tag("pump_command", "output", "BOOL", True))


def test_legacy_transfer_and_three_way_compete_for_one_source_independent_of_order():
    project = valve_project(position=50.0, common=5.0)
    _add_pump(project)
    first = _valid_engine(project)
    reordered = project.model_copy(deep=True)
    reordered.equipment.reverse()
    second = _valid_engine(reordered)
    first.step(_commands(first), 1.0)
    second.step(_commands(second), 1.0)
    assert first.equipment_state == second.equipment_state
    assert first.equipment_state["pump"]["flow_l_s"] == 2.5
    assert first.equipment_state["V3"]["flow_a_l_s"] == 1.25
    assert first.equipment_state["V3"]["flow_b_l_s"] == 1.25
    assert first.equipment_state["a"]["volume_l"] == 3.75
    assert first.equipment_state["b"]["volume_l"] == 1.25
    assert _stock(first) == 5


def test_multiple_three_way_valves_share_depleted_source_without_overdrawing_it():
    project = valve_project(common=5.0)
    second = project.equipment[-1].model_copy(deep=True)
    second.id, second.name, second.bindings = "V4", "V4", {"command": "command_2"}
    project.equipment.append(second)
    project.tags.append(_tag("command_2", "output", initial=75.0))
    engine = _valid_engine(project)
    engine.step(_commands(engine), 1.0)
    assert engine.equipment_state["V3"]["flow_l_s"] == 2.5
    assert engine.equipment_state["V4"]["flow_l_s"] == 2.5
    assert engine.equipment_state["a"]["volume_l"] == 2.5
    assert engine.equipment_state["b"]["volume_l"] == 2.5
    assert engine.equipment_state["common"]["volume_l"] == 0
    assert _stock(engine) == 5


def test_three_way_destination_overflow_remains_in_explicit_mass_balance():
    engine = _valid_engine(valve_project(position=100.0, a=95.0))
    engine.step(_commands(engine), 1.0)
    assert engine.equipment_state["a"]["volume_l"] == 100
    assert engine.equipment_state["a"]["overflow_l"] == 15
    assert engine.equipment_state["common"]["volume_l"] == 80
    assert _stock(engine) == 195


def test_incoming_transferred_water_is_unavailable_until_following_cycle():
    project = valve_project(common=0.0, a=100.0)
    _add_pump(project, source="a", target="common", rate=4.0)
    engine = _valid_engine(project)
    engine.step(_commands(engine), 1.0)
    assert engine.equipment_state["common"]["volume_l"] == 4
    assert engine.equipment_state["V3"]["flow_l_s"] == 0
    engine.step(_commands(engine), 1.0)
    assert engine.equipment_state["V3"]["flow_l_s"] == 4
    assert engine.equipment_state["common"]["volume_l"] == 4
    assert _stock(engine) == 100


def test_external_supply_can_be_allocated_same_cycle_without_creating_volume():
    project = valve_project(common=0.0)
    _add_pump(project, source="", target="common", rate=4.0)
    engine = _valid_engine(project)
    engine.step(_commands(engine), 1.0)
    assert engine.equipment_state["V3"]["flow_l_s"] == 4
    assert engine.equipment_state["common"]["volume_l"] == 0
    assert _stock(engine) == 4


def test_three_way_stuck_fault_freezes_position_then_clear_restores_response():
    project = valve_project(position=25.0)
    project.equipment[-1].params["response_s"] = 1.0
    engine = _valid_engine(project)
    engine.set_fault("V3", "valve_stuck")
    engine.step({"command": 100.0}, 0.5)
    assert engine.equipment_state["V3"]["position"] == 25
    assert engine.equipment_state["V3"]["stuck"] is True
    engine.clear_fault("V3")
    engine.step({"command": 100.0}, 0.5)
    assert engine.equipment_state["V3"]["position"] == pytest.approx(100 - 75 * math.exp(-0.5))
    assert engine.equipment_state["V3"]["stuck"] is False


@pytest.mark.parametrize("field,expected", [("flow_l_s", 5.0), ("flow_a_l_s", 1.25), ("flow_b_l_s", 3.75)])
def test_heat_exchanger_reads_allocated_three_way_flow_same_cycle_independent_of_order(field, expected):
    project = valve_project(common=5.0)
    heat = heat_project(primary_flow_equipment="V3", primary_flow_field=field, primary_flow_l_s=99.0)
    project.equipment = [*heat.equipment, *project.equipment]
    project.tags.extend(heat.tags)
    engine = _valid_engine(project)
    assert engine.equipment_state["HX"]["primary_flow_l_s"] == 0
    engine.step(_commands(engine), 1.0)
    assert engine.equipment_state["HX"]["primary_flow_l_s"] == expected
    engine.step(_commands(engine), 1.0)
    assert engine.equipment_state["HX"]["primary_flow_l_s"] == 0


def test_graphical_connection_does_not_override_declared_thermal_flow():
    project = valve_project(common=0.0)
    heat = heat_project(secondary_flow_l_s=2.0)
    project.equipment.extend(heat.equipment)
    project.tags.extend(heat.tags)
    project.connections = [Connection(id="drawing", source="V3", target="HX", source_port="A", target_port="secondary_in")]
    engine = _valid_engine(project)
    engine.step(_commands(engine), 1.0)
    assert engine.equipment_state["V3"]["flow_a_l_s"] == 0
    assert engine.equipment_state["HX"]["secondary_flow_l_s"] == 2


@pytest.mark.parametrize("kind", ["pump", "pump_vfd", "valve_onoff", "valve_control"])
def test_heat_exchanger_reads_each_supported_legacy_source_after_depletion(kind):
    project = valve_project(common=5.0)
    project.equipment = project.equipment[:3]
    project.tags = [_tag("source_command", "output", "REAL" if kind == "valve_control" else "BOOL",
                         100.0 if kind == "valve_control" else True)]
    bindings = {"command": "source_command"}
    if kind == "pump_vfd":
        project.tags.append(_tag("source_speed", "output", initial=100.0))
        bindings["speed_command"] = "source_speed"
    project.equipment.append(Equipment(id="source", name="source", type=kind, params={
        "tank_id": "a", "source_tank_id": "common", "role": "inlet", "flow_group": "source",
        "max_flow_l_s": 20.0, "response_s": 0.0,
    }, bindings=bindings))
    heat = heat_project(secondary_flow_equipment="source", secondary_flow_l_s=99.0)
    project.equipment = [*heat.equipment, *project.equipment]
    project.tags.extend(heat.tags)
    engine = _valid_engine(project)
    engine.step(_commands(engine), 1.0)
    assert engine.equipment_state["HX"]["secondary_flow_l_s"] == 5
    engine.step(_commands(engine), 1.0)
    assert engine.equipment_state["HX"]["secondary_flow_l_s"] == 0


def test_invalid_heat_boundary_rolls_back_already_staged_volume_and_valve_changes():
    project = valve_project()
    heat = heat_project()
    heat.equipment[0].bindings["primary_flow_command"] = "bad_flow"
    project.equipment.extend(heat.equipment)
    project.tags.extend([*heat.tags, _tag("bad_flow", "output", initial=2.0)])
    engine = _valid_engine(project)
    before = deepcopy((engine.equipment_state, engine.values, engine.qualities, engine.time_s))
    with pytest.raises(ValueError, match="échangeur"):
        engine.step(_commands(engine, command=100.0, bad_flow=-1.0), 1.0)
    assert (engine.equipment_state, engine.values, engine.qualities, engine.time_s) == before


def test_reset_restores_both_models_and_replay_is_deterministic():
    project = valve_project()
    heat = heat_project(primary_flow_equipment="V3", primary_flow_field="flow_a_l_s")
    project.equipment.extend(heat.equipment)
    project.tags.extend(heat.tags)
    engine = _valid_engine(project)
    initial = deepcopy((engine.equipment_state, engine.values))
    for _ in range(4):
        engine.step(_commands(engine), 0.25)
    expected = deepcopy((engine.equipment_state, engine.values))
    engine.set_fault("HX", "fouling", 90.0)
    engine.set_fault("V3", "valve_stuck", 100.0)
    engine.reset()
    assert (engine.equipment_state, engine.values) == initial
    assert engine.faults == {} and engine.forces == {} and engine.time_s == 0
    for _ in range(4):
        engine.step(_commands(engine), 0.25)
    assert (engine.equipment_state, engine.values) == expected


def test_demo_three_way_uses_explicit_manual_request_or_declared_constant():
    project = valve_project()
    project.equipment[-1].params["demo_command"] = 73.0
    controller = DemoController(project)
    assert controller.read_commands({}, 0.1)["command"] == 73
    project.equipment[-1].bindings["manual_request"] = "manual"
    project.tags.append(_tag("manual", initial=11.0))
    controller = DemoController(project)
    assert controller.read_commands({"manual": 33.0}, 0.1)["command"] == 33
    assert controller.read_commands({}, 0.1)["command"] == 73


def test_new_models_and_documentary_symbol_do_not_change_unrelated_legacy_demo():
    baseline = demo_project()
    project = baseline.model_copy(deep=True)
    heat = heat_project()
    project.equipment.extend([*heat.equipment, Equipment(id="doc", name="doc", type="pid_symbol", symbol_kind="three_way_valve")])
    project.tags.extend(heat.tags)
    first, second = _valid_engine(baseline), _valid_engine(project)
    commands = DemoController(baseline).read_commands(first.values, 0.1)
    first.step(commands, 0.1)
    second.step(commands, 0.1)
    assert {key: value for key, value in second.values.items() if key in first.values} == first.values
    assert all(second.equipment_state[item.id] == first.equipment_state[item.id] for item in baseline.equipment)
    assert second.equipment_state["doc"] == {"documentary": True, "quality": "not_simulated"}


def test_heat_model_constants_are_read_without_mutating_project_params():
    project = heat_project()
    before = project.model_dump_json()
    engine = _valid_engine(project)
    engine.step({}, 1.0)
    assert parameters(project.equipment[0])["primary_cp_kj_kg_k"] == 4.18
    assert project.model_dump_json() == before
