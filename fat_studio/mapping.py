"""Lossless CSV mapping exchange. No implicit direction/type changes on import."""

import csv
import io
import json

from .models import Project, Tag, validate_project


LEGACY_FIELDS = ["id", "name", "direction", "data_type", "unit", "initial_value", "min", "max", "node_id", "writable"]
ADDRESS_FIELDS = [*LEGACY_FIELDS, "plc_address", "plc_symbol"]
FIELDS = [*ADDRESS_FIELDS, "signal"]
ENCODING_FIELD = "_fat_csv_encoding"
ENCODING = "apostrophe-v1"
TEXT_FIELDS = ("name", "unit", "node_id", "plc_address", "plc_symbol")


def _needs_escape(value: str) -> bool:
    return value.startswith("'") or value.lstrip().startswith(("=", "+", "-", "@"))


def _decode_text(value: str) -> str:
    if value.startswith("'"):
        decoded = value[1:]
        if _needs_escape(decoded):
            return decoded
        raise ValueError("Échappement CSV apostrophe-v1 invalide.")
    if _needs_escape(value):
        raise ValueError("Texte CSV non échappé pour l'encodage apostrophe-v1.")
    return value


def export_mapping(project: Project) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=[*FIELDS, ENCODING_FIELD])
    writer.writeheader()
    for tag in project.tags:
        row = tag.model_dump()
        row["initial_value"] = json.dumps(row["initial_value"])
        row["writable"] = "true" if row["writable"] else "false"
        row["signal"] = json.dumps(row["signal"], separators=(",", ":")) if row["signal"] is not None else ""
        # Explicit dialect marker keeps legacy imports literal and makes both
        # formula prefixes and original leading apostrophes exactly reversible.
        for field in TEXT_FIELDS:
            if _needs_escape(row[field]):
                row[field] = "'" + row[field]
        row[ENCODING_FIELD] = ENCODING
        writer.writerow(row)
    return stream.getvalue()


def import_mapping(project: Project, content: str) -> Project:
    try:
        return _import_mapping(project, content)
    except csv.Error as exc:
        raise ValueError(f"CSV invalide : {exc}") from exc


def _import_mapping(project: Project, content: str) -> Project:
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")), strict=True)
    if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("En-tête CSV absent ou dupliqué.")
    if set(reader.fieldnames) not in (set(FIELDS), {*FIELDS, ENCODING_FIELD}, set(ADDRESS_FIELDS), {*ADDRESS_FIELDS, ENCODING_FIELD}, set(LEGACY_FIELDS), {*LEGACY_FIELDS, ENCODING_FIELD}):
        raise ValueError("Colonnes CSV attendues : " + ",".join(FIELDS) + " ; encodage optionnel : " + ENCODING_FIELD)
    encoded = ENCODING_FIELD in reader.fieldnames
    tags = []
    for line, row in enumerate(reader, start=2):
        try:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Nombre de colonnes incorrect")
            row.setdefault("plc_address", "")
            row.setdefault("plc_symbol", "")
            row["signal"] = json.loads(row["signal"]) if row.get("signal") else None
            if encoded:
                if row.pop(ENCODING_FIELD) != ENCODING:
                    raise ValueError("Marqueur d'encodage CSV inconnu ; valeur attendue : " + ENCODING)
                for field in TEXT_FIELDS:
                    row[field] = _decode_text(row[field])
            if row["writable"] not in ("true", "false"):
                raise ValueError("writable doit valoir true ou false")
            row["writable"] = row["writable"] == "true"
            row["initial_value"] = json.loads(row["initial_value"])
            row["min"] = float(row["min"]) if row["min"] else None
            row["max"] = float(row["max"]) if row["max"] else None
            tags.append(Tag.model_validate(row))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"CSV ligne {line} : {exc}") from exc
        if len(tags) > 200:
            raise ValueError("Le mapping est limité à 200 variables.")
    if len({tag.id for tag in tags}) != len(tags):
        raise ValueError("Le CSV contient des identifiants de variables dupliqués.")
    data = project.model_dump(mode="json")
    data["tags"] = [tag.model_dump(mode="json") for tag in tags]
    return Project.model_validate(data)


def preview_mapping(project: Project, content: str, mode: str = "merge") -> dict:
    """Prepare a reversible CSV change without saving or altering tag consumers."""
    if mode not in ("merge", "replace"):
        raise ValueError("Mode d'import attendu : merge ou replace.")
    incoming = import_mapping(project, content)
    old = {tag.id: tag for tag in project.tags}
    supplied = {tag.id: tag for tag in incoming.tags}
    tags = ([supplied.get(tag.id, tag) for tag in project.tags]
            + [tag for tag in incoming.tags if tag.id not in old]) if mode == "merge" else incoming.tags
    if len(tags) > 200:
        raise ValueError("La fusion dépasserait la limite de 200 variables.")
    used = {tag_id for equipment in project.equipment for tag_id in equipment.bindings.values()}
    used.update(equipment.animation.tag_id for equipment in project.equipment if equipment.animation)
    for scenario in project.scenarios:
        used.update(scenario.trend_tags)
        used.update(step.target for step in scenario.steps if step.action in ("force", "release", "expect") and step.target)
        for step in scenario.fat_steps:
            used.update(action.target for action in step.actions)
            used.update(check.target for check in step.checks)
    changes, errors = [], []
    resulting = {tag.id: tag for tag in tags}
    for tag_id in dict.fromkeys([*old, *resulting]):
        before, after = old.get(tag_id), resulting.get(tag_id)
        if before == after:
            continue
        fields = ([name for name, value in before.model_dump().items()
                   if after.model_dump()[name] != value] if before and after else [])
        reasons = []
        if tag_id in used and after is None:
            reasons.append("Variable utilisée par un équipement ou un scénario : sa suppression casserait ses références.")
        changed_contract = sorted(set(fields) & {"direction", "data_type", "unit", "signal"})
        if tag_id in used and changed_contract:
            reasons.append("Contrat d'une variable utilisée modifié (" + ", ".join(changed_contract)
                           + "). Modifiez ses consommateurs explicitement avant cet import.")
        name = (after or before).name
        changes.append({"id": tag_id, "name": name, "kind": "added" if before is None else "removed" if after is None else "changed",
                        "fields": fields, "blocked": bool(reasons), "reasons": reasons})
        errors.extend(f"{name} : {reason}" for reason in reasons)
    data = project.model_dump(mode="json")
    data["tags"] = [tag.model_dump(mode="json") for tag in tags]
    preview = Project.model_validate(data)
    return {"project": preview, "changes": changes, "errors": errors, "validation": validate_project(preview)}
