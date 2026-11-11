"""Inert P&ID drawing primitives, independent of simulation and PLC signals.

The vocabulary follows the attributed Scott Duncan ontology where applicable.
Historical geometry is original; four general representations are adapted from
the attributed MIT-licensed pyflowsheet project. Neither is a claim of certified
ISA/ISO/DEXPI conformity. Instrument codes describe functions, not PLC mappings.
All coordinates use a 100 by 100 drawing box. Ports describe drawing terminals;
they do not establish pressure, flow, mixing, heat transfer or a safety function.
"""

from __future__ import annotations

from copy import deepcopy
from math import cos, radians, sin
import re
import unicodedata

_INK = "#23465c"
_FILL = "#eef5fb"


def _line(*points: tuple[int, int]) -> dict:
    return {"kind": "polyline", "points": [list(point) for point in points], "stroke": _INK, "width": 1.8}


def _polygon(*points: tuple[int, int]) -> dict:
    return {"kind": "polygon", "points": [list(point) for point in points], "stroke": _INK, "fill": _FILL, "width": 1.8}


def _rect(x: int, y: int, width: int, height: int) -> dict:
    return {"kind": "rect", "x": x, "y": y, "width": width, "height": height, "stroke": _INK, "fill": _FILL}


def _circle(x: int, y: int, radius: int) -> dict:
    return {"kind": "circle", "x": x, "y": y, "radius": radius, "stroke": _INK, "fill": _FILL, "width": 1.8}


def _ellipse(x: int, y: int, rx: int, ry: int) -> dict:
    return {"kind": "ellipse", "x": x, "y": y, "rx": rx, "ry": ry, "stroke": _INK, "fill": _FILL, "width": 1.8}


def _port(identifier: str, label: str, x: int, y: int, direction: str = "bidirectional") -> dict:
    return {"id": identifier, "label": label, "x": x, "y": y, "direction": direction}


_TWO_PORTS = [_port("in", "Raccord 1", 0, 50), _port("out", "Raccord 2", 100, 50)]
_THREE_PORTS = [_port("feed", "Alimentation", 0, 50, "in"),
                _port("out_1", "Sortie 1", 100, 35, "out"), _port("out_2", "Sortie 2", 100, 75, "out")]
_THERMAL_PORTS = [_port("primary_in", "Circuit primaire · entrée", 0, 35, "in"),
                  _port("primary_out", "Circuit primaire · sortie", 100, 35, "out"),
                  _port("secondary_in", "Circuit secondaire · entrée", 0, 75, "in"),
                  _port("secondary_out", "Circuit secondaire · sortie", 100, 75, "out")]
_ENDS = [_line((0, 50), (25, 50)), _line((75, 50), (100, 50))]
_VALVE = [*_ENDS, _polygon((25, 32), (75, 68), (75, 32), (25, 68))]
_HANDWHEEL = [_line((50, 50), (50, 18)), _line((35, 18), (65, 18))]
_TANK = [_rect(25, 20, 50, 60), _ellipse(50, 20, 25, 8), _ellipse(50, 80, 25, 8), *_ENDS]
_THERMAL_ENDS = [_line((0, 35), (20, 35)), _line((80, 35), (100, 35)),
                 _line((0, 75), (20, 75)), _line((80, 75), (100, 75))]
_HEX = [_rect(20, 20, 60, 70), *_THERMAL_ENDS,
        _line((20, 35), (38, 35), (38, 55), (62, 55), (62, 35), (80, 35)),
        _line((20, 75), (32, 75), (32, 65), (68, 65), (68, 75), (80, 75))]


def _symbol(identifier: str, label: str, category: str, prefix: str, description: str,
            shapes: list[dict], ports: list[dict] | None = None) -> dict:
    return {"id": identifier, "label": label, "category": category, "prefix": prefix,
            "description": description + " Symbole documentaire, sans modèle physique ni association PLC.",
            "simulation": False, "ports": deepcopy(_TWO_PORTS if ports is None else ports),
            "shapes": deepcopy(shapes)}


