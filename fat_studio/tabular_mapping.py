"""Review tabular text before passing it through the canonical mapping preview."""

import csv
import io
import json
import math
import re
import unicodedata
from uuid import uuid4

from pydantic import ValidationError

from .mapping import ENCODING, ENCODING_FIELD, FIELDS, TEXT_FIELDS, _decode_text, export_mapping, preview_mapping
from .models import Project, Tag


SEPARATORS = {"tab": "\t", "semicolon": ";", "comma": ","}
MAX_TEXT_BYTES = 2_000_000
MAX_COLUMNS = 30
MAX_ROWS = 200
TABLE_FIELDS = [*FIELDS, ENCODING_FIELD]
REQUIRED_FIELDS = ("name", "direction", "data_type")
HEADER_NAMES = {
    "id": ("id", "identifiant", "identifier", "tagid"),
    "name": ("name", "nom", "tag", "tagname", "nomdutag", "nomdelavariable"),
    "direction": ("direction", "sens", "sensautomate", "plcdirection"),
    "data_type": ("datatype", "type", "typededonnee", "typededonnees"),
    "unit": ("unit", "unite"),
    "initial_value": ("initialvalue", "valeurinitiale", "initial"),
    "min": ("min", "minimum"),
    "max": ("max", "maximum"),
    "node_id": ("nodeid", "nodeidopcua"),
    "writable": ("writable", "ecriture", "ecritureautorisee", "autorisationecriture"),
    "plc_address": ("plcaddress", "adresse", "adressesiemens", "adresseautomate"),
    "plc_symbol": ("plcsymbol", "symbole", "symboleplc", "symboleautomate"),
    "signal": ("signal", "conversionanalogique"),
    ENCODING_FIELD: ("fatcsvencoding",),
}


def _header_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", value.casefold()).encode("ascii", "ignore").decode())


def _parse(content: str, separator: str, has_header: bool) -> dict:
    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValueError("Le tableau est limité à 2 Mo de texte UTF-8.")
    if type(has_header) is not bool or separator not in {"auto", *SEPARATORS}:
        raise ValueError("Choisissez un séparateur et indiquez si la première ligne contient les titres.")
    text = content.lstrip("\ufeff")
    if not text.strip():
        raise ValueError("Collez au moins une ligne de variables.")
    if separator == "auto":
        try:
            delimiter = csv.Sniffer().sniff(text[:65536], delimiters="\t;,").delimiter
            separator = next(key for key, value in SEPARATORS.items() if value == delimiter)
        except csv.Error:
            # A single-column or irregular table can still be reviewed manually.
            # Prefer delimiters outside quotes, rather than decimal commas.
            first_line = text.splitlines()[0]
            separator = "tab" if "\t" in first_line else "semicolon" if ";" in first_line else "comma"
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=SEPARATORS[separator], strict=True)
    parsed = []
    try:
        while True:
            line = reader.line_num + 1
            try:
                cells = next(reader)
            except StopIteration:
                break
            if not cells or not any(cell.strip() for cell in cells):
                continue
            if len(cells) > MAX_COLUMNS:
                raise ValueError(f"Ligne {line} : le tableau est limité à {MAX_COLUMNS} colonnes.")
            parsed.append({"line": line, "cells": cells})
            if len(parsed) > MAX_ROWS + int(has_header):
                raise ValueError("Le tableau est limité à 200 variables.")
    except csv.Error as exc:
        raise ValueError(f"Tableau ligne {reader.line_num} : {exc}") from exc
    if not parsed or (has_header and len(parsed) == 1):
        raise ValueError("Le tableau ne contient aucune ligne de variables après les titres.")
    headers = parsed.pop(0)["cells"] if has_header else [f"Colonne {i + 1}" for i in range(len(parsed[0]["cells"]))]
    seen = set()
    columns = []
    for index, header in enumerate(headers):
        key = _header_key(header) if has_header else ""
        field = next((name for name, names in HEADER_NAMES.items() if key in names), "")
        if field in seen:
            field = ""
        if field:
            seen.add(field)
        columns.append({"index": index, "header": header or f"Colonne {index + 1}", "suggested_field": field})
    return {"separator": separator, "columns": columns, "rows": parsed, "row_count": len(parsed)}


def analyze_table(content: str, separator: str = "auto", has_header: bool = True) -> dict:
    """Return literal cells and header suggestions; never infer values or permissions."""
    return _parse(content, separator, has_header)


def _boolean(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"true", "vrai", "oui", "1"}:
        return True
    if normalized in {"false", "faux", "non", "0"}:
        return False
    raise ValueError("Valeur booléenne attendue : true/false, vrai/faux, oui/non ou 1/0.")


def _number(value: str, integer: bool = False):
    value = value.strip()
    if integer:
        if not re.fullmatch(r"[+-]?\d+", value):
            raise ValueError("Un entier est attendu, sans décimales ni séparateur de milliers.")
        return int(value)
    if not re.fullmatch(r"[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?", value):
        raise ValueError("Un nombre est attendu, avec une virgule ou un point décimal, sans séparateur de milliers.")
    number = float(value.replace(",", "."))
    if not math.isfinite(number):
        raise ValueError("Un nombre fini est attendu.")
    return number


