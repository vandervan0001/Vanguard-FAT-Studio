"""Public I/O laboratory: manual requests, simulated plant and a passive PLC bridge.

There is no automatic process sequence, customer standard or reusable motor/valve
control library here. The explicit demo adapter mirrors the small public OB1.
"""
from __future__ import annotations

from .demo_contract import DB_NAME, DEMO_TAGS, PUMPS, TANKS, VALVES
from .models import Project, validate_value


def _force(time, target, value):
    return dict(at_s=float(time), action="force", target=target, value=value)


def _release(time, *targets):
    return [dict(at_s=float(time), action="release", target=target) for target in targets]


def _expect(time, target, value, operator="eq", tolerance=.1):
    return dict(at_s=float(time), action="expect", target=target, value=value, operator=operator, tolerance=tolerance)


def _scenario(id, name, duration, steps, focus, trends, description):
    return dict(id=id, name=name, description=description, duration_s=float(duration),
                requirement="DEMO · Vérifier les échanges et le modèle de procédé", execution_mode="timed",
                preconditions="Nouvel essai, demandes manuelles relâchées, arrêt relâché. PLC de démo passif activé uniquement sur une CPU virtuelle isolée.",
                focus_equipment=focus, trend_tags=trends, steps=sorted(steps, key=lambda row: row["at_s"]))


