"""Tabular input is reviewed without mutating a project or granting PLC writes."""

from copy import deepcopy
import csv
import io

from fastapi.testclient import TestClient
import pytest

from fat_studio.app import create_app
from fat_studio.demo import demo_project
from fat_studio.mapping import export_mapping
from fat_studio.models import Project, Tag
from fat_studio.tabular_mapping import analyze_table, preview_table


def blank():
    return Project(id="table_test", name="Table test")


def suggested(text, **options):
    return [column["suggested_field"] for column in analyze_table(text, **options)["columns"]]


def test_excel_tsv_maps_headers_and_leaves_unknown_columns_for_review():
    text = "\ufeffNom\tSens\tType\tAdresse Siemens\tNote libre\r\nP101_Running\tentrée\tBOOL\t%I1.0\tCellule ignorée\r\n"
    analysis = analyze_table(text)
    assert analysis["separator"] == "tab"
    assert suggested(text) == ["name", "direction", "data_type", "plc_address", ""]
    assert analysis["rows"] == [{"line": 2, "cells": ["P101_Running", "entrée", "BOOL", "%I1.0", "Cellule ignorée"]}]
    project = blank()
    result = preview_table(project, text, suggested(text))
    tag = result["project"].tags[0]
    assert tag.id.startswith("tag_") and tag.name == "P101_Running"
    assert (tag.direction, tag.data_type, tag.initial_value, tag.writable) == ("input", "BOOL", False, False)
    assert tag.plc_address == "%I1.0" and tag.node_id == "" and tag.signal is None
    assert result["generated_ids"] and not result["errors"] and project == blank()


def test_semicolon_decimal_comma_and_quoted_multiline_cells_have_physical_line_numbers():
    text = 'Nom;Sens;Type;Valeur initiale;Minimum;Maximum\n"Pression;\nréseau";input;REAL;12,5;0;20\nCommande;output;BOOL;vrai;;\n'
    result = preview_table(blank(), text, suggested(text))
    assert result["separator"] == "semicolon" and result["errors"] == []
    assert [row["line"] for row in result["rows"]] == [2, 4]
    assert result["project"].tags[0].name == "Pression;\nréseau"
    assert result["project"].tags[0].initial_value == 12.5
    assert result["project"].tags[1].initial_value is True
    assert all(not tag.writable for tag in result["project"].tags)


def test_columns_without_headers_are_explicit_and_type_and_direction_are_never_inferred():
    text = "Pump,%Q0.0,BOOL,output"
    assert suggested(text, has_header=False) == ["", "", "", ""]
    result = preview_table(blank(), text, ["name", "plc_address", "data_type", "direction"], has_header=False)
    assert result["project"].tags[0].plc_address == "%Q0.0"
    with pytest.raises(ValueError, match="Nom, Sens automate et Type"):
        preview_table(blank(), "Pump\t%Q0.0", ["name", "plc_address"], has_header=False)


def test_common_values_are_explicit_and_only_fill_missing_columns():
    text = "Nom\tType\tAdresse\nRunning\tBOOL\t%I0.0\nLevel\tREAL\t%IW264"
    result = preview_table(blank(), text, suggested(text), defaults={"direction": "input"})
    assert not result["errors"]
    assert [(tag.data_type, tag.direction, tag.writable) for tag in result["project"].tags] == [("BOOL", "input", False), ("REAL", "input", False)]
    assert all(tag.node_id == "" for tag in result["project"].tags)
    result = preview_table(blank(), "Running\nStopped", ["name"], has_header=False, defaults={"direction": "output", "data_type": "BOOL"})
    assert all(tag.direction == "output" and tag.data_type == "BOOL" for tag in result["project"].tags)
    with pytest.raises(ValueError, match="colonne déjà associée"):
        preview_table(blank(), text, suggested(text), defaults={"direction": "input", "data_type": "REAL"})


@pytest.mark.parametrize("defaults", [{"direction": None}, {"data_type": "WORD"}, {"writable": True}, {"direction": "auto"}])
def test_invalid_or_implicit_common_values_are_refused(defaults):
    with pytest.raises(ValueError, match="valeurs communes"):
        preview_table(blank(), "Nom\nRunning", ["name"], defaults=defaults)


def test_explicit_id_updates_only_supplied_fields_and_reuses_canonical_contract_guard():
    project = demo_project()
    tag = next(tag for tag in project.tags if tag.direction == "input" and tag.data_type == "REAL")
    original = project.model_copy(deep=True)
    text = f"id;Nom;Sens;Type\n{tag.id};Niveau renommé;input;REAL\n"
    result = preview_table(project, text, suggested(text))
    renamed = next(item for item in result["project"].tags if item.id == tag.id)
    assert renamed.model_dump() == {**tag.model_dump(), "name": "Niveau renommé"}
    assert result["project"].equipment == project.equipment
    assert result["errors"] == [] and project == original and not result["generated_ids"]
    changed = text.replace("Type\n", "Type;Unité\n").replace(";REAL\n", ";REAL;bar\n")
    blocked = preview_table(project, changed, suggested(changed))
    assert blocked["errors"] and blocked["changes"][0]["blocked"]
    assert "Contrat d'une variable utilisée" in blocked["errors"][0]


