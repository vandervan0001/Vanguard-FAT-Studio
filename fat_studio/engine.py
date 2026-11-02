"""Deterministic, fixed-step, lumped-volume process simulation.

No PLC control algorithm lives in ProcessEngine. DemoController is a separate
test-only source of commands; the OPC UA adapter must never instantiate it.
Flow circuits are explicit: series capacities take the minimum, parallel
circuits add. This is intentionally not a pressure/network solver.
"""

from __future__ import annotations

import math
import operator
from collections import defaultdict

from .catalog import parameters
from .models import Project, validate_fault, validate_project, validate_value
from .vendor.historiansim import valve as historian_valve

COMPARISONS = {"eq": operator.eq, "ne": operator.ne, "gt": operator.gt, "ge": operator.ge, "lt": operator.lt, "le": operator.le}


def _lag(previous: float, demand: float, response_s: float, dt: float) -> float:
    value = demand if response_s <= 0 else demand + (previous - demand) * math.exp(-dt / response_s)
    return demand if abs(value - demand) < 1e-6 else value


class ProcessEngine:
    def __init__(self, project: Project):
        self.project = project.model_copy(deep=True)
        self.tags = {tag.id: tag for tag in self.project.tags}
        self.objects = {item.id: item for item in self.project.equipment}
        self._params = {item.id: parameters(item) for item in self.project.equipment}
        self.validation = validate_project(self.project)
        self.reset()

    def reset(self) -> None:
        self.time_s = 0.0
        self.values = {tag.id: tag.initial_value for tag in self.project.tags}
        self._raw_values = dict(self.values)
        self.qualities = {tag.id: "good" for tag in self.project.tags}
        self.equipment_state: dict[str, dict] = {}
        self.forces: dict[str, bool | int | float] = {}
        self.faults: dict[str, dict] = {}
        # Incomplete projects are valid editor documents. Their model cannot run.
        if not self.validation["valid"]:
            return
        for item in self.project.equipment:
            p = self._params[item.id]
            if item.type == "tank":
                volume = p["capacity_l"] * p["initial_level_pct"] / 100
                self.equipment_state[item.id] = {"volume_l": volume, "volume": volume, "level": p["initial_level_pct"], "level_percent": p["initial_level_pct"], "capacity_l": p["capacity_l"], "inflow_l_s": 0.0, "outflow_l_s": 0.0, "overflow_l": 0.0, "high": False, "low": False}
                self._tank_flags(item.id)
            elif item.type == "pump":
                self.equipment_state[item.id] = {"running": p["initial_speed_pct"] > 5, "speed": p["initial_speed_pct"], "flow_l_s": 0.0, "fault": False}
            elif item.type in ("valve_onoff", "valve_control"):
                position = p["initial_position_pct"]
                self.equipment_state[item.id] = {"position": position, "open": position >= 99.5, "closed": position <= 0.5, "flow_l_s": 0.0, "stuck": False}
            else:
                tag_id = item.bindings.get("value")
                self.equipment_state[item.id] = {"value": self.values.get(tag_id, 0), "quality": "good"}
        self._publish()

    def _tank_flags(self, tank_id: str) -> None:
        state = self.equipment_state[tank_id]
        p = self._params[tank_id]
        state["volume"] = state["volume_l"]
        state["level"] = state["volume_l"] / p["capacity_l"] * 100
        state["level_percent"] = state["level"]
        state["high"] = state["level"] >= p["high_level_pct"]
        state["low"] = state["level"] <= p["low_level_pct"]

    def step(self, commands: dict, dt: float) -> dict:
        if not self.validation["valid"]:
            raise ValueError("Projet de simulation invalide : " + "; ".join(issue["message"] for issue in self.validation["errors"]))
        if type(dt) not in (float, int) or not 0 < dt <= 2 or not math.isfinite(dt):
            raise ValueError("Le pas de calcul doit être fini, > 0 et ≤ 2 secondes.")
        output_tags = {tag.id: tag for tag in self.project.tags if tag.direction == "output"}
        if set(commands) != set(output_tags):
            missing = sorted(set(output_tags) - set(commands))
            unexpected = sorted(set(commands) - set(output_tags))
            raise ValueError(f"Image des sorties PLC incomplète/invalide (absentes={missing}, inattendues={unexpected}).")
        # Validate the complete image before changing a single state.
        validated = {tag_id: validate_value(output_tags[tag_id], value) for tag_id, value in commands.items()}
        self.values.update(validated)
        self._raw_values.update(validated)
        groups: dict[tuple[str, str, str], list[tuple[str, float]]] = defaultdict(list)
        for item in self.project.equipment:
            if item.type not in ("pump", "valve_onoff", "valve_control"):
                continue
            p = self._params[item.id]
            state = self.equipment_state[item.id]
            faults = self.faults.get(item.id, {})
            command = self.values[item.bindings["command"]]
            if item.type == "pump":
                tripped = bool(faults.get("motor_trip", False))
                target = 100.0 if command and not tripped else 0.0
                # A motor trip drops delivered flow immediately; no residual energy model.
                state["speed"] = 0.0 if tripped else _lag(state["speed"], target, p["response_s"], dt)
                state["running"] = state["speed"] > 5 and not tripped
                state["fault"] = tripped
                available = p["max_flow_l_s"] * state["speed"] / 100
            else:
                target = (100.0 if command else 0.0) if item.type == "valve_onoff" else min(max(float(command), 0.0), 100.0)
                state["position"] = float(faults["valve_stuck"]) if "valve_stuck" in faults else _lag(state["position"], target, p["response_s"], dt)
                state["stuck"] = "valve_stuck" in faults
                state["open"] = state["position"] >= 99.5
                state["closed"] = state["position"] <= 0.5
                opening = state["position"] / 100
                # Upstream equal_percentage(0) returns 1/R. Physical tight shutoff is an
                # explicit FAT model boundary, not a modification of the vendored code.
                if opening <= 1e-8:
                    fraction = 0.0
                elif item.type == "valve_onoff":
                    fraction = historian_valve.linear(opening)
                elif p["characteristic"] == "equal_percentage":
                    fraction = historian_valve.equal_percentage(opening, p["rangeability"])
                else:
                    fraction = historian_valve.characteristic(p["characteristic"])(opening)
                available = p["max_flow_l_s"] * fraction
            groups[(p["tank_id"], p["role"], p["flow_group"])].append((item.id, available))

        flows = {key: min(capacity for _, capacity in devices) for key, devices in groups.items()}
        for item in self.project.equipment:
            if item.type != "tank":
                continue
            state = self.equipment_state[item.id]
            inflow = sum(flow for key, flow in flows.items() if key[0] == item.id and key[1] == "inlet")
            requested_outflow = sum(flow for key, flow in flows.items() if key[0] == item.id and key[1] == "outlet")
            available_volume = state["volume_l"] + inflow * dt
            actual_outflow = min(requested_outflow, available_volume / dt)
            net_volume = max(0.0, available_volume - actual_outflow * dt)
            overflow = max(0.0, net_volume - state["capacity_l"])
            state.update(volume_l=min(net_volume, state["capacity_l"]), inflow_l_s=inflow, outflow_l_s=actual_outflow, overflow_l=state["overflow_l"] + overflow)
            self._tank_flags(item.id)
            # Every device in one series circuit carries the same actual flow.
            for key, devices in groups.items():
                if key[0] != item.id:
                    continue
                flow = flows[key]
                if key[1] == "outlet" and requested_outflow > 0:
                    flow *= actual_outflow / requested_outflow
                for equipment_id, _ in devices:
                    self.equipment_state[equipment_id]["flow_l_s"] = flow
        self.time_s = round(self.time_s + dt, 9)
        self._publish()
        return {tag.id: self.values[tag.id] for tag in self.project.tags if tag.direction == "input"}

    def _publish(self) -> None:
        def emit(item, port, value):
            tag_id = item.bindings.get(port)
            if tag_id is not None:
                tag = self.tags[tag_id]
                if tag.data_type in ("INT", "DINT") and type(value) is float:
                    value = int(round(value))
                self._raw_values[tag_id] = validate_value(tag, value, enforce_limits=False)

        for item in self.project.equipment:
            state = self.equipment_state[item.id]
            if item.type == "tank":
                for port, field in (("level", "level"), ("volume", "volume_l"), ("high", "high"), ("low", "low")):
                    emit(item, port, state[field])
            elif item.type == "pump":
                emit(item, "feedback", state["running"])
                emit(item, "fault", state["fault"])
            elif item.type in ("valve_onoff", "valve_control"):
                for port in ("position", "open", "closed"):
                    emit(item, port, state[port])
            elif item.type == "indicator":
                state["value"] = self.values[item.bindings["value"]]
        for item in self.project.equipment:
            if item.type not in ("analog_sensor", "digital_sensor"):
                continue
            p = self._params[item.id]
            source = self.equipment_state[p["source_equipment"]][p["source_field"]]
            faults = self.faults.get(item.id, {})
            if "out_of_range" in faults:
                value = faults["out_of_range"]
            elif "sensor_stuck" in faults:
                value = faults["sensor_stuck"]
            elif item.type == "analog_sensor":
                value = float(source) * p["scale"] + p["offset"]
            else:
                value = bool(COMPARISONS[p["operator"]](source, p["threshold"]))
            emit(item, "value", value)
        self.values.update(self._raw_values)
        self.values.update(self.forces)
        for tag in self.project.tags:
            value = self.values[tag.id]
            self.qualities[tag.id] = "forced" if tag.id in self.forces else "good"
            if tag.data_type != "BOOL" and ((tag.min is not None and value < tag.min) or (tag.max is not None and value > tag.max)):
                self.qualities[tag.id] = "out_of_range"
        for item in self.project.equipment:
            if item.type in ("analog_sensor", "digital_sensor"):
                tag_id = item.bindings["value"]
                if self.faults.get(item.id) and self.qualities[tag_id] == "good":
                    self.qualities[tag_id] = "fault"
                self.equipment_state[item.id].update(value=self.values[tag_id], quality=self.qualities[tag_id])

    def force(self, tag_id: str, value) -> None:
        tag = self.tags.get(tag_id)
        if tag is None or tag.direction != "input" or not tag.writable:
            raise ValueError("Le forçage est limité aux entrées simulées explicitement autorisées.")
        validated = validate_value(tag, value)
        self.forces[tag_id] = validated
        self.values[tag_id] = validated
        self.qualities[tag_id] = "forced"
        if self.validation["valid"]:
            self._publish()

    def release(self, tag_id: str) -> None:
        if tag_id not in self.tags or self.tags[tag_id].direction != "input":
            raise ValueError("Entrée simulée inconnue.")
        self.forces.pop(tag_id, None)
        self.values[tag_id] = self._raw_values[tag_id]
        self.qualities[tag_id] = "good"
        if self.validation["valid"]:
            self._publish()

    def set_fault(self, equipment_id: str, kind: str, value=None) -> None:
        if not self.validation["valid"]:
            raise ValueError("Complétez le projet avant d'injecter un défaut.")
        item = self.objects.get(equipment_id)
        if item is None:
            raise ValueError("Équipement inconnu.")
        validate_fault(item, kind, value, self.tags)
        existing = self.faults.get(equipment_id, {})
        if kind in ("sensor_stuck", "out_of_range") and set(existing) - {kind}:
            raise ValueError("Libérez le défaut existant avant d'appliquer un autre défaut à ce capteur.")
        if kind == "motor_trip":
            resolved = True if value is None else value
        elif kind == "valve_stuck":
            resolved = self.equipment_state[equipment_id]["position"] if value is None else float(value)
        elif kind == "sensor_stuck":
            resolved = self.values[item.bindings["value"]] if value is None else value
        else:
            resolved = value
        self.faults.setdefault(equipment_id, {})[kind] = resolved
        self._publish()

    def clear_fault(self, equipment_id: str, kind: str | None = None) -> None:
        if equipment_id not in self.objects:
            raise ValueError("Équipement inconnu.")
        if kind is None:
            self.faults.pop(equipment_id, None)
        else:
            self.faults.get(equipment_id, {}).pop(kind, None)
            if not self.faults.get(equipment_id):
                self.faults.pop(equipment_id, None)
        if self.validation["valid"]:
            self._publish()