PID_SYMBOLS = [
    _symbol("tank", "Cuve atmosphérique", "Réservoirs et procédé", "TK", "Réservoir de stockage.", _TANK),
    _symbol("vessel", "Ballon de procédé", "Réservoirs et procédé", "V", "Enceinte de procédé sans pression calculée.",
            [_rect(28, 28, 44, 44), _ellipse(50, 28, 22, 16), _ellipse(50, 72, 22, 16), *_ENDS]),
    _symbol("pressure_vessel", "Réservoir sous pression", "Réservoirs et procédé", "V", "Enceinte sous pression représentée au dessin.",
            [_rect(28, 25, 44, 50), _ellipse(50, 25, 22, 15), _ellipse(50, 75, 22, 15), *_ENDS,
             _line((20, 22), (20, 78)), _line((80, 22), (80, 78))]),
    _symbol("agitated_tank", "Cuve agitée", "Réservoirs et procédé", "TK", "Cuve avec agitateur.",
            [*_TANK, _rect(42, 0, 16, 12), _line((50, 12), (50, 65)), _line((33, 58), (67, 68)), _line((33, 68), (67, 58))]),
    _symbol("reactor", "Réacteur", "Réservoirs et procédé", "R", "Réacteur avec jaquette représentée, sans réaction calculée.",
            [*_TANK, _line((18, 28), (18, 76), (25, 76)), _line((82, 28), (82, 76), (75, 76)),
             _line((50, 5), (50, 65)), _line((37, 60), (63, 60))]),
    _symbol("column", "Colonne", "Réservoirs et procédé", "C", "Colonne à plateaux ou à garnissage.",
            [_rect(35, 8, 30, 84), _line((35, 25), (60, 25)), _line((40, 42), (65, 42)),
             _line((35, 59), (60, 59)), _line((40, 76), (65, 76)), _line((0, 50), (35, 50)),
             _line((50, 0), (50, 8)), _line((50, 92), (50, 100))],
            [_port("feed", "Alimentation", 0, 50, "in"), _port("top", "Tête", 50, 0, "out"), _port("bottom", "Fond", 50, 100, "out")]),
    _symbol("separator", "Séparateur", "Réservoirs et procédé", "V", "Séparation à plusieurs sorties représentée au dessin.",
            [_rect(20, 20, 60, 65), _ellipse(50, 20, 30, 8), _line((0, 50), (20, 50)),
             _line((80, 35), (100, 35)), _line((80, 75), (100, 75)), _line((20, 60), (80, 60))], _THREE_PORTS),
    _symbol("heat_exchanger", "Échangeur à calandre et tubes", "Échanges thermiques", "E", "Deux circuits distincts, quatre piquages.", _HEX, _THERMAL_PORTS),
    _symbol("plate_heat_exchanger", "Échangeur à plaques", "Échanges thermiques", "E", "Échangeur à plaques, deux circuits distincts.",
            [_rect(20, 20, 60, 70), *_THERMAL_ENDS, *[_line((x, 25), (x - 8, 85)) for x in (36, 46, 56, 66, 76)]], _THERMAL_PORTS),
    _symbol("heater", "Réchauffeur", "Échanges thermiques", "H", "Chauffage représenté, sans température calculée.",
            [*_ENDS, _rect(25, 25, 50, 50), _line((31, 64), (39, 36), (47, 64), (55, 36), (63, 64), (69, 36))]),
    _symbol("cooler", "Refroidisseur", "Échanges thermiques", "E", "Refroidissement représenté, sans température calculée.",
            [*_ENDS, _rect(25, 25, 50, 50), _line((50, 30), (50, 70)), _line((33, 40), (67, 60)),
             _line((33, 60), (67, 40))]),
    _symbol("condenser", "Condenseur", "Échanges thermiques", "E", "Condenseur à deux circuits, sans changement de phase calculé.",
            [*_HEX, _line((46, 21), (50, 30), (54, 21))], _THERMAL_PORTS),
    _symbol("evaporator", "Évaporateur", "Échanges thermiques", "E", "Évaporateur, sans changement de phase calculé.",
            [*_TANK, _line((35, 65), (40, 45), (45, 65), (50, 45), (55, 65), (60, 45), (65, 65)),
             _line((50, 12), (50, 0)), _line((75, 70), (100, 70))],
            [_port("feed", "Alimentation", 0, 50, "in"), _port("vapor", "Vapeur", 50, 0, "out"), _port("liquid", "Liquide", 100, 70, "out")]),
    _symbol("boiler", "Chaudière", "Échanges thermiques", "B", "Chaudière représentée, sans génération de vapeur calculée.",
            [_rect(20, 20, 60, 65), _line((0, 65), (20, 65)), _line((50, 20), (50, 0)),
             _polygon((38, 75), (43, 53), (50, 64), (57, 45), (64, 75))],
            [_port("feed", "Eau d'alimentation", 0, 65, "in"), _port("steam", "Vapeur", 50, 0, "out")]),
    _symbol("pump", "Pompe centrifuge", "Machines", "P", "Pompe à deux raccords.",
            [*_ENDS, _circle(50, 50, 25), _polygon((39, 33), (67, 50), (39, 67)), _line((35, 71), (27, 85), (73, 85), (65, 71))]),
    _symbol("positive_displacement_pump", "Pompe volumétrique", "Machines", "P", "Pompe volumétrique représentée.",
            [*_ENDS, _circle(50, 50, 25), _circle(42, 50, 11), _circle(60, 50, 11)]),
    _symbol("metering_pump", "Pompe doseuse", "Machines", "P", "Pompe doseuse représentée, sans loi de dosage.",
            [*_ENDS, _rect(25, 28, 50, 44), _line((36, 34), (36, 66)), _line((36, 50), (65, 50)),
             _line((65, 34), (65, 66))]),
    _symbol("compressor", "Compresseur", "Machines", "K", "Compression représentée, sans pression calculée.",
            [*_ENDS, _circle(50, 50, 27), _polygon((32, 32), (68, 41), (68, 59), (32, 68))]),
    _symbol("blower", "Soufflante", "Machines", "K", "Soufflante à deux raccords.",
            [*_ENDS, _circle(50, 50, 27), _circle(50, 50, 7), _line((50, 43), (36, 29)),
             _line((57, 50), (71, 36)), _line((50, 57), (64, 71)), _line((43, 50), (29, 64))]),
    _symbol("fan", "Ventilateur", "Machines", "FAN", "Ventilateur à deux raccords.",
            [*_ENDS, _circle(50, 50, 27), _circle(50, 50, 5), _ellipse(50, 35, 7, 11),
             _ellipse(63, 58, 10, 6), _ellipse(37, 58, 10, 6)]),
    _symbol("filter", "Filtre", "Séparation et mélange", "F", "Filtre générique sans perte de charge calculée.",
            [*_ENDS, _rect(25, 25, 50, 50), _line((30, 70), (70, 30)), _line((30, 58), (58, 30)), _line((42, 70), (70, 42))]),
    _symbol("filter_press", "Filtre-presse", "Séparation et mélange", "F", "Filtre-presse représenté.",
            [*_ENDS, _rect(25, 25, 50, 50), *[_rect(x, 30, 5, 40) for x in (33, 43, 53, 63)]]),
    _symbol("membrane_filter", "Filtre membranaire", "Séparation et mélange", "F", "Membrane avec perméat et rétentat.",
            [_rect(25, 20, 50, 65), _line((0, 50), (25, 50)), _line((75, 35), (100, 35)),
             _line((75, 75), (100, 75)), _line((50, 25), (50, 80)), _line((55, 25), (55, 80))],
            [_port("feed", "Alimentation", 0, 50, "in"), _port("permeate", "Perméat", 100, 35, "out"), _port("retentate", "Rétentat", 100, 75, "out")]),
    _symbol("strainer", "Crépine ou filtre en Y", "Séparation et mélange", "STR", "Crépine en ligne.",
            [*_ENDS, _polygon((25, 40), (65, 40), (78, 55), (55, 78), (40, 65), (50, 55), (25, 55)),
             _line((47, 60), (61, 73)), _line((52, 55), (66, 68))]),
    _symbol("cyclone", "Cyclone ou hydrocyclone", "Séparation et mélange", "CY", "Séparation cyclonique représentée.",
            [_rect(30, 20, 40, 30), _polygon((30, 50), (70, 50), (50, 88)), _line((0, 35), (30, 35)),
             _line((50, 0), (50, 20)), _line((50, 88), (50, 100))],
            [_port("feed", "Alimentation", 0, 35, "in"), _port("overflow", "Surverse", 50, 0, "out"), _port("underflow", "Sousverse", 50, 100, "out")]),
    _symbol("centrifuge", "Centrifugeuse", "Séparation et mélange", "CF", "Centrifugeuse représentée.",
            [*_ENDS, _circle(50, 50, 27), _polygon((35, 31), (68, 50), (35, 69)), _line((42, 36), (62, 50), (42, 64))]),
    _symbol("static_mixer", "Mélangeur statique", "Séparation et mélange", "MX", "Mélangeur en ligne, sans mélange calculé.",
            [*_ENDS, _rect(25, 35, 50, 30), _line((28, 39), (40, 61), (52, 39), (64, 61), (73, 42))]),
    _symbol("manual_valve", "Vanne manuelle", "Vannes et protections", "HV", "Vanne manuelle de type non précisé.", [*_VALVE, *_HANDWHEEL]),
    _symbol("gate_valve", "Vanne à opercule", "Vannes et protections", "HV", "Vanne d'isolement à opercule.", [*_VALVE, *_HANDWHEEL, _line((45, 31), (45, 69))]),
    _symbol("ball_valve", "Vanne à boule", "Vannes et protections", "HV", "Vanne à boisseau sphérique.", [*_VALVE, *_HANDWHEEL, _circle(50, 50, 11)]),
    _symbol("globe_valve", "Vanne à soupape", "Vannes et protections", "HV", "Vanne manuelle à soupape.", [*_VALVE, *_HANDWHEEL, {**_circle(50, 50, 5), "fill": _INK}]),
    _symbol("butterfly_valve", "Vanne papillon", "Vannes et protections", "HV", "Vanne d'isolement à papillon.", [*_VALVE, *_HANDWHEEL, _line((43, 34), (57, 66))]),
    _symbol("diaphragm_valve", "Vanne à membrane", "Vannes et protections", "HV", "Vanne d'isolement à membrane.",
            [*_ENDS, _polygon((25, 60), (40, 40), (60, 40), (75, 60)), *_HANDWHEEL]),
    _symbol("needle_valve", "Vanne à pointeau", "Vannes et protections", "HV", "Vanne de réglage à pointeau.",
            [*_VALVE, *_HANDWHEEL, _polygon((46, 25), (54, 25), (50, 55))]),
    _symbol("three_way_valve", "Vanne trois voies", "Vannes et protections", "V", "Trois bornes distinctes AB, A et B ; mélange ou dérivation à déclarer.",
            [_line((0, 50), (25, 50)), _line((75, 50), (100, 50)), _line((50, 75), (50, 100)),
             _polygon((25, 33), (50, 50), (25, 67)), _polygon((75, 33), (50, 50), (75, 67)),
             _polygon((33, 75), (50, 50), (67, 75)), _line((50, 50), (50, 15)), _rect(39, 3, 22, 12)],
            [_port("AB", "AB · commun", 0, 50), _port("A", "A", 100, 50), _port("B", "B", 50, 100)]),
    _symbol("four_way_valve", "Vanne quatre voies", "Vannes et protections", "V", "Quatre bornes distinctes ; chemins internes à déclarer.",
            [_line((0, 50), (25, 50)), _line((75, 50), (100, 50)), _line((50, 0), (50, 25)),
             _line((50, 75), (50, 100)), _polygon((25, 33), (50, 50), (25, 67)),
             _polygon((75, 33), (50, 50), (75, 67)), _polygon((33, 25), (50, 50), (67, 25)),
             _polygon((33, 75), (50, 50), (67, 75))],
            [_port("P1", "Raccord 1", 0, 50), _port("P2", "Raccord 2", 100, 50),
             _port("P3", "Raccord 3", 50, 0), _port("P4", "Raccord 4", 50, 100)]),
    _symbol("check_valve", "Clapet antiretour", "Vannes et protections", "NRV", "Sens déclaré au dessin ; aucun blocage hydraulique calculé.",
            [*_ENDS, _polygon((30, 32), (65, 50), (30, 68)), _line((68, 28), (68, 72))],
            [_port("in", "Entrée", 0, 50, "in"), _port("out", "Sortie", 100, 50, "out")]),
    _symbol("pressure_regulator", "Régulateur autonome de pression", "Vannes et protections", "PRV", "Régulation de pression représentée, sans loi de régulation.",
            [*_VALVE, _line((50, 50), (50, 23)), _ellipse(50, 20, 18, 10), _line((80, 50), (80, 10), (63, 10))]),
    _symbol("relief_valve", "Soupape de sûreté ou de décharge", "Vannes et protections", "PSV", "Soupape représentée, sans tarage calculé ni fonction de protection simulée.",
            [_line((0, 65), (30, 65)), _line((65, 30), (100, 30)), _polygon((30, 48), (65, 65), (65, 30)),
             _line((47, 47), (47, 27), (40, 23), (54, 18), (40, 13), (54, 8))],
            [_port("in", "Entrée", 0, 65, "in"), _port("out", "Décharge", 100, 30, "out")]),
    _symbol("rupture_disc", "Disque de rupture", "Vannes et protections", "RD", "Disque représenté, sans rupture calculée.",
            [*_ENDS, _line((38, 25), (38, 75)), _line((62, 25), (62, 75)), _line((50, 25), (43, 38), (43, 62), (50, 75))]),
    _symbol("generic", "Objet documentaire à qualifier", "Autres objets", "X", "Objet conservant son type source et ses raccords déclarés.",
            [_rect(20, 25, 60, 50), *_ENDS, _line((42, 37), (50, 32), (59, 37), (59, 44), (50, 50), (50, 57)), _circle(50, 65, 2)]),
]