def _tag_row(values: dict[str, str], existing: dict[str, Tag]) -> Tag:
    explicit_id = values.get("id", "").strip()
    before = existing.get(explicit_id)
    data = before.model_dump(mode="json") if before else {"id": explicit_id or "tag_" + uuid4().hex[:20], "writable": False}
    if "id" in values and not explicit_id:
        raise ValueError("Identifiant vide : renseignez-le ou ignorez la colonne Identifiant pour créer de nouvelles variables.")
    if ENCODING_FIELD in values:
        if values[ENCODING_FIELD] != ENCODING:
            raise ValueError("Marqueur d'encodage CSV Vanguard inconnu.")
        values = {key: _decode_text(value) if key in TEXT_FIELDS else value for key, value in values.items()}
    if not values["name"].strip():
        raise ValueError("Le nom de la variable ne peut pas être vide.")
    direction = {"input": "input", "entree": "input", "output": "output", "sortie": "output"}.get(_header_key(values["direction"]))
    if direction is None:
        raise ValueError("Sens automate attendu : input/entrée ou output/sortie.")
    data_type = values["data_type"].strip().upper()
    if data_type not in {"BOOL", "INT", "DINT", "REAL"}:
        raise ValueError("Type attendu : BOOL, INT, DINT ou REAL.")
    data.update(name=values["name"], direction=direction, data_type=data_type)
    for field in ("unit", "node_id", "plc_address", "plc_symbol"):
        if field in values:
            data[field] = values[field]
    for field in ("min", "max"):
        if field in values:
            data[field] = _number(values[field]) if values[field].strip() else None
    if "signal" in values:
        data["signal"] = json.loads(values["signal"]) if values["signal"].strip() else None
    if "writable" in values:
        data["writable"] = _boolean(values["writable"])
    if "initial_value" in values:
        data["initial_value"] = (_boolean(values["initial_value"]) if data_type == "BOOL"
                                 else _number(values["initial_value"], data_type in {"INT", "DINT"}))
    elif not before:
        data["initial_value"] = False if data_type == "BOOL" else 0
    return Tag.model_validate(data)


def preview_table(project: Project, content: str, columns: list[str], separator: str = "auto",
                  has_header: bool = True, mode: str = "merge", defaults: dict | None = None) -> dict:
    """Convert reviewed columns, report row errors, then reuse canonical merge guards."""
    table = _parse(content, separator, has_header)
    if (not isinstance(columns, list) or len(columns) != len(table["columns"])
            or any(not isinstance(field, str) or field not in ["", *TABLE_FIELDS] for field in columns)):
        raise ValueError("La correspondance doit désigner un champ connu ou ignorer chaque colonne.")
    selected = [field for field in columns if field]
    if len(selected) != len(set(selected)):
        raise ValueError("Un champ ne peut correspondre qu'à une seule colonne.")
    defaults = {} if defaults is None else defaults
    if (not isinstance(defaults, dict) or set(defaults) - {"direction", "data_type"}
            or any(not isinstance(value, str) or value not in ({"input", "output"} if field == "direction" else {"BOOL", "INT", "DINT", "REAL"})
                   for field, value in defaults.items())):
        raise ValueError("Les valeurs communes doivent être un sens input/output et/ou un type BOOL/INT/DINT/REAL explicites.")
    if set(defaults) & set(selected):
        raise ValueError("Une valeur commune ne peut pas remplacer une colonne déjà associée.")
    if any(field not in selected and field not in defaults for field in REQUIRED_FIELDS):
        raise ValueError("Associez les colonnes Nom, Sens automate et Type, ou choisissez explicitement un sens/type commun.")
    if mode not in {"merge", "replace"}:
        raise ValueError("Mode d'import attendu : merge ou replace.")
    existing = {tag.id: tag for tag in project.tags}
    tags, rows, errors, ids = [], [], [], set()
    for row in table["rows"]:
        line, cells = row["line"], row["cells"]
        try:
            if len(cells) != len(columns):
                raise ValueError(f"{len(cells)} cellules au lieu de {len(columns)}. Vérifiez le séparateur ou les cellules vides.")
            tag = _tag_row({**defaults, **{field: cells[index] for index, field in enumerate(columns) if field}}, existing)
            if tag.id in ids:
                raise ValueError("Identifiant répété dans le tableau : " + tag.id)
            ids.add(tag.id)
            tags.append(tag)
            rows.append({"line": line, "tag": tag.model_dump(mode="json"), "errors": []})
        except (ValueError, TypeError) as exc:
            message = (" ; ".join(".".join(map(str, item["loc"])) + " : " + item["msg"]
                                 for item in exc.errors(include_url=False, include_context=False))
                       if isinstance(exc, ValidationError) else str(exc))
            errors.append(f"Ligne {line} : {message}")
            rows.append({"line": line, "tag": None, "errors": [message]})
    result = {"project": None, "changes": [], "errors": errors, "validation": None, "rows": rows,
              "generated_ids": "id" not in selected, "separator": table["separator"]}
    if errors:
        return result
    try:
        incoming = Project(id="table_import", name="Tableau relu", tags=tags)
        result.update(preview_mapping(project, export_mapping(incoming), mode))
    except ValueError as exc:
        result["errors"] = [str(exc)]
    return result
