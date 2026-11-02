"""Versioned project format and validation at the plant/PLC boundary."""

from __future__ import annotations

import math
import re
import struct
from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .catalog import CATALOG_BY_TYPE, STATE_FIELDS, parameters

ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]{0,79}$"
Scalar = bool | int | float
EquipmentType = Literal["tank", "pump", "valve_onoff", "valve_control", "analog_sensor", "digital_sensor", "indicator"]
DataType = Literal["BOOL", "INT", "DINT", "REAL"]
REAL_MAX = 3.4028234663852886e38


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True, allow_inf_nan=False)


class Position(StrictModel):
    x: float = Field(default=0, ge=-100000, le=100000)
    y: float = Field(default=0, ge=-100000, le=100000)


class SimulationConfig(StrictModel):
    step_ms: int = Field(default=100, ge=20, le=2000, strict=True)
    speed: float = Field(default=1.0, ge=0.1, le=20)


class PLCConfig(StrictModel):
    mode: Literal["demo", "opcua"] = "demo"
    tia_version: Literal["V20", "V21"] = "V21"
    endpoint: str = Field(default="opc.tcp://127.0.0.1:4840", max_length=512)
    expected_application_uri: str = Field(default="", max_length=512)
    namespace_uri: str = Field(default="", max_length=512)
    security_policy: Literal["None", "Basic256Sha256"] = "None"
    server_certificate_sha256: str = Field(default="", max_length=95)
    client_certificate: str = Field(default="", max_length=1000)
    client_private_key: str = Field(default="", max_length=1000)
    username_env: str = Field(default="", max_length=128)
    password_env: str = Field(default="", max_length=128)
    approved_virtual_target: str = Field(default="", max_length=512)
    timeout_s: float = Field(default=3, ge=0.2, le=30)

    @field_validator("username_env", "password_env")
    @classmethod
    def valid_env_name(cls, value: str) -> str:
        if value and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError("Le champ doit contenir un nom de variable d'environnement, pas un secret.")
        return value


class Tag(StrictModel):
    id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    direction: Literal["input", "output"]
    data_type: DataType
    unit: str = Field(default="", max_length=40)
    initial_value: Any = 0.0
    min: float | None = None
    max: float | None = None
    node_id: str = Field(default="", max_length=1000)
    writable: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def check_value(self):
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("La limite min doit être inférieure ou égale à max.")
        if self.direction == "output" and self.writable:
            raise ValueError("Une sortie PLC ne peut jamais être autorisée en écriture.")
        # Store the same value that the declared PLC type can represent. Bypass
        # assignment validation here to avoid recursively invoking this validator.
        object.__setattr__(self, "initial_value", validate_value(self, self.initial_value))
        return self


class Equipment(StrictModel):
    id: str = Field(pattern=ID_PATTERN)
    type: EquipmentType
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    unit: str = Field(default="", max_length=40)
    position: Position = Field(default_factory=Position)
    params: dict[str, Any] = Field(default_factory=dict, max_length=30)
    bindings: dict[str, str] = Field(default_factory=dict, max_length=16)

    @field_validator("params")
    @classmethod
    def scalar_params(cls, value: dict) -> dict:
        for key, item in value.items():
            if not isinstance(item, (str, bool, int, float)) or (isinstance(item, float) and not math.isfinite(item)):
                raise ValueError(f"Le paramètre {key} doit être un scalaire fini.")
            if len(key) > 80 or (isinstance(item, str) and len(item) > 1000):
                raise ValueError("Paramètre trop long.")
        return value


class Connection(StrictModel):
    id: str = Field(pattern=ID_PATTERN)
    source: str = Field(pattern=ID_PATTERN)
    target: str = Field(pattern=ID_PATTERN)
    label: str = Field(default="", max_length=200)
    directed: bool = True