_PYFLOWSHEET_COMMIT = "8a68f2569a9a977079ece242aa7771b9d53448a8"
_PYFLOWSHEET_HASHES = {
    "pump": "f52463af9deb811763862e124679ac9471660d2e6bbb15d57f512e37123ff61b",
    "valve": "fe72d12a9262fb51ce6607ff3f0b30d0a876b181e528dfa5c35564d8c27ba174",
    "heatexchanger": "f30d45e228116a499b0bdae4fd97aa38a8d646994ba7e39ab0967df9f2dd884f",
    "compressor": "9ad71daca0590aeca48f93f29423fcdbda51a358c5e3ae5d04b39323a6cec245",
}


def _sourced_symbol(identifier, label, prefix, upstream, shapes, ports=None):
    symbol = _symbol(identifier, label, "Représentations générales sourcées", prefix,
                     "Géométrie adaptée de pyflowsheet (Jochen Steimel, MIT), sans certification normative.",
                     shapes, ports)
    symbol["source"] = {
        "name": "pyflowsheet / Jochen Steimel",
        "url": f"https://github.com/nukleon84/pyflowsheet/blob/{_PYFLOWSHEET_COMMIT}/pyflowsheet/unitoperations/{upstream}.py",
        "license": "MIT", "commit": _PYFLOWSHEET_COMMIT,
        "source_sha256": _PYFLOWSHEET_HASHES[upstream],
        "changes": "Normalisation du corps dans 25..75, raccords de dessin ajoutés, couleurs locales et libellés français. Aucun code amont exécuté.",
    }
    symbol["references"] = ["ISO 10628-2:2012 : contexte des symboles de procédé, conformité non certifiée"]
    return symbol