def test_name_matches_never_overwrite_a_tag_without_an_explicit_id_column():
    project = Project(id="existing", name="Existing", tags=[Tag(id="old", name="Pressure", direction="input", data_type="REAL", writable=True)])
    result = preview_table(project, "Nom;Sens;Type\nPressure;input;REAL", ["name", "direction", "data_type"])
    assert len(result["project"].tags) == 2
    assert result["project"].tags[0] == project.tags[0]
    assert result["project"].tags[1].id != "old" and not result["project"].tags[1].writable


def test_errors_are_reported_for_each_physical_row_and_no_partial_project_is_returned():
    text = "id;Nom;Sens;Type;Valeur initiale;Écriture\none;Valid;input;BOOL;true;non\ntwo;Bad type;input;WORD;0;non\nthree;Bad sense;%I0.0;REAL;0;non\nfour;Bad bool;input;BOOL;maybe;non\nfive;Bad columns;input;BOOL\n"
    result = preview_table(blank(), text, suggested(text), separator="semicolon")
    assert result["project"] is None and not result["changes"]
    assert len(result["errors"]) == 4
    assert [row["line"] for row in result["rows"] if row["errors"]] == [3, 4, 5, 6]
    assert result["rows"][0]["tag"]["initial_value"] is True


@pytest.mark.parametrize("row,fragment", [
    (";Empty id;input;BOOL;false;false", "Identifiant vide"),
    ("one; ;input;BOOL;false;false", "nom"),
    ("one;Output;output;BOOL;false;true", "sortie PLC"),
    ("one;Int;input;INT;1,5;false", "entier"),
    ("one;Real;input;REAL;NaN;false", "nombre"),
    ("one;Real;input;REAL;1e500;false", "fini"),
    ("one;Real;input;REAL;1e100;false", "REAL"),
    ("one;Input;input;BOOL;false;maybe", "booléenne"),
])
def test_explicit_values_remain_strict_and_cannot_grant_output_writes(row, fragment):
    text = "id;Nom;Sens;Type;Valeur initiale;Écriture\n" + row
    result = preview_table(blank(), text, suggested(text))
    assert result["project"] is None and fragment.casefold() in " ".join(result["errors"]).casefold()


def test_duplicate_identifiers_and_duplicate_field_choices_are_rejected():
    text = "id;Nom;Sens;Type\nsame;One;input;BOOL\nsame;Two;input;BOOL"
    result = preview_table(blank(), text, suggested(text))
    assert "Identifiant répété" in result["errors"][0]
    with pytest.raises(ValueError, match="seule colonne"):
        preview_table(blank(), text, ["name", "name", "direction", "data_type"])
    with pytest.raises(ValueError, match="champ connu"):
        preview_table(blank(), text, ["unknown", "name", "direction", "data_type"])
    with pytest.raises(ValueError, match="champ connu"):
        preview_table(blank(), text, ["name"])


def test_replacement_reuses_the_used_tag_removal_guard():
    project = demo_project()
    result = preview_table(project, "Nom,Sens,Type\nNew,input,BOOL", ["name", "direction", "data_type"], mode="replace")
    assert result["errors"] and any(change["kind"] == "removed" and change["blocked"] for change in result["changes"])


def test_canonical_csv_roundtrip_keeps_escaped_text_scaling_and_explicit_permissions():
    original = Tag(id="analog", name="'=formula literal", direction="input", data_type="REAL", initial_value=1.2,
                   min=-100., max=30000., unit="@unit", node_id="ns=2;s=literal", plc_symbol="'literal", writable=True,
                   signal={"kind": "4-20mA", "raw_min": 0., "raw_max": 27648.})
    project = Project(id="canonical", name="Canonical", tags=[original])
    text = export_mapping(project)
    result = preview_table(blank(), text, suggested(text))
    assert result["project"].tags == [original] and not result["errors"]


def test_ragged_rows_are_visible_in_analysis_and_can_be_corrected_before_preview():
    text = "Nom;Sens;Type\nOne;input;BOOL\nTwo;input"
    analysis = analyze_table(text)
    assert len(analysis["rows"][1]["cells"]) == 2 and analysis["row_count"] == 2
    result = preview_table(blank(), text, suggested(text))
    assert result["project"] is None and result["rows"][1]["errors"]


