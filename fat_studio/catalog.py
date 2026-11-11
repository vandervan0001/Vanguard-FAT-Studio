"""Equipment catalogue shared by validation, the editor and the plant model."""

from __future__ import annotations

from .pid_symbols import PID_SYMBOLS


def port(label: str, direction: str, types: list[str], unit: str = "", required: bool = False) -> dict:
    return {"label": label, "direction": direction, "data_types": types, "unit": unit, "required": required}


def number(label: str, low: float, high: float, unit: str = "") -> dict:
    return {"label": label, "type": "number", "min": low, "max": high, "unit": unit}


FLOW_PARAMETERS = {
    "tank_id": {"label": "Cuve associée (identifiant)", "type": "string"},
    "source_tank_id": {"label": "Cuve source du transfert (vide = source extérieure)", "type": "string"},
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

CATALOG.extend([
    {
        "type": "pump_vfd", "label": "Pompe à variateur", "description": "Pompe avec marche et consigne 0–100 %, inertie, retour vitesse et défaut moteur.",
        "default_params": {"tank_id": "", "role": "inlet", "flow_group": "feed", "max_flow_l_s": 80.0, "response_s": 0.4, "initial_speed_pct": 0.0, "demo_control": "level", "demo_command": True, "demo_speed_pct": 60.0},
        "parameters": {**FLOW_PARAMETERS, "initial_speed_pct": number("Vitesse initiale", 0, 100, "%"), "demo_command": {"label": "Démo : commande constante", "type": "boolean"}, "demo_speed_pct": number("Démo : consigne vitesse", 0, 100, "%")},
        "ports": {"command": port("Commande marche PLC", "output", ["BOOL"], required=True), "speed_command": port("Consigne vitesse PLC", "output", ["REAL"], "%", required=True), "feedback": port("Retour marche simulé", "input", ["BOOL"]), "speed": port("Vitesse simulée", "input", ["REAL"], "%"), "fault": port("Défaut moteur simulé", "input", ["BOOL"])},
        "faults": ["motor_trip"],
    },
    {
        "type": "digital_input", "label": "Bouton / entrée TOR", "description": "Contact simulé, actionnable par forçage d’une entrée autorisée ; aucun signal de sécurité certifié.",
        "default_params": {"initial_value": False},
        "parameters": {"initial_value": {"label": "État au repos", "type": "boolean"}},
        "ports": {"value": port("Contact vers PLC", "input", ["BOOL"], required=True)}, "faults": [],
    },
    {
        "type": "valve_three_way", "label": "Vanne trois voies simulée",
        "description": "Répartition linéaire entre trois cuves déclarées. 0 % vers B, 100 % vers A ; mélange ou diversion, sans calcul de pression.",
        "default_params": {"mode": "diverting", "common_tank_id": "", "branch_a_tank_id": "", "branch_b_tank_id": "", "max_flow_l_s": 20.0, "response_s": 0.5, "initial_position_pct": 50.0, "demo_command": 50.0},
        "parameters": {
            "mode": {"label": "Fonction", "type": "select", "options": ["diverting", "mixing"]},
            "common_tank_id": {"label": "Cuve commune AB", "type": "string"},
            "branch_a_tank_id": {"label": "Cuve de branche A", "type": "string"},
            "branch_b_tank_id": {"label": "Cuve de branche B", "type": "string"},
            "max_flow_l_s": number("Débit total nominal AB", 0, 100000, "L/s"),
            "response_s": number("Constante de réponse", 0, 120, "s"),
            "initial_position_pct": number("Position initiale vers A", 0, 100, "%"),
            "demo_command": number("Démo : position vers A", 0, 100, "%"),
        },
        "ports": {
            "command": port("Consigne PLC vers A (0 = B, 100 = A)", "output", ["REAL"], "%", required=True),
            "position": port("Position simulée vers A", "input", ["REAL"], "%"),
            "flow_a": port("Débit réel de branche A", "input", ["REAL"], "L/s"),
            "flow_b": port("Débit réel de branche B", "input", ["REAL"], "L/s"),
            "feedback_a": port("Fin de course vers A", "input", ["BOOL"]),
            "feedback_b": port("Fin de course vers B", "input", ["BOOL"]),
        },
        "faults": ["valve_stuck"],
    },
    {
        "type": "heat_exchanger", "label": "Échangeur simulé",
        "description": "Deux volumes parfaitement mélangés échangent de la chaleur par UA. Circuits isolés, fluides monophasiques et conditions d'entrée déclarées.",
        "default_params": {
            "primary_inlet_temperature_c": 80.0, "secondary_inlet_temperature_c": 20.0,
            "primary_flow_l_s": 2.0, "secondary_flow_l_s": 2.0,
            "primary_volume_l": 20.0, "secondary_volume_l": 20.0,
            "primary_density_kg_l": 1.0, "secondary_density_kg_l": 1.0,
            "primary_cp_kj_kg_k": 4.18, "secondary_cp_kj_kg_k": 4.18,
            "initial_primary_temperature_c": 80.0, "initial_secondary_temperature_c": 20.0,
            "ua_kw_k": 5.0,
            "primary_flow_equipment": "", "secondary_flow_equipment": "",
            "primary_flow_field": "flow_l_s", "secondary_flow_field": "flow_l_s",
        },
        "parameters": {
            "primary_inlet_temperature_c": number("Primaire : température d'entrée", -100, 500, "°C"),
            "secondary_inlet_temperature_c": number("Secondaire : température d'entrée", -100, 500, "°C"),
            "primary_flow_l_s": number("Primaire : débit imposé sans source", 0, 100000, "L/s"),
            "secondary_flow_l_s": number("Secondaire : débit imposé sans source", 0, 100000, "L/s"),
            "primary_volume_l": number("Primaire : volume interne", 0.001, 1e6, "L"),
            "secondary_volume_l": number("Secondaire : volume interne", 0.001, 1e6, "L"),
            "primary_density_kg_l": number("Primaire : masse volumique", 0.01, 20, "kg/L"),
            "secondary_density_kg_l": number("Secondaire : masse volumique", 0.01, 20, "kg/L"),
            "primary_cp_kj_kg_k": number("Primaire : capacité thermique massique", 0.01, 100, "kJ/(kg·K)"),
            "secondary_cp_kj_kg_k": number("Secondaire : capacité thermique massique", 0.01, 100, "kJ/(kg·K)"),
            "initial_primary_temperature_c": number("Primaire : température initiale", -100, 500, "°C"),
            "initial_secondary_temperature_c": number("Secondaire : température initiale", -100, 500, "°C"),
            "ua_kw_k": number("Conductance globale UA", 0, 1e6, "kW/K"),
            "primary_flow_equipment": {"label": "Primaire : source de débit (facultative)", "type": "string"},
            "secondary_flow_equipment": {"label": "Secondaire : source de débit (facultative)", "type": "string"},
            "primary_flow_field": {"label": "Primaire : débit de la source", "type": "select", "options": ["flow_l_s", "flow_a_l_s", "flow_b_l_s"]},
            "secondary_flow_field": {"label": "Secondaire : débit de la source", "type": "select", "options": ["flow_l_s", "flow_a_l_s", "flow_b_l_s"]},
        },
        "ports": {
            "primary_flow_command": port("Primaire : débit imposé par PLC", "output", ["REAL"], "L/s"),
            "secondary_flow_command": port("Secondaire : débit imposé par PLC", "output", ["REAL"], "L/s"),
            "primary_inlet_command": port("Primaire : température d'entrée imposée par PLC", "output", ["REAL"], "°C"),
            "secondary_inlet_command": port("Secondaire : température d'entrée imposée par PLC", "output", ["REAL"], "°C"),
            "primary_temperature": port("Primaire : température de sortie simulée", "input", ["REAL"], "°C"),
            "secondary_temperature": port("Secondaire : température de sortie simulée", "input", ["REAL"], "°C"),
            "heat": port("Puissance primaire vers secondaire", "input", ["REAL"], "kW"),
            "primary_flow": port("Primaire : débit simulé", "input", ["REAL"], "L/s"),
            "secondary_flow": port("Secondaire : débit simulé", "input", ["REAL"], "L/s"),
        },
        "faults": ["fouling"],
    },
])

# Optional operator requests are exchange inputs, not physical signal producers.
# They may share a tag with an explicit pushbutton without duplicating a sensor.
for _item in CATALOG:
    if _item["type"] in ("pump", "pump_vfd", "valve_onoff", "valve_control", "valve_three_way"):
        _kind = "REAL" if _item["type"] in ("valve_control", "valve_three_way") else "BOOL"
        _request = port("Demande manuelle simulée", "input", [_kind], "%" if _kind == "REAL" else "")
        _request["simulated_source"] = False
        _item["ports"]["manual_request"] = _request
        if _item["type"] == "pump_vfd":
            _speed = port("Consigne manuelle simulée", "input", ["REAL"], "%")
            _speed["simulated_source"] = False
            _item["ports"]["manual_speed"] = _speed

CATALOG.append({
    "type": "pid_symbol", "label": "Symbole P&ID documentaire",
    "description": "Équipement dessiné avec ses piquages, sans modèle physique ni variable PLC produite.",
    "default_params": {}, "parameters": {}, "ports": {}, "faults": [],
    "simulation": False, "symbols": PID_SYMBOLS,
})
CATALOG_BY_TYPE = {item["type"]: item for item in CATALOG}
CATALOG_BY_TYPE["analog_sensor"]["ports"]["scaled_value"] = port("Valeur d'ingénierie lue du PLC", "output", ["REAL"])
STATE_FIELDS = {
    "tank": {"level", "level_percent", "volume", "volume_l", "capacity_l", "inflow_l_s", "outflow_l_s", "overflow_l", "high", "low"},
    "pump": {"running", "speed", "flow_l_s", "fault"},
    "pump_vfd": {"running", "speed", "flow_l_s", "fault"},
    "valve_onoff": {"position", "open", "closed", "flow_l_s", "stuck"},
    "valve_control": {"position", "open", "closed", "flow_l_s", "stuck"},
    "valve_three_way": {"position", "to_a", "to_b", "flow_l_s", "flow_a_l_s", "flow_b_l_s", "stuck"},
    "heat_exchanger": {"primary_outlet_temperature_c", "secondary_outlet_temperature_c", "primary_inlet_temperature_c", "secondary_inlet_temperature_c", "primary_flow_l_s", "secondary_flow_l_s", "heat_kw", "ua_effective_kw_k", "fouled"},
    "analog_sensor": {"value"}, "digital_sensor": {"value"}, "indicator": {"value"}, "digital_input": {"value"},
    "pid_symbol": set(),
}


def parameters(equipment) -> dict:
    """Return resolved parameters without mutating the versioned project."""
    return {**CATALOG_BY_TYPE[equipment.type]["default_params"], **equipment.params}