def demo_scenarios() -> list[dict]:
    scenarios = [
        _scenario("demo-fill-source", "01 · Alimentation de la cuve source", 7, [
            _force(0, "p101_request", True), _force(0, "p101_requested_speed", 70.0), _force(0, "xv101_request", True),
            _expect(1, "p101_command", True), _expect(1, "p101_running", True),
            _expect(4, "tk101_volume", 730.0, "gt"),
            *_release(5, "p101_request", "p101_requested_speed", "xv101_request"),
            _expect(6.5, "p101_running", False),
        ], ["TK101", "P101", "XV101"], ["tk101_volume", "p101_command", "p101_speed"],
           "Les demandes manuelles traversent le PLC ; l'ouverture et la vitesse déterminent le débit simulé."),
        _scenario("demo-transfer-1", "02 · Transfert source vers cuve intermédiaire", 6, [
            _force(0, "p201_request", True), _force(0, "p201_requested_speed", 100.0), _force(0, "xv201_request", True),
            _expect(1, "p201_command", True), _expect(3.5, "tk101_volume", 700.0, "lt"),
            _expect(3.5, "tk201_volume", 475.0, "gt"),
            *_release(4, "p201_request", "p201_requested_speed", "xv201_request"),
            _expect(5, "p201_command", False),
        ], ["TK101", "P201", "XV201", "TK201"], ["tk101_volume", "tk201_volume", "p201_command"],
           "Le volume débité de la source est crédité à la destination. Aucun transfert automatique n'est programmé."),
        _scenario("demo-transfer-2", "03 · Transfert vers la cuve de réception", 6, [
            _force(0, "p202_request", True), _force(0, "p202_requested_speed", 80.0), _force(0, "xv202_request", True),
            _expect(1, "p202_running", True), _expect(3.5, "tk201_volume", 430.0, "lt"),
            _expect(3.5, "tk301_volume", 200.0, "gt"),
            *_release(4, "p202_request", "p202_requested_speed", "xv202_request"),
            _expect(5, "p202_command", False),
        ], ["TK201", "P202", "XV202", "TK301"], ["tk201_volume", "tk301_volume", "p202_speed"],
           "Les trois cuves restent indépendantes des traits graphiques ; le circuit déclare sa source et sa destination."),
        _scenario("demo-drain", "04 · Vidange et vanne de réglage", 6, [
            _force(0, "p301_request", True), _force(0, "p301_requested_speed", 100.0),
            _force(0, "xv301_request", True), _force(0, "fcv302_request", 50.0),
            _expect(1.5, "fcv302_position", 49.0, "gt"), _expect(3.5, "tk301_volume", 160.0, "lt"),
            *_release(4, "p301_request", "p301_requested_speed", "xv301_request", "fcv302_request"),
            _expect(5, "p301_command", False),
        ], ["TK301", "P301", "XV301", "FCV302"], ["tk301_volume", "fcv302_position", "p301_command"],
           "La pompe et les deux vannes sont en série ; le plus petit débit disponible limite le circuit."),
        _scenario("demo-stop", "05 · Contact d'arrêt du démonstrateur", 6, [
            _force(0, "p101_request", True), _force(0, "xv101_request", True),
            _expect(1, "p101_command", True), _force(2, "stop_healthy", False),
            _expect(3, "p101_command", False), _expect(3, "p101_running", False),
            *_release(3.5, "p101_request", "xv101_request"), *_release(4, "stop_healthy"),
            _expect(5, "p101_command", False),
        ], ["P101", "XV101"], ["stop_healthy", "p101_command", "p101_running"],
           "Le contact de démo inhibe les commandes. Les demandes sont relâchées avant de rétablir ce contact ; aucun réarmement métier ou fonction de sécurité n'est simulé."),
        _scenario("demo-pump-fault", "06 · Défaut physique de pompe", 5, [
            _force(0, "p201_request", True), _force(0, "xv201_request", True),
            dict(at_s=1.5, action="fault", target="P201", value=dict(kind="motor_trip")),
            _expect(2.2, "p201_fault", True), _expect(2.2, "p201_running", False),
            _expect(2.2, "p201_command", True),
            *_release(3, "p201_request", "xv201_request"),
            dict(at_s=3.5, action="clear_fault", target="P201"),
            _expect(4.2, "p201_fault", False), _expect(4.2, "p201_running", False),
        ], ["P201", "TK101", "TK201"], ["p201_command", "p201_running", "p201_fault"],
           "Le PLC passif conserve la demande ; le défaut du modèle coupe le retour et le débit. Cette différence commande/retour est attendue."),
        _scenario("demo-valve-stuck", "07 · Vanne bloquée et débit nul", 5, [
            dict(at_s=0.0, action="fault", target="XV201", value=dict(kind="valve_stuck", value=0.0)),
            _force(0, "p201_request", True), _force(0, "xv201_request", True),
            _expect(2, "xv201_open", False), _expect(3, "tk101_volume", 720.0),
            _expect(3, "tk201_volume", 450.0),
            *_release(3.5, "p201_request", "xv201_request"),
            dict(at_s=4.0, action="clear_fault", target="XV201"),
        ], ["TK101", "P201", "XV201", "TK201"], ["tk101_volume", "tk201_volume", "xv201_command", "xv201_open"],
           "Une vanne en série maintenue fermée bloque le transfert, même si le moteur tourne."),
        _scenario("demo-analog", "08 · Échelles analogiques et défaut de signal", 5, [
            _force(0, "lt101_raw", 13824), _expect(.5, "lt101_percent", 50.0),
            dict(at_s=1.5, action="fault", target="LT201", value=dict(kind="out_of_range", value=30000)),
            _expect(2.2, "lt201_percent", 100.0, "gt"),
            dict(at_s=3.0, action="clear_fault", target="LT201"), *_release(3, "lt101_raw"),
            _expect(4, "lt101_percent", 60.0), _expect(4, "lt201_percent", 25.0),
        ], ["LT101", "LT201"], ["lt101_raw", "lt101_percent", "lt201_raw", "lt201_percent"],
           "La conversion linéaire est illustrée, sans alarme ou substitution métier. Une valeur hors plage et sa qualité restent visibles."),
    ]
    scenarios.append(dict(id="demo-guided-io", name="09 · FAT manuelle pas à pas", execution_mode="guided", duration_s=120.0,
        requirement="DEMO-GUIDED · Stimuli groupés, résultat attendu et observation", description="Préparer les écritures, exécuter un STEP puis consigner ce qui a été observé.",
        preconditions="Nouveau modèle, cuves à leurs niveaux initiaux, demandes relâchées ; PLC de démo passif sur une cible virtuelle isolée.",
        focus_equipment=["TK101", "LT101", "P101", "XV101"], trend_tags=["lt101_raw", "lt101_percent", "p101_command", "p101_speed"],
        fat_steps=[
            dict(id="guided-initial", name="Vérifier le niveau à 12 mA", instructions="Appliquer, attendre deux cycles d'échange puis comparer les valeurs.",
                 expected_result="LT-101 = 50 %, P-101 non commandée.",
                 actions=[dict(target="p101_request", value=False), dict(target="stop_healthy", value=True), dict(target="lt101_raw", value=12.0, unit="mA")],
                 checks=[dict(target="lt101_percent", value=50.0, tolerance=.1), dict(target="p101_command", value=False)]),
            dict(id="guided-run", name="Demander une marche à 50 %", instructions="Ouvrir l'arrivée et appliquer la demande manuelle de pompe.",
                 expected_result="La commande P-101 vaut TRUE, la consigne vaut 50 %, puis le retour marche apparaît.",
                 actions=[dict(target="xv101_request", value=True), dict(target="p101_requested_speed", value=50.0, unit="percent"), dict(target="p101_request", value=True)],
                 checks=[dict(target="p101_command", value=True), dict(target="p101_speed_command", value=50.0, tolerance=.1), dict(target="p101_running", value=True)]),
            dict(id="guided-stop", name="Ouvrir le contact d'arrêt", instructions="Conserver les demandes et ouvrir le contact de démo.",
                 expected_result="Les commandes de pompe et vanne passent à FALSE ; le retour marche disparaît après la réponse simulée.",
                 actions=[dict(target="stop_healthy", value=False)], checks=[dict(target="p101_command", value=False), dict(target="xv101_command", value=False), dict(target="p101_running", value=False)]),
            dict(id="guided-requests-off", name="Relâcher les demandes", instructions="Couper les demandes avant de rétablir le contact.",
                 expected_result="P-101 reste non commandée.", actions=[dict(target="p101_request", value=False), dict(target="xv101_request", value=False)],
                 checks=[dict(target="p101_command", value=False)]),
            dict(id="guided-release", name="Libérer les stimuli", instructions="Revenir aux entrées physiques simulées ; aucune conclusion FAT n'est renseignée automatiquement.",
                 expected_result="Les commandes restent FALSE et LT-101 reprend le niveau du modèle.",
                 actions=[dict(action="release", target=id) for id in ["p101_request", "xv101_request", "p101_requested_speed", "stop_healthy", "lt101_raw"]],
                 checks=[dict(target="p101_command", value=False), dict(target="xv101_command", value=False)]),
        ]))
    return scenarios


