"""Declared title-block metadata survives drawing and project interchange.

Native metadata tests do not qualify external CAD recognition or ISO compliance.
Storage and archive cases use new temporary stores, never an operator instance.
"""

import io
import json
import zipfile

from pydantic import ValidationError
import pytest

from fat_studio.archive import export_archive, prepare_archive, restore_archive
from fat_studio.demo import demo_project
from fat_studio.exchange import project_package, read_project
from fat_studio.models import Project
from fat_studio.pid_cad import cad_capabilities
from fat_studio.pid_exchange import PidPrepareRequest, prepare_pid
from fat_studio.pid_export import EXPORT_FORMATS, export_pid, project_document
from fat_studio.pid_import import inspect_pid
from fat_studio.pid_models import PidDocument
from fat_studio.pid_titleblock import DrawingRevision, PidDrawingSettings
from fat_studio.storage import Store


def drawing_settings():
    return PidDrawingSettings(
        paper_size="A2", orientation="portrait", company="EXEMPLE · Atelier de test", client="Client de démonstration",
        project_reference="TEST-PROJ-2026", site="Site de test", unit="Unité de test", drawing_title="Transfert · essai du cartouche",
        document_number="TEST-PID-042", revision="04", issue_date="2026-11-11", status="for_review",
        sheet_number=3, sheet_total=8, notes="Document de test.", show_legend=False,
        revisions=[DrawingRevision(revision=f"{index:02}", date=f"2026-11-{index + 1:02}",
                                   description=f"Modification synthétique de test {index}") for index in range(5)],
    )


@pytest.fixture
def drawing_project():
    project = demo_project()
    project.id = "drawing-contract"
    project.pid_drawing = drawing_settings()
    project.pid_document = PidDocument(title="Source antérieure", drawing=PidDrawingSettings(company="SOURCE ANTERIEURE", revision="00"))
    return project


def test_old_projects_and_pid_documents_receive_neutral_independent_defaults():
    project = Project.model_validate({"id": "old", "name": "Old project"})
    document = PidDocument.model_validate({"title": "Old drawing"})
    for drawing in (project.pid_drawing, document.drawing):
        assert drawing.paper_size == "A3" and drawing.orientation == "landscape"
        assert drawing.status == "draft" and drawing.revision == "00"
        assert drawing.sheet_number == drawing.sheet_total == 1
        assert drawing.issue_date == ""
        assert drawing.company == drawing.client == drawing.drawn_by == drawing.checked_by == drawing.approved_by == ""
        assert drawing.revisions == []
    project.pid_drawing.company = "Explicit test value"
    assert document.drawing.company == ""


@pytest.mark.parametrize("valid", ["", "2024-02-29", "2026-11-11", "2000-01-01"])
def test_issue_and_revision_dates_accept_only_declared_calendar_dates(valid):
    assert PidDrawingSettings(issue_date=valid).issue_date == valid
    assert DrawingRevision(revision="01", description="Test revision", date=valid).date == valid


@pytest.mark.parametrize("invalid", ["2026-02-29", "2026-13-01", "2026-00-01", "2026-11-31", "2026-2-01", "20261111",
                                     "11/11/2026", "2026-W46-3", "2026-11-11Z", "2026-11-11\n", "now", None, True, 20261111])
def test_invalid_dates_are_rejected_on_both_models(invalid):
    with pytest.raises(ValidationError):
        PidDrawingSettings(issue_date=invalid)
    with pytest.raises(ValidationError):
        DrawingRevision(revision="01", description="Test revision", date=invalid)


@pytest.mark.parametrize("field", ["company", "client", "project_reference", "site", "unit", "drawing_title", "document_number",
                                   "revision", "drawn_by", "checked_by", "approved_by"])
@pytest.mark.parametrize("control", ["\x00", "\x1b", "\x7f", "\n", "\t"])
def test_title_fields_reject_controls_instead_of_silently_normalizing_them(field, control):
    with pytest.raises(ValidationError, match="contrôle"):
        PidDrawingSettings(**{field: "Test" + control + "field"})


@pytest.mark.parametrize("field", ["revision", "description", "drawn_by", "checked_by", "approved_by"])
def test_revision_text_rejects_control_characters(field):
    values = {"revision": "01", "description": "Test revision", field: "Test\x1bfield"}
    with pytest.raises(ValidationError, match="contrôle"):
        DrawingRevision(**values)


def test_notes_preserve_newlines_and_tabs_but_reject_other_controls():
    notes = "Première ligne\n\tDeuxième ligne"
    assert PidDrawingSettings(notes=notes).notes == notes
    for control in ("\x00", "\r", "\x1b", "\x7f"):
        with pytest.raises(ValidationError):
            PidDrawingSettings(notes="Test" + control)


@pytest.mark.parametrize("payload", [{"sheet_number": 0}, {"sheet_total": 0}, {"sheet_number": 1000}, {"sheet_total": 1000},
                                      {"sheet_number": 2, "sheet_total": 1}, {"sheet_number": True}, {"sheet_total": False},
                                      {"sheet_number": 1.0}, {"sheet_total": "1"}])
def test_folio_bounds_and_integer_types_are_strict(payload):
    with pytest.raises(ValidationError):
        PidDrawingSettings(**payload)


def test_folio_upper_bound_is_valid_and_failed_assignment_preserves_previous_state():
    assert PidDrawingSettings(sheet_number=999, sheet_total=999).sheet_total == 999
    settings = PidDrawingSettings()
    before = settings.model_dump()
    with pytest.raises(ValidationError):
        settings.sheet_number = 2
    assert settings.model_dump() == before
    settings = PidDrawingSettings(sheet_number=2, sheet_total=2)
    before = settings.model_dump()
    with pytest.raises(ValidationError):
        settings.sheet_total = 1
    assert settings.model_dump() == before