def test_bounds_apply_before_conversion_and_after_merge():
    with pytest.raises(ValueError, match="2 Mo"):
        analyze_table("é" * 1_000_001)
    with pytest.raises(ValueError, match="30 colonnes"):
        analyze_table("\t".join(str(i) for i in range(31)))
    with pytest.raises(ValueError, match="200 variables"):
        analyze_table("Nom;Sens;Type\n" + "One;input;BOOL\n" * 201)
    project = Project(id="full", name="Full", tags=[Tag(id=f"tag_{i}", name=str(i), direction="input", data_type="REAL") for i in range(200)])
    result = preview_table(project, "Nom;Sens;Type\nNew;input;BOOL", ["name", "direction", "data_type"])
    assert result["project"] is None and "200 variables" in result["errors"][0]


@pytest.mark.parametrize("text", ["", "Nom;Sens;Type\n", 'Nom;Sens;Type\n"Unclosed;input;BOOL'])
def test_empty_or_malformed_text_has_an_actionable_error(text):
    with pytest.raises(ValueError):
        analyze_table(text)


def scope(client):
    response = client.get("/api/project")
    state = client.get("/api/state").json()
    return response.json(), {"X-FAT-Token": client.get("/api/session").json()["token"],
                             "X-FAT-Project-ID": response.json()["id"],
                             "X-FAT-Project-Revision": response.headers["X-FAT-Project-Revision"],
                             "X-FAT-Run-ID": state["run_id"] or ""}


def test_table_api_previews_require_exact_context_and_leave_project_run_and_writes_unchanged(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        original, headers = scope(client)
        before = client.get("/api/state").json()
        draft = deepcopy(original)
        draft["name"] = "Local table draft"
        body = {"project": draft, "text": "Nom\tSens\tType\nNew\tinput\tBOOL", "separator": "auto", "has_header": True}
        for path, payload in (("/api/mapping/table/analyze", body),
                              ("/api/mapping/table/preview", {**body, "columns": ["name", "direction", "data_type"], "mode": "merge"})):
            result = client.post(path, json=payload, headers=headers)
            assert result.status_code == 200, result.text
            assert "X-FAT-Project-Revision" not in result.headers
            assert client.post(path, json=payload).status_code == 403
            assert client.post(path, json=payload, headers={"X-FAT-Token": headers["X-FAT-Token"]}).status_code == 409
            assert client.post(path, json=payload, headers={**headers, "X-FAT-Project-Revision": "stale"}).status_code == 409
            assert client.post(path, json={**payload, "project": {**draft, "id": "wrong"}}, headers=headers).status_code == 409
        assert result.json()["project"]["name"] == draft["name"]
        assert result.json()["project"]["tags"][-1]["writable"] is False
        assert client.get("/api/project").json() == original
        after = client.get("/api/state").json()
        for key in ("run_id", "status", "project_revision", "write_count", "result"):
            assert after[key] == before[key]


def test_table_api_explicit_common_values_are_previewed_without_saving(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        project, headers = scope(client)
        body = {"project": project, "text": "Nom\nRunning", "columns": ["name"],
                "defaults": {"direction": "input", "data_type": "BOOL"}}
        response = client.post("/api/mapping/table/preview", json=body, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["project"]["tags"][-1]["writable"] is False
        assert client.get("/api/project").json() == project
        response = client.post("/api/mapping/table/preview", json={**body, "defaults": {"direction": "auto"}}, headers=headers)
        assert response.status_code == 422


def test_table_api_previews_refuse_running_and_paused_trials(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        _, headers = scope(client)
        assert client.post("/api/run/start", json={}, headers=headers).status_code == 200
        for paused in (False, True):
            project, headers = scope(client)
            if paused:
                assert client.post("/api/run/pause", headers=headers).status_code == 200
            body = {"project": project, "text": "Nom;Sens;Type\nNew;input;BOOL"}
            for path, payload in (("/api/mapping/table/analyze", body),
                                  ("/api/mapping/table/preview", {**body, "columns": ["name", "direction", "data_type"]})):
                response = client.post(path, json=payload, headers=headers)
                assert response.status_code == 409 and "Arrêtez" in response.json()["detail"]
        assert client.post("/api/run/stop", headers=headers).status_code == 200


def test_incoming_literals_are_not_evaluated_or_converted_into_opcua_addresses():
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter="\t")
    writer.writerow(["Nom", "Sens", "Type", "Adresse Siemens"])
    writer.writerow(['=HYPERLINK("https://example.invalid")', "input", "REAL", "%IW264"])
    result = preview_table(blank(), stream.getvalue(), suggested(stream.getvalue()))
    tag = result["project"].tags[0]
    assert tag.name.startswith("=HYPERLINK") and tag.node_id == "" and tag.plc_address == "%IW264"