# Drawing formulae adapted from pyflowsheet at the immutable commit above.
# Copyright (c) 2020 Jochen Steimel, MIT; full notice is shipped alongside this
# module in pid_symbols_pyflowsheet_LICENSE.txt. Body bounds are [25,25,75,75].
PID_SYMBOLS.extend([
    _sourced_symbol("pump_general", "Pompe, représentation générale", "P", "pump",
                    [*_ENDS, _circle(50, 50, 25), _line((50, 25), (75, 50)), _line((50, 75), (75, 50))]),
    _sourced_symbol("valve_general", "Vanne, représentation générale", "V", "valve",
                    [*_ENDS, _polygon((25, 35), (75, 65), (75, 35), (25, 65))]),
    _sourced_symbol("heat_exchanger_general", "Échangeur, représentation générale à quatre piquages", "E", "heatexchanger",
                    [*_ENDS, _circle(50, 50, 25), _line((50, 0), (50, 25)), _line((50, 75), (50, 100)),
                     _line((25, 50), (25 + 50 / 6, 50), (25 + 50 / 3, 37.5),
                           (25 + 100 / 3, 62.5), (75 - 50 / 6, 50), (75, 50))],
                    [_port("primary_in", "Circuit primaire · entrée", 0, 50, "in"),
                     _port("primary_out", "Circuit primaire · sortie", 100, 50, "out"),
                     _port("secondary_in", "Circuit secondaire · entrée", 50, 0, "in"),
                     _port("secondary_out", "Circuit secondaire · sortie", 50, 100, "out")]),
    _sourced_symbol("compressor_general", "Compresseur, représentation générale", "K", "compressor",
                    [*_ENDS, _circle(50, 50, 25),
                     _line((50 + 25 * cos(radians(120)), 50 - 25 * sin(radians(120))),
                           (50 + 25 * cos(radians(10)), 50 - 25 * sin(radians(10)))),
                     _line((50 + 25 * cos(radians(120)), 50 + 25 * sin(radians(120))),
                           (50 + 25 * cos(radians(10)), 50 + 25 * sin(radians(10))))]),
])