def test_five_revision_entries_are_retained_and_six_are_rejected():
    settings = drawing_settings()
    assert len(settings.revisions) == 5
    payload = settings.model_dump()
    payload["revisions"].append({"revision": "05", "description": "Sixth test revision"})
    with pytest.raises(ValidationError):
        PidDrawingSettings.model_validate(payload)
    for field in ("revision", "description"):
        values = {"revision": "01", "description": "Test revision", field: ""}
        with pytest.raises(ValidationError):
            DrawingRevision(**values)


@pytest.mark.parametrize("payload", [{"logo_url": "https://example.invalid/logo.svg"}, {"logo_path": "C:/private/logo.svg"},
                                      {"scale": "1:100"}, {"status": "approved"}, {"show_legend": "true"}, {"company": 123},
                                      {"company": "X" * 101}, {"notes": "X" * 1201}])
def test_unknown_features_and_oversized_or_coerced_values_are_rejected(payload):
    with pytest.raises(ValidationError):
        PidDrawingSettings(**payload)


def test_current_settings_override_stale_source_and_export_copies_are_independent(drawing_project):
    before = drawing_project.model_dump_json()
    document = project_document(drawing_project)
    assert document.drawing == drawing_project.pid_drawing
    assert document.drawing != drawing_project.pid_document.drawing
    assert drawing_project.model_dump_json() == before
    document.drawing.company = "Changed exported copy"
    document.drawing.revisions[0].description = "Changed copied revision"
    assert drawing_project.pid_drawing.company == "EXEMPLE · Atelier de test"
    assert drawing_project.pid_drawing.revisions[0].description == "Modification synthétique de test 0"


@pytest.mark.parametrize("format", EXPORT_FORMATS)
def test_ten_native_drawing_formats_preserve_declared_settings_and_preparation_copies_them(drawing_project, format):
    if format == "dwg" and not cad_capabilities()["available"]:
        pytest.skip("Optional real LibreDWG unavailable; this run makes no DWG claim")
    before = drawing_project.model_dump_json()
    payload, media_type, extension = export_pid(drawing_project, format)
    assert payload and media_type
    restored = inspect_pid(payload, "titleblock." + extension, ocr=False)
    assert restored.drawing == drawing_project.pid_drawing
    assert len(restored.equipment) == len(drawing_project.equipment)
    prepared = prepare_pid(PidPrepareRequest(document=restored, selected_ids=[item.id for item in restored.equipment]))["project"]
    assert prepared.pid_drawing == drawing_project.pid_drawing
    assert prepared.pid_document.drawing == drawing_project.pid_drawing
    prepared.pid_drawing.company = "Edited preparation"
    assert prepared.pid_document.drawing.company == restored.drawing.company == drawing_project.pid_drawing.company
    assert drawing_project.model_dump_json() == before


def test_graph_uses_separate_drawing_namespace_without_creating_process_objects(drawing_project):
    graph = json.loads(export_pid(drawing_project, "graph-json")[0])
    assert graph["fat_studio_drawing"] == drawing_project.pid_drawing.model_dump(mode="json")
    assert len(graph["nodes"]) == len(drawing_project.equipment)
    graph["fat_studio_drawing"]["issue_date"] = "2026-02-30"
    with pytest.raises((ValidationError, ValueError)):
        inspect_pid(json.dumps(graph).encode(), "invalid-date.graph.json", ocr=False)


def test_project_package_and_store_restart_preserve_full_drawing_settings(drawing_project, tmp_path):
    package = project_package(drawing_project).model_dump(mode="json")
    restored = read_project(package)
    assert restored == drawing_project
    store = Store(tmp_path / "store")
    try:
        store.save_project(restored)
        assert store.load_project(restored.id) == restored
    finally:
        store.close()
    reopened = Store(tmp_path / "store")
    try:
        assert reopened.last_project() == drawing_project
        assert reopened.last_project().pid_drawing.issue_date == "2026-11-11"
        assert reopened.last_project().pid_drawing.revision == "04"
    finally:
        reopened.close()


def test_archive_preserves_current_and_historical_titleblocks_without_inventing_verdict(drawing_project, tmp_path):
    source, target = Store(tmp_path / "source"), Store(tmp_path / "target")
    try:
        source.save_project(drawing_project)
        source.start_run("run-titleblock", drawing_project, drawing_project.scenarios[0], {"mode": "demo", "target": "demo"})
        source.set_status("run-titleblock", "stopped", ended=True)
        historical = drawing_project.pid_drawing.model_dump(mode="json")
        drawing_project.pid_drawing.revision = "05"
        drawing_project.pid_drawing.issue_date = "2026-11-12"
        source.save_project(drawing_project)
        payload = export_archive(source, drawing_project)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            packaged = json.loads(archive.read("project.json"))
            evidence = json.loads(archive.read("runs/run-titleblock/evidence.json"))
        assert packaged["project"]["pid_drawing"] == drawing_project.pid_drawing.model_dump(mode="json")
        assert evidence["project"]["pid_drawing"] == historical
        assert evidence["result"]["verdict"] == "not_evaluated"
        recovered = restore_archive(target, prepare_archive(payload))
        assert recovered.pid_drawing == drawing_project.pid_drawing
        assert recovered.pid_document.drawing == drawing_project.pid_document.drawing
        run = target.run("run-titleblock")
        assert run["project"]["pid_drawing"] == historical
        assert run["result"]["verdict"] == "not_evaluated"
        assert recovered.pid_drawing.approved_by == historical["approved_by"] == ""
    finally:
        source.close()
        target.close()