class ScenarioStep(StrictModel):
    at_s: float = Field(ge=0, le=86400)
    action: Literal["force", "release", "fault", "clear_fault", "marker", "expect"]
    target: str = Field(default="", max_length=80)
    value: Any = None
    operator: Literal["eq", "ne", "gt", "ge", "lt", "le"] = "eq"
    tolerance: float = Field(default=0.001, ge=0, le=1e9)
    message: str = Field(default="", max_length=4000)

    @field_validator("value")
    @classmethod
    def finite_value(cls, value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("La valeur d'une étape doit être finie.")
        if isinstance(value, dict):
            if set(value) - {"kind", "value"}:
                raise ValueError("Une valeur de défaut accepte seulement kind et value.")
            if not isinstance(value.get("kind"), str):
                raise ValueError("Le défaut doit préciser kind.")
            item = value.get("value")
            if item is not None and (not isinstance(item, (bool, int, float)) or (isinstance(item, float) and not math.isfinite(item))):
                raise ValueError("La valeur du défaut doit être un scalaire fini.")
        elif value is not None and not isinstance(value, (bool, int, float, str)):
            raise ValueError("Valeur de scénario non prise en charge.")
        return value


class Scenario(StrictModel):
    id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    duration_s: float = Field(default=60, gt=0, le=86400)
    steps: list[ScenarioStep] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def ordered_steps(self):
        previous = -1.0
        for step in self.steps:
            if step.at_s < previous:
                raise ValueError("Les étapes du scénario doivent être ordonnées par temps croissant.")
            if step.at_s > self.duration_s:
                raise ValueError("Une étape dépasse la durée du scénario.")
            previous = step.at_s
        return self


class Project(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    equipment: list[Equipment] = Field(default_factory=list, max_length=50)
    connections: list[Connection] = Field(default_factory=list, max_length=200)
    tags: list[Tag] = Field(default_factory=list, max_length=200)
    scenarios: list[Scenario] = Field(default_factory=list, max_length=100)
    plc: PLCConfig = Field(default_factory=PLCConfig)


def _float32(value: int | float) -> float:
    return struct.unpack("!f", struct.pack("!f", value))[0]


def engineering_bounds(tag: Tag) -> tuple[float | None, float | None]:
    """Compare REAL signals to bounds in their PLC representation too."""
    def bound(value):
        return _float32(value) if tag.data_type == "REAL" and value is not None and abs(value) <= REAL_MAX else value

    return bound(tag.min), bound(tag.max)


def outside_engineering_limits(tag: Tag, value: Scalar) -> bool:
    low, high = engineering_bounds(tag)
    return tag.data_type != "BOOL" and ((low is not None and value < low) or (high is not None and value > high))


def validate_value(tag: Tag, value: Any, *, enforce_limits: bool = True) -> Scalar:
    """Validate wire types without Python's unsafe bool/int/string coercions.

    Fault injection can bypass engineering bounds, never PLC storage bounds.
    REAL is quantized to IEEE-754 single precision so the logged image, demo
    controller and OPC UA Float carry exactly the same signal. Plant state is
    still calculated in double precision.
    """
    if tag.data_type == "BOOL":
        if type(value) is not bool:
            raise ValueError(f"{tag.name} attend un BOOL (true/false).")
        result = value
    elif tag.data_type in ("INT", "DINT"):
        if type(value) is not int:
            raise ValueError(f"{tag.name} attend un entier {tag.data_type}.")
        low, high = (-32768, 32767) if tag.data_type == "INT" else (-2147483648, 2147483647)
        if not low <= value <= high:
            raise ValueError(f"{tag.name} dépasse la plage {tag.data_type} [{low}, {high}].")
        result = value
    else:
        if type(value) not in (int, float) or abs(value) > REAL_MAX or not math.isfinite(value):
            raise ValueError(f"{tag.name} attend un REAL fini.")
        result = _float32(value)
    if enforce_limits and tag.data_type != "BOOL":
        low, high = engineering_bounds(tag)
        if low is not None and result < low:
            raise ValueError(f"{tag.name} doit être ≥ {tag.min} {tag.unit}.")
        if high is not None and result > high:
            raise ValueError(f"{tag.name} doit être ≤ {tag.max} {tag.unit}.")
    return result


def validate_tag_value(tag: Tag, value: Any, *, allow_out_of_range: bool = False) -> Scalar:
    """Public adapter boundary; faults may bypass engineering limits only."""
    return validate_value(tag, value, enforce_limits=not allow_out_of_range)


def validate_fault(equipment: Equipment, kind: str, value: Any, tags: dict[str, Tag]) -> None:
    if kind not in CATALOG_BY_TYPE[equipment.type]["faults"]:
        raise ValueError(f"Défaut {kind!r} indisponible pour {equipment.name}.")
    if kind == "motor_trip":
        if value is not None and type(value) is not bool:
            raise ValueError("motor_trip accepte une valeur booléenne ou aucune valeur.")
    elif kind == "valve_stuck":
        if value is not None and (type(value) not in (int, float) or not 0 <= value <= 100 or not math.isfinite(value)):
            raise ValueError("La position de vanne bloquée doit être comprise entre 0 et 100 %.")
    else:
        tag_id = equipment.bindings.get("value")
        if tag_id not in tags:
            raise ValueError("Le capteur doit être associé à une variable avant l'injection.")
        if value is not None:
            value = validate_value(tags[tag_id], value, enforce_limits=kind != "out_of_range")
        if kind == "out_of_range":
            tag = tags[tag_id]
            if value is None:
                raise ValueError("Le défaut hors plage exige une valeur explicite.")
            if not outside_engineering_limits(tag, value):
                raise ValueError("La valeur du défaut doit être hors des limites min/max du tag.")


def _source_range(source: Equipment, field: str, equipment: dict[str, Equipment]) -> tuple[float, float] | None:
    """Conservative finite bounds used to reject incompatible wire mappings."""
    p = parameters(source)
    if field in ("level", "level_percent", "speed", "position"):
        return (0, 100)
    if field in ("high", "low", "running", "fault", "open", "closed", "stuck"):
        return (0, 1)
    if field in ("volume", "volume_l"):
        return (0, p["capacity_l"])
    if field == "capacity_l":
        return (p["capacity_l"], p["capacity_l"])
    if field == "flow_l_s":
        return (0, p["max_flow_l_s"])
    if field in ("inflow_l_s", "outflow_l_s"):
        role = "inlet" if field == "inflow_l_s" else "outlet"
        groups: dict[str, list[float]] = defaultdict(list)
        for item in equipment.values():
            if item.type not in ("pump", "valve_onoff", "valve_control"):
                continue
            flow = parameters(item)
            if flow["tank_id"] == source.id and flow["role"] == role:
                groups[flow["flow_group"]].append(flow["max_flow_l_s"])
        return (0, sum(min(capacities) for capacities in groups.values()))
    return None


def validate_project(project: Project | dict) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []
    if not isinstance(project, Project):
        try:
            project = Project.model_validate(project)
        except ValidationError as exc:
            return {"valid": False, "errors": [{"path": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()], "warnings": []}

    def error(path, message):
        errors.append({"path": path, "message": message})

    def warning(path, message):
        warnings.append({"path": path, "message": message})

    for collection in ("equipment", "tags", "connections", "scenarios"):
        seen: set[str] = set()
        for index, obj in enumerate(getattr(project, collection)):
            if obj.id in seen:
                error(f"{collection}.{index}.id", f"Identifiant dupliqué : {obj.id}.")
            seen.add(obj.id)
    tags = {tag.id: tag for tag in project.tags}
    equipment = {item.id: item for item in project.equipment}
    producers: dict[str, str] = {}
    used_tags: set[str] = set()
    nodes: dict[str, str] = {}
    if not equipment:
        warning("equipment", "Aucun équipement ; seuls les tags manuels seront simulés.")
    if not tags:
        error("tags", "Ajoutez au moins une variable de simulation.")

    for i, tag in enumerate(project.tags):
        path = f"tags.{i}"
        if tag.direction == "input" and not tag.writable:
            error(path + ".writable", "L'entrée simulée doit être explicitement autorisée en écriture.")
        if tag.direction == "input" and tag.data_type != "BOOL" and (tag.min is None or tag.max is None):
            warning(path, "Bornes de procédé incomplètes : seuls les types et limites de stockage sont garantis.")
        if tag.node_id.strip():
            if tag.node_id.strip() in nodes:
                error(path + ".node_id", f"Nœud PLC déjà associé à {nodes[tag.node_id.strip()]}.")
            nodes[tag.node_id.strip()] = tag.id
        elif project.plc.mode == "opcua":
            error(path + ".node_id", "NodeId OPC UA requis avant la connexion.")

    for i, item in enumerate(project.equipment):
        path = f"equipment.{i}"
        spec = CATALOG_BY_TYPE[item.type]
        params = parameters(item)
        for name, value in item.params.items():
            meta = spec["parameters"].get(name)
            if meta is None:
                error(path + ".params." + name, "Paramètre inconnu ; il ne serait pas simulé.")
                continue
            kind = meta["type"]
            if kind == "number":
                if type(value) not in (int, float) or not meta["min"] <= value <= meta["max"] or not math.isfinite(value):
                    error(path + ".params." + name, f"Valeur numérique attendue entre {meta['min']} et {meta['max']}.")
            elif kind == "boolean" and type(value) is not bool:
                error(path + ".params." + name, "Booléen attendu.")
            elif kind in ("string", "select") and not isinstance(value, str):
                error(path + ".params." + name, "Texte attendu.")
            elif kind == "select" and value not in meta["options"]:
                error(path + ".params." + name, f"Valeur attendue : {', '.join(meta['options'])}.")

        for name, meta in spec["ports"].items():
            if meta["required"] and not item.bindings.get(name):
                error(path + ".bindings." + name, f"Association manquante : {meta['label']}.")
        for name, tag_id in item.bindings.items():
            meta = spec["ports"].get(name)
            tag = tags.get(tag_id)
            if meta is None:
                error(path + ".bindings." + name, "Port inexistant pour ce symbole.")
            elif tag is None:
                error(path + ".bindings." + name, f"Variable inconnue : {tag_id}.")
            else:
                used_tags.add(tag_id)
                if tag.direction != meta["direction"]:
                    error(path + ".bindings." + name, f"Sens attendu : {meta['direction']} (vu depuis le PLC).")
                if tag.data_type not in meta["data_types"]:
                    error(path + ".bindings." + name, f"Type attendu : {' / '.join(meta['data_types'])}.")
                if meta["direction"] == "input":
                    if tag_id in producers:
                        error(path + ".bindings." + name, f"Deux producteurs écrivent {tag_id} : {producers[tag_id]} et {item.id}.{name}.")
                    producers[tag_id] = f"{item.id}.{name}"

        if item.type in ("pump", "valve_onoff", "valve_control"):
            tank = equipment.get(params.get("tank_id"))
            if tank is None or tank.type != "tank":
                error(path + ".params.tank_id", "Associez le débit à une cuve existante.")
            if not isinstance(params.get("flow_group"), str) or not params["flow_group"].strip():
                error(path + ".params.flow_group", "Le circuit hydraulique doit être nommé.")
        elif item.type in ("analog_sensor", "digital_sensor"):
            source = equipment.get(params.get("source_equipment"))
            if source is None:
                error(path + ".params.source_equipment", "Équipement mesuré introuvable.")
            elif source.type in ("analog_sensor", "digital_sensor", "indicator"):
                error(path + ".params.source_equipment", "La source doit être un équipement physique (cuve, pompe ou vanne).")
            elif params.get("source_field") not in STATE_FIELDS[source.type]:
                error(path + ".params.source_field", f"Grandeur inconnue ; possibilités : {', '.join(sorted(STATE_FIELDS[source.type]))}.")
            elif item.type == "analog_sensor":
                tag = tags.get(item.bindings.get("value"))
                if tag is not None:
                    try:
                        source_range = _source_range(source, params["source_field"], equipment)
                        # Cumulative overflow has no finite bound in a manual
                        # run, but its initial value (zero) must still be valid.
                        for source_value in source_range if source_range is not None else (0,):
                            value = source_value * params["scale"] + params["offset"]
                            if tag.data_type in ("INT", "DINT"):
                                value = int(round(value))
                            validate_value(tag, value, enforce_limits=False)
                        if source_range is None and params["scale"] != 0:
                            warning(path + ".bindings.value", "Cette mesure cumulative n'a pas de borne supérieure : un dépassement du type PLC arrêtera l'essai.")
                    except (ValueError, TypeError, OverflowError):
                        error(path + ".bindings.value", "La plage du modèle dépasse le type PLC de cette mesure ; ajustez l'échelle ou le type.")
        elif item.type == "tank":
            for low, high in (("low_level_pct", "high_level_pct"), ("demo_start_pct", "demo_stop_pct")):
                if type(params.get(low)) in (int, float) and type(params.get(high)) in (int, float) and params[low] >= params[high]:
                    error(path + ".params", f"{low} doit être inférieur à {high}.")

    for i, edge in enumerate(project.connections):
        if edge.source not in equipment or edge.target not in equipment:
            error(f"connections.{i}", "La connexion référence un symbole inexistant.")
        if edge.source == edge.target:
            error(f"connections.{i}", "Une connexion doit relier deux symboles distincts.")
    for tag in project.tags:
        if tag.id not in used_tags:
            warning(f"tags.{tag.id}", "Variable non associée à un symbole ; sa valeur initiale reste disponible pour les essais manuels." if tag.direction == "input" else "Sortie PLC lue mais non associée à un symbole.")

    if project.plc.mode == "opcua":
        if not project.plc.expected_application_uri:
            error("plc.expected_application_uri", "Identité ApplicationUri du serveur virtuel attendue.")
        if not project.plc.approved_virtual_target:
            error("plc.approved_virtual_target", "Le nom de la cible virtuelle doit être renseigné.")
        warning("plc", "La topologie et l'identité doivent être qualifiées sur le poste Siemens ; l'ApplicationUri ne prouve pas à elle seule qu'une CPU est virtuelle.")
    if project.connections:
        warning("connections", "Les lignes sont graphiques. Les débits utilisent cuve, sens et circuit explicitement configurés, sans solveur hydraulique général.")
    if project.plc.mode == "demo":
        for item in project.equipment:
            p = parameters(item)
            if item.type not in ("pump", "valve_onoff", "valve_control") or p.get("demo_control") != "level":
                continue
            tank = equipment.get(p.get("tank_id"))
            if tank is None:
                continue
            sensors = [sensor for sensor in project.equipment if sensor.type == "analog_sensor" and parameters(sensor).get("source_equipment") == tank.id and parameters(sensor).get("source_field") in ("level", "level_percent") and parameters(sensor).get("scale") != 0 and sensor.bindings.get("value") in tags]
            if not tank.bindings.get("level") and not sensors:
                warning(f"equipment.{item.id}.params.demo_control", "Le contrôleur de démonstration n'a pas de niveau associé : il conserve son état initial. Associez un transmetteur ou choisissez une commande constante.")

    for i, scenario in enumerate(project.scenarios):
        for j, step in enumerate(scenario.steps):
            path = f"scenarios.{i}.steps.{j}"
            try:
                if step.action in ("force", "release", "fault", "clear_fault"):
                    dt = project.simulation.step_ms / 1000
                    first_cycle_start = math.ceil((step.at_s - 1e-9) / dt) * dt
                    if first_cycle_start >= scenario.duration_s - 1e-9:
                        raise ValueError("Cette action arriverait après la dernière écriture du scénario. Placez-la avant le début du dernier cycle ; seules les assertions et marqueurs sont admis à la fin.")
                if step.action in ("force", "release", "expect"):
                    tag = tags.get(step.target)
                    if tag is None:
                        raise ValueError("Variable cible du scénario inconnue.")
                    if step.action in ("force", "release") and (tag.direction != "input" or not tag.writable):
                        raise ValueError("Seules les entrées simulées autorisées peuvent être forcées/libérées.")
                    if step.action == "force":
                        validate_value(tag, step.value)
                    elif step.action == "expect":
                        validate_value(tag, step.value, enforce_limits=False)
                        if tag.data_type == "BOOL" and step.operator not in ("eq", "ne"):
                            raise ValueError("Les assertions booléennes acceptent seulement eq et ne.")
                elif step.action in ("fault", "clear_fault"):
                    item = equipment.get(step.target)
                    if item is None:
                        raise ValueError("Équipement cible du scénario inconnu.")
                    if step.action == "fault":
                        if not isinstance(step.value, dict) or "kind" not in step.value:
                            raise ValueError("Le défaut exige {kind, value?}.")
                        validate_fault(item, step.value["kind"], step.value.get("value"), tags)
                    elif step.value is not None:
                        if not isinstance(step.value, dict) or step.value.get("kind") not in CATALOG_BY_TYPE[item.type]["faults"]:
                            raise ValueError("clear_fault accepte aucune valeur ou {kind: défaut supporté}.")
                elif step.action == "marker" and not (step.message or isinstance(step.value, str)):
                    raise ValueError("Un marqueur doit contenir un commentaire.")
            except (ValueError, TypeError) as exc:
                error(path, str(exc))
    return {"valid": not errors, "errors": errors, "warnings": warnings}
