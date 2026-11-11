"""The drawing library preserves terminals without creating process semantics."""

import json
import math

import pytest

from fat_studio.pid_symbols import PID_SYMBOLS, PID_SYMBOLS_BY_ID, resolve_symbol


def test_documentary_catalog_has_distinct_ids_and_no_simulation_authority():
    assert len(PID_SYMBOLS) == 61
    assert len(PID_SYMBOLS_BY_ID) == len(PID_SYMBOLS)
    for symbol in PID_SYMBOLS:
        assert symbol["id"] and symbol["label"] and symbol["category"] and symbol["prefix"]
        assert symbol["simulation"] is False
        assert "sans modèle physique" in symbol["description"]
        assert not {"bindings", "params", "faults", "state", "plc", "command"} & symbol.keys()
    assert json.loads(json.dumps(PID_SYMBOLS, ensure_ascii=False)) == PID_SYMBOLS


def test_heat_exchangers_have_two_distinct_circuits_and_four_terminals():
    for identifier in ("heat_exchanger", "plate_heat_exchanger", "condenser"):
        ports = PID_SYMBOLS_BY_ID[identifier]["ports"]
        assert [port["id"] for port in ports] == ["primary_in", "primary_out", "secondary_in", "secondary_out"]
        assert [port["direction"] for port in ports] == ["in", "out", "in", "out"]
        assert len({(port["x"], port["y"]) for port in ports}) == 4


def test_multiway_valves_keep_every_independent_terminal():
    three = PID_SYMBOLS_BY_ID["three_way_valve"]
    four = PID_SYMBOLS_BY_ID["four_way_valve"]
    assert [port["id"] for port in three["ports"]] == ["AB", "A", "B"]
    assert [port["id"] for port in four["ports"]] == ["P1", "P2", "P3", "P4"]
    assert all(port["direction"] == "bidirectional" for symbol in (three, four) for port in symbol["ports"])


def test_geometry_is_bounded_inert_data_compatible_with_shared_export_scene():
    keys = {
        "polyline": {"kind", "points", "stroke", "width"},
        "polygon": {"kind", "points", "stroke", "fill", "width"},
        "rect": {"kind", "x", "y", "width", "height", "stroke", "fill"},
        "circle": {"kind", "x", "y", "radius", "stroke", "fill", "width"},
        "ellipse": {"kind", "x", "y", "rx", "ry", "stroke", "fill", "width"},
    }
    for symbol in PID_SYMBOLS:
        assert symbol["shapes"] and 1 <= len(symbol["ports"]) <= 4
        assert len(symbol["ports"]) != 1 or symbol.get("instrument_code")
        assert len({port["id"] for port in symbol["ports"]}) == len(symbol["ports"])
        for port in symbol["ports"]:
            assert port["direction"] in {"in", "out", "bidirectional"}
            assert 0 <= port["x"] <= 100 and 0 <= port["y"] <= 100
        for shape in symbol["shapes"]:
            assert shape["kind"] in keys and shape.keys() <= keys[shape["kind"]]
            for value in shape.values():
                if isinstance(value, (int, float)):
                    assert math.isfinite(value) and 0 <= value <= 100
            for point in shape.get("points", []):
                assert len(point) == 2 and all(0 <= value <= 100 for value in point)
            if shape["kind"] in {"circle", "ellipse"}:
                rx, ry = (shape["radius"], shape["radius"]) if shape["kind"] == "circle" else (shape["rx"], shape["ry"])
                assert 0 <= shape["x"] - rx < shape["x"] + rx <= 100
                assert 0 <= shape["y"] - ry < shape["y"] + ry <= 100
            if shape["kind"] == "rect":
                assert shape["x"] + shape["width"] <= 100 and shape["y"] + shape["height"] <= 100


@pytest.mark.parametrize("source,expected", [
    ("HeatExchanger", "heat_exchanger"), ("ShellAndTubeHeatExchanger", "heat_exchanger"),
    ("PlateHeatExchanger", "plate_heat_exchanger"), ("Échangeur à plaques", "plate_heat_exchanger"),
    ("ThreeWayValve", "three_way_valve"), ("vanne 3 voies", "three_way_valve"),
    ("FOUR-WAY-VALVE", "four_way_valve"), ("vanne quatre voies", "four_way_valve"),
    ("CentrifugalPump", "pump"), ("NonReturnValve", "check_valve"),
    ("soupape de sûreté", "relief_valve"), ("Unknown", "generic"),
])
def test_declared_source_aliases_are_resolved(source, expected):
    assert resolve_symbol(source) == expected


@pytest.mark.parametrize("source", ["", " ", "PSV-101", "HX-001", "my_custom_reactor", "<svg>HeatExchanger</svg>",
                                     "https://example.invalid/heat_exchanger", "__import__('os')", "x" * 161, None, 42])
def test_unknown_source_names_are_not_guessed(source):
    assert resolve_symbol(source) is None


def test_every_library_id_and_french_label_resolves_to_itself():
    for symbol in PID_SYMBOLS:
        assert resolve_symbol(symbol["id"]) == symbol["id"]
        assert resolve_symbol(symbol["label"]) == symbol["id"]


def test_shapes_and_ports_are_not_shared_between_library_entries():
    first, second = PID_SYMBOLS_BY_ID["heat_exchanger"], PID_SYMBOLS_BY_ID["condenser"]
    assert first["ports"] == second["ports"] and first["ports"] is not second["ports"]
    assert first["ports"][0] is not second["ports"][0]
    assert first["shapes"][0] is not second["shapes"][0]