def demo_lab_project() -> Project:
    tags = []
    for id, (field, direction, kind, initial, unit, low, high) in DEMO_TAGS.items():
        tag = dict(id=id, name=field, direction=direction, data_type=kind, initial_value=initial,
                   unit=unit, min=low, max=high, writable=direction == "input", plc_symbol=f'{DB_NAME}.{field}')
        if id.endswith("_raw"):
            tag["signal"] = dict(kind="4-20mA", raw_min=0.0, raw_max=27648.0, engineering_min=0.0,
                                 engineering_max=100.0, engineering_unit="%", underflow_raw=-32768.0, overflow_raw=32767.0)
        elif direction == "input" and kind == "REAL" and unit == "%":
            tag["signal"] = dict(kind="linear", raw_min=0.0, raw_max=100.0, engineering_min=0.0, engineering_max=100.0, engineering_unit="%")
        elif direction == "input" and kind == "REAL" and unit == "L":
            tag["signal"] = dict(kind="linear", raw_min=float(low), raw_max=float(high),
                                 engineering_min=float(low), engineering_max=float(high), engineering_unit="L")
        tags.append(tag)
    equipment = []
    def add(id, kind, name, x, y, params, bindings, animation=None, description=""):
        equipment.append(dict(id=id, type=kind, name=name, position=dict(x=x, y=y), params=params,
                              bindings=bindings, animation=animation, description=description))
    for tank in TANKS:
        number = tank["id"][2:]
        add(tank["id"], "tank", tank["name"], tank["x"], tank["y"],
            dict(capacity_l=tank["capacity_l"], initial_level_pct=tank["initial_level_pct"]), {"volume": f"tk{number}_volume"},
            dict(tag_id=f"lt{number}_percent", operator="ge", value=0.0, effect="level"))
        add(f"LT{number}", "analog_sensor", f"LT-{number} · 4–20 mA", tank["x"] - 190, tank["y"] - 100,
            dict(source_equipment=tank["id"], source_field="level", scale=276.48, offset=0.0),
            {"value": f"lt{number}_raw", "scaled_value": f"lt{number}_percent"})
        for kind, operator, threshold, delta in [("LSL", "le", 10.0, 70), ("LSH", "ge", 90.0, -90)]:
            id = f"{kind}{number}"
            add(id, "digital_sensor", f"{kind}-{number}", tank["x"] + 190, tank["y"] + delta,
                dict(source_equipment=tank["id"], source_field="level", operator=operator, threshold=threshold), {"value": id.lower()})
    for pump in PUMPS:
        prefix = pump["id"].lower()
        params = {key: pump[key] for key in ("tank_id", "role", "flow_group", "source_tank_id", "max_flow_l_s")}
        params["response_s"] = .2
        add(pump["id"], "pump_vfd", pump["name"], pump["x"], pump["y"], params,
            dict(command=f"{prefix}_command", speed_command=f"{prefix}_speed_command", feedback=f"{prefix}_running", speed=f"{prefix}_speed", fault=f"{prefix}_fault",
                 manual_request=f"{prefix}_request", manual_speed=f"{prefix}_requested_speed"),
            dict(tag_id=f"{prefix}_running", value=True, effect="rotate"))
    for valve in VALVES:
        prefix = valve["id"].lower()
        params = {key: valve[key] for key in ("tank_id", "role", "flow_group", "max_flow_l_s")}
        params["response_s"] = .2
        modulating = valve["id"].startswith("FCV")
        bindings = dict(command=f"{prefix}_command", manual_request=f"{prefix}_request")
        if modulating:
            bindings["position"] = f"{prefix}_position"
        else:
            bindings.update(open=f"{prefix}_open", closed=f"{prefix}_closed")
        add(valve["id"], "valve_control" if modulating else "valve_onoff", valve["name"], valve["x"], valve["y"], params, bindings,
            dict(tag_id=f"{prefix}_position", operator="gt", value=0.0, effect="position") if modulating else dict(tag_id=f"{prefix}_open", value=True, effect="highlight"),
            "Évent graphique sans bilan de pression." if valve["id"] == "XV103" else "")
    for id in ["stop_healthy", *[id for id in DEMO_TAGS if id.endswith("_request") and DEMO_TAGS[id][2] == "BOOL"]]:
        field = DEMO_TAGS[id][0]
        add(f"IO_{id}", "digital_input", field, 50.0 + (len(equipment) % 8) * 210, 1000.0,
            dict(initial_value=DEMO_TAGS[id][3]), {"value": id})
    links = [("P101", "XV101", "Alimentation"), ("XV101", "TK101", "Eau de démonstration"),
             ("TK101", "P201", "Transfert 1"), ("P201", "XV201", ""), ("XV201", "TK201", ""),
             ("TK201", "P202", "Transfert 2"), ("P202", "XV202", ""), ("XV202", "TK301", ""),
             ("TK301", "P301", "Vidange"), ("P301", "XV301", ""), ("XV301", "FCV302", "Sortie"),
             ("TK101", "XV102", "Purge"), ("TK201", "XV203", "Purge"), ("TK101", "XV103", "Évent")]
    links.extend((tank["id"], f"{instrument}{tank['id'][2:]}", "") for tank in TANKS for instrument in ("LT", "LSL", "LSH"))
    return Project.model_validate(dict(schema_version="1.0", id="public-io-lab", name="FAT LAB · Banc de transfert",
        description="Démonstrateur public : trois cuves, quatre pompes et huit vannes. Demandes manuelles, retours physiques et conversion linéaire ; aucun programme client, standard privé ou séquence métier. La référence Python est utilisée seulement en mode demo ; en OPC UA les commandes proviennent du vrai PLC.",
        plc=dict(mode="demo", demo_controller="manual_lab_v1"), equipment=equipment, tags=tags,
        connections=[dict(id=f"pipe_{index}", source=a, target=b, label=label, directed=True) for index, (a, b, label) in enumerate(links)],
        scenarios=demo_scenarios()))


