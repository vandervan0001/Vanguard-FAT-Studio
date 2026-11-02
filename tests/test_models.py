import pytest
from pydantic import ValidationError

from fat_studio.demo import demo_project
from fat_studio.models import Project, Scenario, Tag, validate_project, validate_tag_value


def tag_for(dtype):
    return Tag(id="value", name="Value", direction="input", data_type=dtype, initial_value=False if dtype == "BOOL" else 0 if dtype in ("INT", "DINT") else 0.0, writable=True)


@pytest.mark.parametrize("dtype,value", [("BOOL", 1), ("BOOL", "false"), ("INT", True), ("INT", 2.0), ("INT", 32768), ("INT", -32769), ("DINT", 2147483648), ("DINT", -2147483649), ("REAL", True), ("REAL", "4.2"), ("REAL", float("inf")), ("REAL", float("nan")), ("REAL", 3.5e38)])
def test_no_silent_wire_type_coercion(dtype, value):
    with pytest.raises(ValueError):
        validate_tag_value(tag_for(dtype), value)


@pytest.mark.parametrize("dtype,value", [("BOOL", True), ("BOOL", False), ("INT", 32767), ("INT", -32768), ("DINT", 2147483647), ("DINT", -2147483648), ("REAL", 12.5), ("REAL", 0)])
def test_supported_storage_types(dtype, value):
    assert validate_tag_value(tag_for(dtype), value) == value


def test_engineering_bound_override_never_disables_storage_bound():
    tag = Tag(id="x", name="x", direction="input", data_type="INT", initial_value=0, min=0, max=100, writable=True)
    with pytest.raises(ValueError):
        validate_tag_value(tag, 101)
    assert validate_tag_value(tag, 101, allow_out_of_range=True) == 101
    with pytest.raises(ValueError):
        validate_tag_value(tag, 40000, allow_out_of_range=True)


def test_plc_command_can_never_be_declared_writable():
    with pytest.raises(ValidationError):
        Tag(id="x", name="x", direction="output", data_type="BOOL", initial_value=False, writable=True)


def test_duplicate_ids_are_reported():
    project = demo_project()
    project.tags.append(project.tags[0].model_copy())
    result = validate_project(project)
    assert not result["valid"]
    assert any("dupliqué" in error["message"] for error in result["errors"])


def test_two_sensor_producers_cannot_write_one_tag():
    project = demo_project()
    project.equipment[0].bindings["level"] = "level"
    result = validate_project(project)
    assert not result["valid"]
    assert any("Deux producteurs" in error["message"] for error in result["errors"])


def test_shared_command_reads_are_allowed():
    project = demo_project()
    assert sum("pump_cmd" in item.bindings.values() for item in project.equipment) == 2
    assert validate_project(project)["valid"]


def test_mapping_direction_and_type_are_checked():
    project = demo_project()
    project.equipment[1].bindings["command"] = "level"
    result = validate_project(project)
    assert not result["valid"]
    assert any("Sens attendu" in error["message"] for error in result["errors"])
    assert any("Type attendu" in error["message"] for error in result["errors"])


def test_missing_and_duplicate_opcua_addresses_are_reported():
    project = demo_project()
    project.plc.mode = "opcua"
    project.tags[1].node_id = project.tags[0].node_id
    project.tags[2].node_id = ""
    result = validate_project(project)
    assert not result["valid"]
    messages = " ".join(item["message"] for item in result["errors"])
    assert "déjà associé" in messages
    assert "NodeId" in messages
    assert "ApplicationUri" in messages


@pytest.mark.parametrize("params", [{"capacity_l": -1}, {"initial_level_pct": 120}, {"high_level_pct": 5, "low_level_pct": 10}, {"capacity_l": "1000"}, {"invisible_parameter": 123}])
def test_invalid_physics_parameters_are_reported(params):
    project = demo_project()
    project.equipment[0].params.update(params)
    assert not validate_project(project)["valid"]


def test_nonexistent_source_and_sensor_cascade_are_refused():
    project = demo_project()
    sensor = next(item for item in project.equipment if item.id == "LT101")
    sensor.params["source_equipment"] = "does_not_exist"
    assert not validate_project(project)["valid"]
    sensor.params["source_equipment"] = "LSH101"
    assert not validate_project(project)["valid"]


def test_unknown_source_field_is_rejected_before_start():
    project = demo_project()
    next(item for item in project.equipment if item.id == "LT101").params["source_field"] = "temperature"
    assert not validate_project(project)["valid"]


def test_sensor_scaling_cannot_overflow_plc_storage_during_model_reset():
    project = demo_project()
    sensor = next(item for item in project.equipment if item.id == "LT101")
    sensor.params["scale"] = 1000.0
    project.tags = [Tag(id=tag.id, name=tag.name, direction="input", data_type="INT", initial_value=25, writable=True) if tag.id == "level" else tag for tag in project.tags]
    project.scenarios = []
    result = validate_project(project)
    assert not result["valid"]
    assert any("plage du modèle" in error["message"] for error in result["errors"])


def test_huge_real_integer_is_rejected_cleanly():
    with pytest.raises(ValueError):
        validate_tag_value(tag_for("REAL"), 10**400)


@pytest.mark.parametrize("steps", [[{"at_s": 12, "action": "marker", "message": "late"}], [{"at_s": 9, "action": "marker", "message": "A"}, {"at_s": 1, "action": "marker", "message": "B"}]])
def test_scenario_timeline_must_be_ordered_and_within_duration(steps):
    with pytest.raises(ValidationError):
        Scenario(id="x", name="x", duration_s=10, steps=steps)


def test_scenario_cannot_force_plc_commands_or_bad_types():
    project = demo_project()
    project.scenarios = [Scenario(id="bad", name="bad", duration_s=10, steps=[{"at_s": 0, "action": "force", "target": "pump_cmd", "value": True}, {"at_s": 1, "action": "force", "target": "pump_running", "value": 1}])]
    result = validate_project(project)
    assert not result["valid"]
    assert len(result["errors"]) == 2


@pytest.mark.parametrize("at_s", [10.0, 9.95])
def test_terminal_mutation_without_a_following_write_is_refused(at_s):
    project = demo_project()
    project.scenarios = [Scenario(id="terminal", name="terminal", duration_s=10, steps=[{"at_s": at_s, "action": "force", "target": "level", "value": 50.0}])]
    result = validate_project(project)
    assert not result["valid"]
    assert any("dernière écriture" in error["message"] for error in result["errors"])


def test_assertion_and_marker_at_final_timestamp_remain_valid():
    project = demo_project()
    project.scenarios = [Scenario(id="terminal", name="terminal", duration_s=10, steps=[
        {"at_s": 9.9, "action": "force", "target": "level", "value": 50.0},
        {"at_s": 10, "action": "expect", "target": "level", "value": 50.0},
        {"at_s": 10, "action": "marker", "message": "fin"},
    ])]
    assert validate_project(project)["valid"]


def test_payload_limits_and_unknown_fields_are_explicit():
    raw = demo_project().model_dump()
    raw["unsafe_script"] = "ignored?"
    with pytest.raises(ValidationError):
        Project.model_validate(raw)
    raw.pop("unsafe_script")
    raw["equipment"] = raw["equipment"] * 7
    with pytest.raises(ValidationError):
        Project.model_validate(raw)


def test_project_is_stable_through_json_roundtrip():
    project = demo_project()
    restored = Project.model_validate_json(project.model_dump_json())
    assert restored == project
    assert validate_project(restored)["valid"]
