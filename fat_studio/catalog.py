"""Equipment catalogue shared by validation, the editor and the plant model."""

from __future__ import annotations


def port(label: str, direction: str, types: list[str], unit: str = "", required: bool = False) -> dict:
    return {"label": label, "direction": direction, "data_types": types, "unit": unit, "required": required}


def number(label: str, low: float, high: float, unit: str = "") -> dict:
    return {"label": label, "type": "number", "min": low, "max": high, "unit": unit}


FLOW_PARAMETERS = {
    "tank_id": {"label": "Cuve associée (identifiant)", "type": "string"},
    "role": {"label": "Sens du débit", "type": "select", "options": ["inlet", "outlet"]},
    "flow_group": {"label": "Circuit en série", "type": "string"},
    "max_flow_l_s": number("Débit à pleine ouverture", 0, 100000, "L/s"),
    "response_s": number("Constante de réponse", 0, 120, "s"),
    "demo_control": {"label": "Contrôle de démonstration", "type": "select", "options": ["level", "constant"]},
}

CATALOG = [
    {
        "type": "tank", "label": "Cuve", "description": "Bilan volumique d'une cuve à section constante. Niveau exprimé en %.",
        "default_params": {"capacity_l": 1000.0, "initial_level_pct": 25.0, "high_level_pct": 90.0, "low_level_pct": 10.0, "demo_start_pct": 30.0, "demo_stop_pct": 70.0},
        "parameters": {"capacity_l": number("Volume utile", 0.001, 1e9, "L"), "initial_level_pct": number("Niveau initial", 0, 100, "%"), "high_level_pct": number("Seuil haut", 0, 100, "%"), "low_level_pct": number("Seuil bas", 0, 100, "%"), "demo_start_pct": number("Démo : reprise remplissage", 0, 100, "%"), "demo_stop_pct": number("Démo : arrêt remplissage", 0, 100, "%")},
        "ports": {"level": port("Niveau", "input", ["REAL"], "%"), "volume": port("Volume", "input", ["REAL"], "L"), "high": port("Niveau haut", "input", ["BOOL"]), "low": port("Niveau bas", "input", ["BOOL"])},
        "faults": [],
    },
    {
        "type": "pump", "label": "Pompe", "description": "Pompe commandée en tout-ou-rien avec inertie et défaut moteur.",
        "default_params": {"tank_id": "", "role": "inlet", "flow_group": "feed", "max_flow_l_s": 30.0, "response_s": 0.4, "initial_speed_pct": 0.0, "demo_control": "level", "demo_command": True},
        "parameters": {**FLOW_PARAMETERS, "initial_speed_pct": number("Vitesse initiale", 0, 100, "%"), "demo_command": {"label": "Démo : commande constante", "type": "boolean"}},
        "ports": {"command": port("Commande marche PLC", "output", ["BOOL"], required=True), "feedback": port("Retour marche simulé", "input", ["BOOL"]), "fault": port("Défaut moteur simulé", "input", ["BOOL"])},
        "faults": ["motor_trip"],
    },
    {
        "type": "valve_onoff", "label": "Vanne TOR", "description": "Vanne tout-ou-rien avec temps de réponse et fins de course.",
        "default_params": {"tank_id": "", "role": "inlet", "flow_group": "feed", "max_flow_l_s": 25.0, "response_s": 0.3, "initial_position_pct": 0.0, "demo_control": "level", "demo_command": True},
        "parameters": {**FLOW_PARAMETERS, "initial_position_pct": number("Position initiale", 0, 100, "%"), "demo_command": {"label": "Démo : commande constante", "type": "boolean"}},
        "ports": {"command": port("Commande ouverture PLC", "output", ["BOOL"], required=True), "position": port("Position simulée", "input", ["REAL"], "%"), "open": port("Fin de course ouvert", "input", ["BOOL"]), "closed": port("Fin de course fermé", "input", ["BOOL"])},
        "faults": ["valve_stuck"],
    },
    {
        "type": "valve_control", "label": "Vanne modulante", "description": "Position 0–100 %, caractéristique HistorianSim, fermeture étanche à 0 %.",
        "default_params": {"tank_id": "", "role": "outlet", "flow_group": "drain", "max_flow_l_s": 12.0, "response_s": 0.5, "initial_position_pct": 0.0, "characteristic": "linear", "rangeability": 50.0, "demo_control": "constant", "demo_command": 35.0},
        "parameters": {**FLOW_PARAMETERS, "initial_position_pct": number("Position initiale", 0, 100, "%"), "characteristic": {"label": "Caractéristique de débit", "type": "select", "options": ["linear", "equal_percentage", "quick_opening"]}, "rangeability": number("Rangeabilité", 1.001, 10000), "demo_command": number("Démo : commande constante", 0, 100, "%")},
        "ports": {"command": port("Consigne position PLC", "output", ["REAL"], "%", required=True), "position": port("Position simulée", "input", ["REAL"], "%"), "open": port("Fin de course ouvert", "input", ["BOOL"]), "closed": port("Fin de course fermé", "input", ["BOOL"])},
        "faults": ["valve_stuck"],
    },
    {
        "type": "analog_sensor", "label": "Capteur analogique", "description": "Mesure d'un état du procédé : valeur = source × échelle + décalage.",
        "default_params": {"source_equipment": "", "source_field": "level", "scale": 1.0, "offset": 0.0},
        "parameters": {"source_equipment": {"label": "Équipement mesuré (identifiant)", "type": "string"}, "source_field": {"label": "Grandeur mesurée", "type": "string"}, "scale": number("Échelle", -1e9, 1e9), "offset": number("Décalage", -1e9, 1e9)},
        "ports": {"value": port("Mesure simulée", "input", ["REAL", "INT", "DINT"], required=True)},
        "faults": ["sensor_stuck", "out_of_range"],
    },
    {
        "type": "digital_sensor", "label": "Capteur binaire", "description": "Comparaison d'une mesure de procédé à un seuil configurable.",
        "default_params": {"source_equipment": "", "source_field": "level", "operator": "ge", "threshold": 90.0},
        "parameters": {"source_equipment": {"label": "Équipement mesuré (identifiant)", "type": "string"}, "source_field": {"label": "Grandeur mesurée", "type": "string"}, "operator": {"label": "Comparaison", "type": "select", "options": ["ge", "gt", "le", "lt", "eq", "ne"]}, "threshold": number("Seuil", -1e9, 1e9)},
        "ports": {"value": port("État capteur simulé", "input", ["BOOL"], required=True)},
        "faults": ["sensor_stuck"],
    },
    {
        "type": "indicator", "label": "Indicateur PLC", "description": "Affiche une variable lue dans le PLC ; n'écrit aucune valeur.",
        "default_params": {}, "parameters": {},
        "ports": {"value": port("État PLC", "output", ["BOOL", "INT", "DINT", "REAL"], required=True)},
        "faults": [],
    },
]

CATALOG_BY_TYPE = {item["type"]: item for item in CATALOG}
STATE_FIELDS = {
    "tank": {"level", "level_percent", "volume", "volume_l", "capacity_l", "inflow_l_s", "outflow_l_s", "overflow_l", "high", "low"},
    "pump": {"running", "speed", "flow_l_s", "fault"},
    "valve_onoff": {"position", "open", "closed", "flow_l_s", "stuck"},
    "valve_control": {"position", "open", "closed", "flow_l_s", "stuck"},
    "analog_sensor": {"value"}, "digital_sensor": {"value"}, "indicator": {"value"},
}


def parameters(equipment) -> dict:
    """Return resolved parameters without mutating the versioned project."""
    return {**CATALOG_BY_TYPE[equipment.type]["default_params"], **equipment.params}