def _instrument(identifier, label, code):
    symbol = _symbol(identifier, f"{label} ({code})", "Instrumentation et fonctions", code,
                     "Code fonctionnel usuel d'instrumentation ; implantation et boucle à déclarer selon le projet.",
                     [_circle(50, 50, 28), _line((50, 78), (50, 100))],
                     [_port("tap", "Prise de mesure ou raccord documentaire", 50, 100)])
    symbol["instrument_code"] = code
    symbol["references"] = ["ANSI/ISA-5.1-2024 : symboles et identification des fonctions d'instrumentation"]
    return symbol


# Functional examples, not a reproduction of an ISA table or a loop-numbering
# policy. Existing source tags are never guessed or renamed from these codes.
PID_SYMBOLS.extend(_instrument(*entry) for entry in [
    ("flow_transmitter", "Transmetteur de débit", "FT"),
    ("pressure_transmitter", "Transmetteur de pression", "PT"),
    ("level_transmitter", "Transmetteur de niveau", "LT"),
    ("temperature_transmitter", "Transmetteur de température", "TT"),
    ("flow_indicator", "Indicateur de débit", "FI"),
    ("pressure_indicator", "Indicateur de pression", "PI"),
    ("level_indicator", "Indicateur de niveau", "LI"),
    ("temperature_indicator", "Indicateur de température", "TI"),
    ("flow_indicating_controller", "Régulateur indicateur de débit", "FIC"),
    ("pressure_indicating_controller", "Régulateur indicateur de pression", "PIC"),
    ("level_indicating_controller", "Régulateur indicateur de niveau", "LIC"),
    ("temperature_indicating_controller", "Régulateur indicateur de température", "TIC"),
    ("level_alarm_high", "Alarme de niveau haut", "LAH"),
    ("level_alarm_low", "Alarme de niveau bas", "LAL"),
    ("pressure_switch_high", "Pressostat haut", "PSH"),
    ("pressure_switch_low", "Pressostat bas", "PSL"),
])

