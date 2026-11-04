"""Versioned, machine-readable project and scenario interchange."""
from __future__ import annotations

from typing import Literal
from pydantic import Field

from .models import DataType, EquipmentType, ID_PATTERN, Project, Scenario, SignalScaling, StrictModel, validate_project


class ProjectPackage(StrictModel):
    format: Literal["fat-studio/project"] = "fat-studio/project"
    version: Literal["1.0"] = "1.0"
    project: Project


class TagContract(StrictModel):
    id: str = Field(pattern=ID_PATTERN)
    direction: Literal["input", "output"]
    data_type: DataType
    unit: str = Field(default="", max_length=40)
    signal: SignalScaling | None = None


class EquipmentContract(StrictModel):
    id: str = Field(pattern=ID_PATTERN)
    type: EquipmentType


class ScenarioPackage(StrictModel):
    format: Literal["fat-studio/scenarios"] = "fat-studio/scenarios"
    version: Literal["1.0"] = "1.0"
    scenarios: list[Scenario] = Field(min_length=1, max_length=100)
    tag_contracts: list[TagContract] = Field(default_factory=list, max_length=200)
    equipment_contracts: list[EquipmentContract] = Field(default_factory=list, max_length=50)


def project_package(project: Project) -> ProjectPackage:
    return ProjectPackage(project=project.model_copy(deep=True))


def read_project(payload: dict) -> Project:
    """Accept the v1 package and existing flat projects; never guess a future format."""
    if not isinstance(payload, dict):
        raise ValueError("Objet JSON de projet attendu.")
    if "format" in payload or "version" in payload or "project" in payload:
        project = ProjectPackage.model_validate(payload).project
    else:
        project = Project.model_validate(payload)
    # A project package may be an unfinished builder draft. Types are strict;
    # functional diagnostics remain visible and Runtime.start blocks any exchange.
    return project


def scenarios_package(project: Project, scenario_id: str | None = None) -> ScenarioPackage:
    selected = [scenario for scenario in project.scenarios if scenario_id is None or scenario.id == scenario_id]
    if not selected:
        raise ValueError("Aucun scénario à exporter.")
    tag_ids = set()
    equipment_ids = set()
    for scenario in selected:
        tag_ids.update(scenario.trend_tags)
        equipment_ids.update(scenario.focus_equipment)
        for step in scenario.steps:
            if step.action in ("force", "release", "expect"):
                tag_ids.add(step.target)
            elif step.action in ("fault", "clear_fault"):
                equipment_ids.add(step.target)
        for step in scenario.fat_steps:
            tag_ids.update(action.target for action in step.actions)
            tag_ids.update(check.target for check in step.checks)
    return ScenarioPackage(scenarios=[scenario.model_copy(deep=True) for scenario in selected],
        tag_contracts=[TagContract(id=tag.id, direction=tag.direction, data_type=tag.data_type,
                                  unit=tag.unit, signal=tag.signal) for tag in project.tags if tag.id in tag_ids],
        equipment_contracts=[EquipmentContract(id=item.id, type=item.type) for item in project.equipment if item.id in equipment_ids])


def import_scenarios(project: Project, package: ScenarioPackage, mode: str = "merge") -> Project:
    if mode not in ("merge", "replace"):
        raise ValueError("Mode d'import attendu : merge ou replace.")
    ids = [scenario.id for scenario in package.scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("Identifiants de scénario dupliqués dans le fichier.")
    tag_ids = [tag.id for tag in package.tag_contracts]
    equipment_ids = [item.id for item in package.equipment_contracts]
    if len(tag_ids) != len(set(tag_ids)) or len(equipment_ids) != len(set(equipment_ids)):
        raise ValueError("Contrats de tags ou d'équipements dupliqués.")
    tags = {tag.id: tag for tag in project.tags}
    for contract in package.tag_contracts:
        current = tags.get(contract.id)
        if current is None or TagContract(id=current.id, direction=current.direction, data_type=current.data_type,
                                         unit=current.unit, signal=current.signal) != contract:
            raise ValueError(f"Contrat incompatible pour {contract.id} : vérifier sens, type, unité et conversion.")
    equipment = {item.id: item for item in project.equipment}
    for contract in package.equipment_contracts:
        current = equipment.get(contract.id)
        if current is None or current.type != contract.type:
            raise ValueError(f"Équipement incompatible ou absent : {contract.id}.")
    if mode == "merge" and set(ids) & {scenario.id for scenario in project.scenarios}:
        raise ValueError("Un scénario existe déjà avec cet identifiant ; renommer ou choisir Remplacer explicitement.")
    candidate = project.model_copy(deep=True)
    candidate.scenarios = ([*candidate.scenarios, *package.scenarios] if mode == "merge" else list(package.scenarios))
    validation = validate_project(candidate)
    if not validation["valid"]:
        raise ValueError("Scénarios incompatibles avec ce projet : " + "; ".join(row["message"] for row in validation["errors"]))
    return candidate
