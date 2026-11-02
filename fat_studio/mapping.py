"""Lossless CSV mapping exchange. No implicit direction/type changes on import."""

import csv
import io
import json

from .models import Project, Tag


FIELDS = ["id", "name", "direction", "data_type", "unit", "initial_value", "min", "max", "node_id", "writable"]


def export_mapping(project: Project) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    for tag in project.tags:
        row = tag.model_dump()
        row["initial_value"] = json.dumps(row["initial_value"])
        row["writable"] = "true" if row["writable"] else "false"
        # This is a machine-readable exchange format, not an Excel report; values remain exact.
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
    if set(reader.fieldnames) != set(FIELDS):
        raise ValueError("Colonnes CSV attendues : " + ",".join(FIELDS))
    tags = []
    for line, row in enumerate(reader, start=2):
        try:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Nombre de colonnes incorrect")
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