class ManualLabController:
    """Literal counterpart of the public passive DB/OB1, exclusively in demo mode."""
    def __init__(self, project):
        self.tags = {tag.id: tag for tag in project.tags}
        self.equipment = project.equipment

    def read_commands(self, values, dt):
        result = {id: tag.initial_value for id, tag in self.tags.items() if tag.direction == "output"}
        enabled = values.get("stop_healthy", True)
        for item in self.equipment:
            bindings = item.bindings
            if item.type in ("pump", "pump_vfd", "valve_onoff", "valve_control"):
                requested = values.get(bindings.get("manual_request"), 0.0 if item.type == "valve_control" else False)
                if item.type == "valve_control":
                    result[bindings["command"]] = min(100.0, max(0.0, requested)) if enabled else 0.0
                else:
                    command = enabled and requested
                    result[bindings["command"]] = command
                    if item.type == "pump_vfd":
                        speed = values.get(bindings.get("manual_speed"), 0.0)
                        result[bindings["speed_command"]] = min(100.0, max(0.0, speed)) if command else 0.0
            elif item.type == "analog_sensor" and bindings.get("scaled_value"):
                source = self.tags[bindings["value"]]
                output = self.tags[bindings["scaled_value"]]
                signal = source.signal
                if signal:
                    normalized = validate_value(output, (values[source.id] - signal.raw_min) / (signal.raw_max - signal.raw_min))
                    scaled = signal.engineering_min + normalized * (signal.engineering_max - signal.engineering_min)
                else:
                    scaled = values[source.id]
                result[output.id] = validate_value(output, scaled)
        return {id: validate_value(self.tags[id], value) for id, value in result.items()}
