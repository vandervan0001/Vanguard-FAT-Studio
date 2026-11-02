"""A complete, versionable FAT example with all seven catalogue symbols."""

from __future__ import annotations

from .models import Project


def demo_project() -> Project:
    def tag(id, name, direction, data_type, initial, unit="", low=None, high=None):
        return {"id": id, "name": name, "direction": direction, "data_type": data_type, "initial_value": initial, "unit": unit, "min": low, "max": high, "writable": direction == "input", "node_id": f'ns=3;s="DB_FAT"."{name}"'}

    def equipment(id, kind, name, x, y, params, bindings, description="", unit=""):
        return {"id": id, "type": kind, "name": name, "position": {"x": x, "y": y}, "params": params, "bindings": bindings, "description": description, "unit": unit}

    return Project.model_validate({
        "schema_version": "1.0",
        "id": "tank-demo",
        "name": "TK-101 · Banc de remplissage",
        "description": "Cuve 1 000 L, alimentation P-101/XV-101 en série, soutirage FCV-101, mesure LT-101 et seuils haut/bas. Démonstration autonome : un contrôleur fictif remplit entre 30 et 70 %. En mode OPC UA, seul le programme PLC connecté produit les commandes. Les NodeIds d'exemple doivent être remplacés par ceux observés sur votre CPU virtuelle.",
        "simulation": {"step_ms": 100, "speed": 1},
        "plc": {"mode": "demo"},
        "equipment": [
            equipment("TK101", "tank", "TK-101", 470, 190, {"capacity_l": 1000.0, "initial_level_pct": 25.0, "high_level_pct": 90.0, "low_level_pct": 10.0}, {"volume": "volume"}, "Cuve à section constante ; débordement comptabilisé, volume borné.", "L"),
            equipment("P101", "pump", "P-101", 40, 230, {"tank_id": "TK101", "role": "inlet", "flow_group": "feed", "max_flow_l_s": 30.0, "response_s": 0.4}, {"command": "pump_cmd", "feedback": "pump_running", "fault": "pump_fault"}, "Alimentation ; 30 L/s à pleine vitesse."),
            equipment("XV101", "valve_onoff", "XV-101", 250, 230, {"tank_id": "TK101", "role": "inlet", "flow_group": "feed", "max_flow_l_s": 25.0, "response_s": 0.3}, {"command": "inlet_cmd", "position": "inlet_position", "open": "inlet_open", "closed": "inlet_closed"}, "Vanne d'isolement de l'alimentation ; limite du circuit à 25 L/s."),
            equipment("FCV101", "valve_control", "FCV-101", 760, 230, {"tank_id": "TK101", "role": "outlet", "flow_group": "drain", "max_flow_l_s": 12.0, "response_s": 0.5, "characteristic": "linear", "demo_control": "constant", "demo_command": 35.0}, {"command": "outlet_cmd", "position": "outlet_position"}, "Soutirage 4,2 L/s à 35 % d'ouverture.", "%"),
            equipment("LT101", "analog_sensor", "LT-101", 470, 10, {"source_equipment": "TK101", "source_field": "level", "scale": 1.0, "offset": 0.0}, {"value": "level"}, "Transmetteur de niveau 0–100 %.", "%"),
            equipment("LSH101", "digital_sensor", "LSH-101", 700, 10, {"source_equipment": "TK101", "source_field": "level", "operator": "ge", "threshold": 90.0}, {"value": "high"}, "Détection niveau haut ≥ 90 %."),
            equipment("LSL101", "digital_sensor", "LSL-101", 910, 10, {"source_equipment": "TK101", "source_field": "level", "operator": "le", "threshold": 10.0}, {"value": "low"}, "Détection niveau bas ≤ 10 %."),
            equipment("RUN101", "indicator", "Commande P-101", 40, 10, {}, {"value": "pump_cmd"}, "Observation de la commande PLC, sans écriture."),
        ],
        "connections": [
            {"id": "feed_pump_valve", "source": "P101", "target": "XV101", "label": "Alimentation", "directed": True},
            {"id": "feed_valve_tank", "source": "XV101", "target": "TK101", "label": "25 L/s max.", "directed": True},
            {"id": "drain_tank_valve", "source": "TK101", "target": "FCV101", "label": "Soutirage", "directed": True},
            {"id": "level_measurement", "source": "TK101", "target": "LT101", "label": "Niveau", "directed": False},
        ],
        "tags": [
            tag("pump_cmd", "PumpCmd", "output", "BOOL", False),
            tag("inlet_cmd", "InletCmd", "output", "BOOL", False),
            tag("outlet_cmd", "OutletCmd", "output", "REAL", 0.0, "%", 0, 100),
            tag("level", "LevelPct", "input", "REAL", 25.0, "%", 0, 100),
            tag("volume", "VolumeL", "input", "REAL", 250.0, "L", 0, 1000),
            tag("pump_running", "PumpRunning", "input", "BOOL", False),
            tag("pump_fault", "PumpFault", "input", "BOOL", False),
            tag("inlet_position", "InletPosition", "input", "REAL", 0.0, "%", 0, 100),
            tag("inlet_open", "InletOpen", "input", "BOOL", False),
            tag("inlet_closed", "InletClosed", "input", "BOOL", True),
            tag("outlet_position", "OutletPosition", "input", "REAL", 0.0, "%", 0, 100),
            tag("high", "LevelHigh", "input", "BOOL", False),
            tag("low", "LevelLow", "input", "BOOL", False),
        ],
        "scenarios": [
            {
                "id": "reference", "name": "01 · Cycle de référence", "duration_s": 32,
                "description": "Remplir la cuve depuis 25 %, constater la marche et l'augmentation du niveau puis l'arrêt à 70 %. Les seuils d'assertion sont adaptés au contrôleur de démonstration ; les adapter au programme PLC réel.",
                "steps": [
                    {"at_s": 0, "action": "marker", "message": "Début du cycle de référence, cuve initiale 25 %."},
                    {"at_s": 5, "action": "expect", "target": "pump_running", "value": True, "message": "La pompe retourne sa marche."},
                    {"at_s": 10, "action": "expect", "target": "level", "operator": "gt", "value": 35.0, "message": "Le niveau augmente réellement."},
                    {"at_s": 25, "action": "expect", "target": "pump_cmd", "value": False, "message": "Arrêt de remplissage après le seuil haut de contrôle."},
                    {"at_s": 30, "action": "expect", "target": "level", "operator": "gt", "value": 60.0, "message": "Le soutirage reste limité après l'arrêt."},
                    {"at_s": 32, "action": "marker", "message": "Fin de scénario : relever le résultat de la FAT."},
                ],
            },
            {
                "id": "motor-trip", "name": "02 · Défaut moteur et reprise", "duration_s": 28,
                "description": "Déclenchement moteur à 5 s, contrôle retour et défaut, suppression à 15 s puis observation de la reprise.",
                "steps": [
                    {"at_s": 0, "action": "marker", "message": "Vérification du défaut moteur P-101."},
                    {"at_s": 5, "action": "fault", "target": "P101", "value": {"kind": "motor_trip"}},
                    {"at_s": 6, "action": "expect", "target": "pump_running", "value": False, "message": "Perte du retour marche."},
                    {"at_s": 6, "action": "expect", "target": "pump_fault", "value": True, "message": "Défaut transmis au PLC."},
                    {"at_s": 10, "action": "expect", "target": "level", "operator": "lt", "value": 40.0, "message": "Aucun remplissage caché pendant le défaut."},
                    {"at_s": 15, "action": "clear_fault", "target": "P101"},
                    {"at_s": 17, "action": "expect", "target": "pump_running", "value": True, "message": "Reprise après disparition du défaut."},
                    {"at_s": 25, "action": "expect", "target": "level", "operator": "gt", "value": 40.0, "message": "Reprise du remplissage observable."},
                ],
            },
            {
                "id": "sensor-freeze", "name": "03 · Capteur figé puis libéré", "duration_s": 24,
                "description": "Figer LT-101 à 40 %, constater la mesure fixe, puis libérer le capteur. Le volume réel continue d'évoluer pendant le défaut.",
                "steps": [
                    {"at_s": 5, "action": "fault", "target": "LT101", "value": {"kind": "sensor_stuck", "value": 40.0}},
                    {"at_s": 10, "action": "expect", "target": "level", "value": 40.0, "message": "Mesure figée à 40 %."},
                    {"at_s": 14, "action": "expect", "target": "volume", "operator": "gt", "value": 450.0, "message": "Le procédé continue d'évoluer malgré la mesure figée."},
                    {"at_s": 15, "action": "clear_fault", "target": "LT101"},
                    {"at_s": 16, "action": "expect", "target": "level", "operator": "gt", "value": 50.0, "message": "Retour à la mesure du procédé."},
                ],
            },
        ],
    })
