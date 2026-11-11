"""Documentary P&ID conventions; never infer physical conditions or compliance."""

from copy import deepcopy
from typing import Literal

PidService = Literal["unspecified", "cold_supply", "cold_return", "hot_supply", "hot_return",
                     "steam", "condensate", "cooling_water", "instrument_air", "process"]

# These service identifiers, codes and colours are the editable drawing office's
# house palette. They are not safety pipe marking or a universal ISO/ISA palette.
SERVICE_DEFINITIONS = [
    {"id": "unspecified", "label": "Service non renseigné", "code": "", "color": "#000000", "aci": 7},
    {"id": "cold_supply", "label": "Départ froid", "code": "CHWS", "color": "#0052A5", "aci": 152},
    {"id": "cold_return", "label": "Retour froid", "code": "CHWR", "color": "#527CA5", "aci": 153},
    {"id": "hot_supply", "label": "Départ chaud", "code": "HWS", "color": "#A50000", "aci": 12},
    {"id": "hot_return", "label": "Retour chaud", "code": "HWR", "color": "#A55252", "aci": 13},
    {"id": "steam", "label": "Vapeur", "code": "STM", "color": "#A57C00", "aci": 42},
    {"id": "condensate", "label": "Condensats", "code": "COND", "color": "#7F5F00", "aci": 44},
    {"id": "cooling_water", "label": "Eau de refroidissement", "code": "CW", "color": "#007F7F", "aci": 134},
    {"id": "instrument_air", "label": "Air instruments", "code": "IA", "color": "#6752A5", "aci": 183},
    {"id": "process", "label": "Fluide de procédé", "code": "PROC", "color": "#3F7F3F", "aci": 95},
]
_SERVICES = {item["id"]: item for item in SERVICE_DEFINITIONS}

REFERENCES = [
    {"id": "isa-5.1", "title": "ANSI/ISA-5.1-2024", "url": "https://www.isa.org/standards-and-publications/isa-standards/find-isa-standards-by-topic",
     "scope": "Symboles et identification des fonctions d'instrumentation. Guide de lecture ; aucune conformité complète revendiquée."},
    {"id": "iso-10628-1", "title": "ISO 10628-1:2014", "url": "https://www.iso.org/standard/51840.html",
     "scope": "Spécification des schémas pour l'industrie chimique et pétrochimique."},
    {"id": "iso-10628-2", "title": "ISO 10628-2:2012", "url": "https://www.iso.org/standard/51841.html",
     "scope": "Symboles graphiques des schémas de procédé. Les dessins normatifs ne sont pas redistribués."},
    {"id": "iso-14617", "title": "ISO 14617-1 et -2:2025", "url": "https://www.iso.org/standard/83364.html",
     "scope": "Règles générales et bibliothèque de symboles pour les diagrammes."},
    {"id": "en-1861", "title": "EN 1861:1998", "url": "https://www.dinmedia.de/en/standard/din-en-1861/4533906",
     "scope": "Schémas de systèmes frigorifiques et de pompes à chaleur."},
    {"id": "iso-20560-1", "title": "ISO 20560-1:2024", "url": "https://www.iso.org/standard/86049.html",
     "scope": "Marquage de sécurité des tuyauteries physiques aériennes ; ne définit pas la palette P&ID du projet."},
]

INSTRUMENT_FUNCTIONS = [
    {"code": code, "label": label, "example": code + "-101"}
    for code, label in [
        ("FI", "Indication de débit"), ("FT", "Transmission de débit"), ("FIC", "Indication et régulation de débit"),
        ("PI", "Indication de pression"), ("PT", "Transmission de pression"), ("PIC", "Indication et régulation de pression"),
        ("TI", "Indication de température"), ("TT", "Transmission de température"), ("TIC", "Indication et régulation de température"),
        ("LI", "Indication de niveau"), ("LT", "Transmission de niveau"), ("LIC", "Indication et régulation de niveau"),
        ("LSH", "Contact de niveau haut"), ("LSL", "Contact de niveau bas"),
        ("LAH", "Alarme de niveau haut"), ("LAL", "Alarme de niveau bas"),
        ("PSH", "Contact de pression haute"), ("PSL", "Contact de pression basse"),
    ]
]


def service_definition(identifier: str) -> dict:
    """Return detached display metadata; unknown external service stays unspecified."""
    return deepcopy(_SERVICES.get(identifier, _SERVICES["unspecified"]))


def conventions_catalog() -> dict:
    return {"version": "1.0", "services": deepcopy(SERVICE_DEFINITIONS),
            "references": deepcopy(REFERENCES), "instruments": deepcopy(INSTRUMENT_FUNCTIONS),
            "notice": "Couleurs et codes de services : convention de projet Vanguard, à faire correspondre au cahier des charges. "
                      "Les exemples ISA expliquent des fonctions, sans renommer les repères importés ni valider une conformité normative."}