PID_SYMBOLS_BY_ID = {symbol["id"]: symbol for symbol in PID_SYMBOLS}


def _key(value: str) -> str:
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value.strip())
    value = "".join(character for character in unicodedata.normalize("NFKD", value) if not unicodedata.combining(character))
    return re.sub(r"[\s\-'’]+", "_", value.lower())


_ALIASES = {_key(symbol["id"]): symbol["id"] for symbol in PID_SYMBOLS}
_ALIASES.update({_key(symbol["label"]): symbol["id"] for symbol in PID_SYMBOLS})
_ALIASES.update({_key(symbol["instrument_code"]): symbol["id"] for symbol in PID_SYMBOLS if symbol.get("instrument_code")})
for _identifier, _names in {
    "tank": ["cuve", "reservoir atmospherique", "storage_tank"],
    "vessel": ["ballon", "process_vessel"],
    "pressure_vessel": ["reservoir sous pression", "pressure_tank"],
    "agitated_tank": ["cuve agitee", "stirred_tank"],
    "reactor": ["reacteur"], "column": ["colonne", "distillation_column"],
    "separator": ["separateur"],
    "heat_exchanger": ["echangeur", "echangeur thermique", "echangeur tubulaire", "shell_and_tube_heat_exchanger", "shell_tube_heat_exchanger"],
    "plate_heat_exchanger": ["echangeur a plaques", "heat_exchanger_plate", "plate_type_heat_exchanger"],
    "heater": ["rechauffeur"], "cooler": ["refroidisseur"],
    "condenser": ["condenseur"], "evaporator": ["evaporateur"], "boiler": ["chaudiere"],
    "pump": ["centrifugal_pump", "pompe centrifuge"],
    "positive_displacement_pump": ["pompe volumetrique"], "metering_pump": ["dosing_pump", "pompe doseuse"],
    "compressor": ["compresseur"], "blower": ["soufflante"], "fan": ["ventilateur"],
    "filter": ["filtre"], "filter_press": ["filtre presse"], "membrane_filter": ["filtre membranaire"],
    "strainer": ["crepine", "y_strainer"], "cyclone": ["hydrocyclone"],
    "centrifuge": ["centrifugeuse"], "static_mixer": ["melangeur statique"],
    "manual_valve": ["vanne manuelle"], "gate_valve": ["vanne a opercule"],
    "ball_valve": ["vanne a boule", "vanne a boisseau spherique"], "globe_valve": ["vanne a soupape"],
    "butterfly_valve": ["vanne papillon"], "diaphragm_valve": ["vanne a membrane"], "needle_valve": ["vanne a pointeau"],
    "three_way_valve": ["vanne 3 voies", "vanne trois voies", "valve_three_way", "3_way_valve"],
    "four_way_valve": ["vanne 4 voies", "vanne quatre voies", "valve_four_way", "4_way_valve"],
    "check_valve": ["non_return_valve", "clapet antiretour", "clapet anti retour"],
    "pressure_regulator": ["regulateur de pression", "regulateur autonome de pression"],
    "relief_valve": ["safety_valve", "pressure_relief_valve", "soupape de surete", "soupape de decharge"],
    "rupture_disc": ["rupture_disk", "disque de rupture"],
    "pump_general": ["general_pump", "pyflowsheet_pump"],
    "valve_general": ["general_valve", "pyflowsheet_valve"],
    "heat_exchanger_general": ["general_heat_exchanger", "pyflowsheet_heat_exchanger"],
    "compressor_general": ["general_compressor", "pyflowsheet_compressor"],
    "flow_transmitter": ["transmetteur de debit"],
    "pressure_transmitter": ["transmetteur de pression"],
    "level_transmitter": ["transmetteur de niveau"],
    "temperature_transmitter": ["transmetteur de temperature"],
    "flow_indicator": ["indicateur de debit"],
    "pressure_indicator": ["indicateur de pression"],
    "level_indicator": ["indicateur de niveau"],
    "temperature_indicator": ["indicateur de temperature"],
    "generic": ["unknown", "other", "inconnu", "objet a qualifier"],
}.items():
    _ALIASES.update({_key(name): _identifier for name in _names})


def resolve_symbol(kind: str) -> str | None:
    """Resolve only declared names and aliases, never tag prefixes or fuzzy text."""
    if not isinstance(kind, str) or not kind.strip() or len(kind) > 160:
        return None
    return _ALIASES.get(_key(kind))
