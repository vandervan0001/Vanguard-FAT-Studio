"""Validation at the boundary between drawings, physical states and PLC values."""

import pytest

from fat_studio.models import Equipment, Project, Tag, validate_fault, validate_project


def thermal_project():
    return Project(id="thermal", name="Thermal boundary validation", equipment=[
        Equipment(id="HX", type="heat_exchanger", name="HX"),
    ], tags=[Tag(id="manual", name="Manual", direction="input", data_type="BOOL", initial_value=False, writable=True)])


def three_way_project():
    project = thermal_project()
    project.equipment.extend([Equipment(id=identifier, name=identifier, type="tank") for identifier in ("AB", "A", "B")])
    project.tags.append(Tag(id="position", name="Position command", direction="output", data_type="REAL", initial_value=50.0))
    project.equipment.append(Equipment(id="V3", name="V3", type="valve_three_way", params={
        "common_tank_id": "AB", "branch_a_tank_id": "A", "branch_b_tank_id": "B",
    }, bindings={"command": "position"}))
    return project


def error_paths(project):
    result = validate_project(project)
    assert not result["valid"]
    return {item["path"] for item in result["errors"]}


def test_new_models_require_explicit_conditions_without_reinterpreting_documentary_objects():
    project = three_way_project()
    project.equipment.append(Equipment(id="drawing", name="Drawing", type="pid_symbol", symbol_kind="heat_exchanger"))
    assert validate_project(project)["valid"]
    project.equipment[-2].bindings.clear()
    assert "equipment.4.bindings.command" in error_paths(project)
    assert project.equipment[-1].type == "pid_symbol"
    assert project.equipment[-1].bindings == {}


@pytest.mark.parametrize("field,value", [
    ("primary_volume_l", 0), ("secondary_density_kg_l", -1), ("primary_cp_kj_kg_k", 0),
    ("ua_kw_k", -1), ("primary_flow_l_s", -0.001), ("initial_primary_temperature_c", -101),
    ("secondary_inlet_temperature_c", 501), ("primary_density_kg_l", True),
])
def test_nonphysical_thermal_parameters_are_rejected(field, value):
    project = thermal_project()
    project.equipment[0].params[field] = value
    assert "equipment.0.params." + field in error_paths(project)


@pytest.mark.parametrize("key,value", [("branch_a_tank_id", "AB"), ("branch_b_tank_id", "missing"), ("common_tank_id", "HX")])
def test_three_way_requires_three_distinct_simulated_tanks(key, value):
    project = three_way_project()
    project.equipment[-1].params[key] = value
    assert any(path.startswith("equipment.4.params") for path in error_paths(project))


def test_documentary_tank_is_not_a_volume_source():
    project = three_way_project()
    project.equipment[1] = Equipment(id="AB", name="AB drawing", type="pid_symbol", symbol_kind="tank")
    assert "equipment.4.params.common_tank_id" in error_paths(project)


@pytest.mark.parametrize("source,field", [("HX", "flow_l_s"), ("missing", "flow_a_l_s"), ("AB", "flow_l_s"), ("V3", "position")])
def test_thermal_flow_sources_cannot_form_cycles_or_read_nonflow_states(source, field):
    project = three_way_project()
    project.equipment[0].params.update(primary_flow_equipment=source, primary_flow_field=field)
    assert any(path.startswith("equipment.0.params.primary_flow_") for path in error_paths(project))


@pytest.mark.parametrize("field", ["flow_l_s", "flow_a_l_s", "flow_b_l_s"])
def test_explicit_three_way_flow_source_is_valid(field):
    project = three_way_project()
    project.equipment[0].params.update(primary_flow_equipment="V3", primary_flow_field=field)
    assert validate_project(project)["valid"]


def test_flow_source_and_plc_boundary_cannot_both_drive_one_circuit():
    project = three_way_project()
    project.tags.append(Tag(id="flow", name="Flow", direction="output", data_type="REAL", initial_value=2.0))
    project.equipment[0].params.update(primary_flow_equipment="V3", primary_flow_field="flow_a_l_s")
    project.equipment[0].bindings["primary_flow_command"] = "flow"
    assert "equipment.0.bindings.primary_flow_command" in error_paths(project)


@pytest.mark.parametrize("port,value", [("primary_flow_command", -1.0), ("secondary_flow_command", 100001.0), ("primary_inlet_command", -101.0), ("secondary_inlet_command", 501.0)])
def test_initial_plc_boundary_values_must_be_in_model_range(port, value):
    project = thermal_project()
    project.tags.append(Tag(id="boundary", name="Boundary", direction="output", data_type="REAL", initial_value=value))
    project.equipment[0].bindings[port] = "boundary"
    assert "equipment.0.bindings." + port in error_paths(project)


@pytest.mark.parametrize("value", [None, True, -1, 101, float("inf"), "50"])
def test_fouling_requires_an_explicit_numeric_loss_percent(value):
    project = thermal_project()
    with pytest.raises(ValueError, match="perte explicite"):
        validate_fault(project.equipment[0], "fouling", value, {})


@pytest.mark.parametrize("value", [0, 35.5, 100])
def test_fouling_does_not_require_a_fictitious_sensor_binding(value):
    validate_fault(thermal_project().equipment[0], "fouling", value, {})


def test_sensor_wire_range_includes_three_way_tank_withdrawals():
    project = three_way_project()
    project.equipment[-1].params["max_flow_l_s"] = 40000.0
    project.tags.append(Tag(id="measured", name="Measured", direction="input", data_type="INT", initial_value=0, writable=True))
    project.equipment.append(Equipment(id="FT", name="FT", type="analog_sensor", params={
        "source_equipment": "AB", "source_field": "outflow_l_s",
    }, bindings={"value": "measured"}))
    assert "equipment.5.bindings.value" in error_paths(project)
    project.equipment[-1].params["scale"] = 0.1
    assert validate_project(project)["valid"]


def test_heat_measurement_bounds_are_signed_and_validate_storage_before_running():
    project = thermal_project()
    project.equipment[0].params["ua_kw_k"] = 1e6
    project.tags.append(Tag(id="heat", name="Heat", direction="input", data_type="INT", initial_value=0, writable=True))
    project.equipment.append(Equipment(id="QT", name="QT", type="analog_sensor", params={
        "source_equipment": "HX", "source_field": "heat_kw",
    }, bindings={"value": "heat"}))
    assert "equipment.1.bindings.value" in error_paths(project)
    project.equipment[-1].params["scale"] = 0.00001
    assert validate_project(project)["valid"]


def test_new_thermal_producers_keep_existing_direction_and_unique_writer_rules():
    project = thermal_project()
    project.tags.append(Tag(id="temperature", name="Temperature", direction="input", data_type="REAL", initial_value=20.0, writable=True))
    project.equipment[0].bindings.update(primary_temperature="temperature", secondary_temperature="temperature")
    result = validate_project(project)
    assert any("Deux producteurs" in error["message"] for error in result["errors"])
    project.equipment[0].bindings = {"primary_inlet_command": "temperature"}
    result = validate_project(project)
    assert any("Sens attendu" in error["message"] for error in result["errors"])
