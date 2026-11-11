"""Prepare a reviewed P&ID as a new, disconnected builder draft."""

from __future__ import annotations

import uuid

from pydantic import Field

from .catalog import CATALOG_BY_TYPE
from .models import Connection, Equipment, PLCConfig, Position, Project
from .pid_models import PidDocument, PidModel
from .pid_ports import SIMULATED_PID_SYMBOLS
from .pid_symbols import resolve_symbol


class PidPrepareRequest(PidModel):
    document: PidDocument
    selected_ids: list[str] = Field(min_length=1, max_length=50)
    types: dict[str, str] = Field(default_factory=dict, max_length=2000)
    name: str = Field(default="P&ID importé", min_length=1, max_length=200)


def prepare_pid(body: PidPrepareRequest) -> dict:
    selected = set(body.selected_ids)
    if len(selected) != len(body.selected_ids):
        raise ValueError("Sélection P&ID dupliquée.")
    source = {item.id: item for item in body.document.equipment}
    if selected - source.keys():
        raise ValueError("La sélection contient un objet absent du document P&ID.")
    if body.types.keys() - source.keys():
        raise ValueError("Un choix de type concerne un objet absent du document.")
    equipment = []
    retained_unknown = 0
    for item in body.document.equipment:
        if item.id not in selected:
            continue
        source_symbol = SIMULATED_PID_SYMBOLS.get(item.type) or resolve_symbol(item.type)
        # Drawing data contains no thermal boundaries or tank assignments: new
        # physical families must be selected explicitly during this review.
        documentary = item.documentary or source_symbol in SIMULATED_PID_SYMBOLS.values()
        default_type = "pid:" + (source_symbol or "generic") if documentary else item.type
        requested = body.types.get(item.id, default_type)
        symbol_kind = ""
        if requested.startswith("pid:"):
            symbol_kind = resolve_symbol(requested[4:])
            if not symbol_kind:
                raise ValueError(f"Symbole P&ID inconnu pour {item.name}.")
            kind = "pid_symbol"
        elif requested in CATALOG_BY_TYPE and requested != "pid_symbol":
            kind = requested
        else:
            symbol_kind = resolve_symbol(requested)
            if item.id in body.types and not symbol_kind:
                raise ValueError(f"Choix de type inconnu pour {item.name}.")
            symbol_kind = symbol_kind or "generic"
            kind = "pid_symbol"
        retained_unknown += symbol_kind == "generic"
        equipment.append(Equipment(
            id=item.id, name=item.name, type=kind,
            description=f"Source P&ID : {item.source_tag or item.name}, page {item.page}. "
                        f"{item.provenance}\nParamètres physiques et associations PLC à renseigner."[:4000],
            position=Position(x=item.position.x, y=item.position.y),
            symbol_kind=symbol_kind,
            source_kind=(item.source_kind or item.type) if kind == "pid_symbol" or kind in SIMULATED_PID_SYMBOLS else "",
            rotation=item.rotation,
        ))
    links = [item for item in body.document.connections if item.source in selected and item.target in selected]
    if len(links) > 200:
        raise ValueError("La sélection dépasse les 200 liaisons du banc ; réduire le périmètre importé.")
    document = body.document.model_copy(deep=True)
    if "selected_ids" in document.metadata or len(document.metadata) < 40:
        document.metadata["selected_ids"] = ",".join(body.selected_ids)[:4000]
    document = PidDocument.model_validate(document.model_dump())
    project = Project(
        id="pid-" + uuid.uuid4().hex[:16], name=body.name.strip() or document.title,
        description="Brouillon préparé depuis un P&ID. Revoir les liaisons, les paramètres physiques "
                    "et les associations PLC avant tout essai.",
        equipment=equipment,
        connections=[Connection(id=item.id, source=item.source, target=item.target,
                                label=item.label, directed=item.directed, service=item.service,
                                source_port=item.source_port, target_port=item.target_port) for item in links],
        plc=PLCConfig(mode="demo", demo_controller="manual_lab_v1"),
        pid_document=document,
        pid_drawing=document.drawing.model_copy(deep=True),
    )
    warnings = [
        "Nouveau projet préparé sans variable, scénario, adresse PLC ni autorisation de cible.",
        "Les paramètres du modèle restent à renseigner ; les valeurs par défaut du catalogue ne proviennent pas du plan.",
        "Revoir les liaisons, y compris leur sens, avant tout essai.",
    ]
    omitted = len(body.document.equipment) - len(equipment)
    if omitted:
        warnings.append(f"{omitted} objet(s) source conservé(s) dans le document mais exclus du schéma actif.")
    if retained_unknown:
        warnings.append(f"{retained_unknown} objet(s) non classé(s) conservé(s) comme symboles documentaires, sans simulation.")
    if any(item.type == "pid_symbol" for item in equipment):
        warnings.append("Les symboles P&ID documentaires conservent le dessin et les piquages ; aucun comportement physique n'est simulé.")
    if any(item.type in SIMULATED_PID_SYMBOLS for item in equipment):
        warnings.append("Modèle thermique ou vanne trois voies choisi explicitement : renseigner ses paramètres et associations PLC ; aucune donnée physique n'est déduite du dessin.")
    return {"project": project, "warnings": warnings}
