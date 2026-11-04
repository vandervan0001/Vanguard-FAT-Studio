"""Lossless CSV mapping exchange. No implicit direction/type changes on import."""

import csv
import io
import json

from .models import Project, Tag


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
