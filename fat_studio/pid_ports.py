"""Drawing connection points, independent of PLC signal ports and flow models."""

from __future__ import annotations

from .pid_symbols import PID_SYMBOLS_BY_ID, resolve_symbol


# These aliases describe drawing terminals; they never select a physical model.
SIMULATED_PID_SYMBOLS = {"heat_exchanger": "heat_exchanger", "valve_three_way": "three_way_valve"}


LEGACY_PORTS = {
    "tank": [("in", "Entrée", 0, 50), ("out", "Sortie", 100, 50)],
    "pump": [("in", "Aspiration", 0, 50), ("out", "Refoulement", 100, 50)],
    "pump_vfd": [("in", "Aspiration", 0, 50), ("out", "Refoulement", 100, 50)],
    "valve_onoff": [("in", "Amont", 0, 50), ("out", "Aval", 100, 50)],
    "valve_control": [("in", "Amont", 0, 50), ("out", "Aval", 100, 50)],
    "analog_sensor": [("tap", "Prise de mesure", 50, 100)],
    "digital_sensor": [("tap", "Prise de mesure", 50, 100)],
}


def process_ports(equipment) -> list[dict]:
    if equipment.type == "pid_symbol":
        return PID_SYMBOLS_BY_ID[equipment.symbol_kind]["ports"]
    if equipment.type in SIMULATED_PID_SYMBOLS:
        return PID_SYMBOLS_BY_ID[SIMULATED_PID_SYMBOLS[equipment.type]]["ports"]
    return [{"id": identifier, "label": label, "x": x, "y": y, "direction": "bidirectional"}
            for identifier, label, x, y in LEGACY_PORTS.get(equipment.type, [])]


def document_ports(kind: str) -> list[dict]:
    identifier = SIMULATED_PID_SYMBOLS.get(kind) or resolve_symbol(kind)
    return PID_SYMBOLS_BY_ID[identifier]["ports"] if identifier else []


def rotate_point(x: float, y: float, rotation: int) -> tuple[float, float]:
    for _ in range((rotation % 360) // 90):
        x, y = 100 - y, x
    return x, y


def port_point(kind: str, identifier: str, rotation: int) -> tuple[float, float] | None:
    port = next((port for port in document_ports(kind) if port["id"] == identifier), None)
    return rotate_point(port["x"], port["y"], rotation) if port else None