class DemoController:
    """Small, explicit PLC stand-in, used exclusively by the demo adapter.

    Inlet devices use tank level hysteresis; outlet devices use the configured
    demo command. The controller sees mapped sensor values, including faults
    and forcing, never the plant's internal volume.
    """

    def __init__(self, project: Project):
        self.project = project.model_copy(deep=True)
        self._params = {item.id: parameters(item) for item in self.project.equipment}
        self.reset()

    def reset(self) -> None:
        self._filling = {}
        for tank in self.project.equipment:
            if tank.type == "tank":
                p = self._params[tank.id]
                self._filling[tank.id] = p["initial_level_pct"] < p["demo_stop_pct"]

    def read_commands(self, values: dict, dt: float) -> dict:
        result = {tag.id: tag.initial_value for tag in self.project.tags if tag.direction == "output"}
        generated: dict[str, bool | int | float] = {}
        for tank in self.project.equipment:
            if tank.type != "tank":
                continue
            p = self._params[tank.id]
            tag_id = tank.bindings.get("level")
            level = values.get(tag_id) if tag_id else None
            if level is None:
                for sensor in self.project.equipment:
                    sp = self._params[sensor.id]
                    if sensor.type == "analog_sensor" and sp["source_equipment"] == tank.id and sp["source_field"] in ("level", "level_percent") and sp["scale"] != 0:
                        sensor_tag = sensor.bindings.get("value")
                        if sensor_tag in values:
                            level = (values[sensor_tag] - sp["offset"]) / sp["scale"]
                            break
            if level is None:
                # Absence is visible through validation warning; no hidden plant read.
                continue
            if level >= p["demo_stop_pct"]:
                self._filling[tank.id] = False
            elif level <= p["demo_start_pct"]:
                self._filling[tank.id] = True
        for item in self.project.equipment:
            if item.type not in ("pump", "valve_onoff", "valve_control"):
                continue
            p = self._params[item.id]
            command = p["demo_command"]
            if p["demo_control"] == "level":
                on = self._filling.get(p["tank_id"], False)
                command = (100.0 if on else 0.0) if item.type == "valve_control" else on
            if item.type == "pump" and values.get(item.bindings.get("fault"), False):
                command = False
            tag_id = item.bindings.get("command")
            if tag_id is not None:
                if tag_id in generated and generated[tag_id] != command:
                    raise ValueError(f"Deux contrôleurs de démonstration produisent des commandes incompatibles pour {tag_id}.")
                generated[tag_id] = command
                result[tag_id] = command
        return result
