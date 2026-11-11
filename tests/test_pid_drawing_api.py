"""Drawing previews are passive, bounded and independent of operational commands."""

import base64
from concurrent.futures import ThreadPoolExecutor
import io
from threading import Event

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from fat_studio.app import create_app
from fat_studio import pid_export
from fat_studio.pid_titleblock import PidDrawingSettings


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as instance:
        instance.headers["X-FAT-Token"] = instance.get("/api/session").json()["token"]
        yield instance


def context(client):
    project = client.get("/api/project")
    state = client.get("/api/state").json()
    return {"X-FAT-Project-ID": project.json()["id"],
            "X-FAT-Project-Revision": project.headers["X-FAT-Project-Revision"],
            "X-FAT-Run-ID": state["run_id"] or ""}


def fake_preview(project):
    return {"image_data_url": "data:image/png;base64,fixture", "width_mm": 420, "height_mm": 297, "warnings": []}


def test_preview_requires_session_and_current_context_before_rendering(client, monkeypatch):
    calls = []
    monkeypatch.setattr(pid_export, "export_pid_preview", lambda project: calls.append(project) or fake_preview(project), raising=False)
    assert client.post("/api/pid/preview", json={}, headers={"X-FAT-Token": ""}).status_code == 403
    for key in ("X-FAT-Project-ID", "X-FAT-Project-Revision", "X-FAT-Run-ID"):
        headers = {**context(client), key: "obsolete"}
        assert client.post("/api/pid/preview", json={}, headers=headers).status_code == 409
    assert calls == []


def test_preview_overrides_only_copy_layout_without_saving_or_approving(client, monkeypatch):
    captured = []
    def render(project):
        captured.append(project.model_dump(mode="json"))
        return fake_preview(project)
    monkeypatch.setattr(pid_export, "export_pid_preview", render, raising=False)
    original = client.get("/api/project").json()
    initial = context(client)
    settings = PidDrawingSettings(company="Entreprise déclarée", document_number="PID-ET-001", revision="B",
                                  status="for_construction", approved_by="Nom déclaré", issue_date="2026-11-11")
    response = client.post("/api/pid/preview", json=settings.model_dump(), headers=initial)
    assert response.status_code == 200, response.text
    assert response.json()["project_revision"] == initial["X-FAT-Project-Revision"]
    assert response.json()["saved_geometry"] is True
    assert captured[0]["pid_drawing"] == settings.model_dump()
    assert captured[0]["equipment"] == original["equipment"]
    assert client.get("/api/project").json() == original
    assert context(client) == initial
    state = client.get("/api/state").json()
    assert state["status"] == "idle" and state["run_id"] is None and state["write_count"] == 0
    assert state["result"]["verdict"] == "not_evaluated"


@pytest.mark.parametrize("invalid", [
    {"sheet_number": 2, "sheet_total": 1}, {"issue_date": "2026-02-30"}, {"company": "A\x00B"},
    {"approved": True}, {"paper_size": "A9"}, {"sheet_number": True},
])
def test_invalid_layout_never_changes_saved_project(client, monkeypatch, invalid):
    def unexpected(project):
        raise AssertionError("Invalid preview reached renderer")
    monkeypatch.setattr(pid_export, "export_pid_preview", unexpected, raising=False)
    before = client.get("/api/project").content
    response = client.post("/api/pid/preview", json=invalid, headers=context(client))
    assert response.status_code == 422, response.text
    assert client.get("/api/project").content == before


def test_heavy_preview_does_not_hold_stop_or_project_mutation_lock(client, monkeypatch):
    entered, release = Event(), Event()
    def heavy(project):
        entered.set()
        assert release.wait(10), "Test failed to release renderer"
        return fake_preview(project)
    monkeypatch.setattr(pid_export, "export_pid_preview", heavy, raising=False)
    assert client.post("/api/run/start", json={}, headers=context(client)).status_code == 200
    initial = context(client)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, "/api/pid/preview", json={}, headers=initial)
        try:
            assert entered.wait(3)
            stopped = client.post("/api/run/stop", json={}, headers=initial)
            assert stopped.status_code == 200, stopped.text
            assert stopped.json()["status"] == "stopped"
        finally:
            release.set()
        assert pending.result(timeout=5).status_code == 200


def test_preview_response_identifies_frozen_saved_geometry_if_revision_changes(client, monkeypatch):
    entered, release = Event(), Event()
    rendered = []
    def heavy(project):
        rendered.append(project.name)
        entered.set()
        assert release.wait(10)
        return fake_preview(project)
    monkeypatch.setattr(pid_export, "export_pid_preview", heavy, raising=False)
    initial = context(client)
    original = client.get("/api/project").json()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, "/api/pid/preview", json={}, headers=initial)
        try:
            assert entered.wait(3)
            changed = {**original, "name": "Révision du dessin pendant l'aperçu"}
            saved = client.put("/api/project", json=changed, headers=initial)
            assert saved.status_code == 200, saved.text
        finally:
            release.set()
        result = pending.result(timeout=5)
    assert result.status_code == 200
    assert rendered == [original["name"]]
    assert result.json()["project_revision"] == initial["X-FAT-Project-Revision"]
    assert context(client)["X-FAT-Project-Revision"] != initial["X-FAT-Project-Revision"]
    assert client.get("/api/project").json()["name"] == changed["name"]


def test_real_preview_is_bounded_png_and_keeps_active_project(client):
    before = client.get("/api/project").content
    headers = context(client)
    response = client.post("/api/pid/preview", json={"paper_size": "A1", "orientation": "portrait", "company": "EXEMPLE"}, headers=headers)
    assert response.status_code == 200, response.text
    preview = response.json()
    assert (preview["width_mm"], preview["height_mm"]) == (594, 841)
    assert preview["image_data_url"].startswith("data:image/png;base64,")
    image_bytes = base64.b64decode(preview["image_data_url"].split(",", 1)[1], validate=True)
    with Image.open(io.BytesIO(image_bytes)) as image:
        assert image.format == "PNG"
        assert 100 < image.width <= 1600 and 100 < image.height <= 1100
        assert image.convert("RGB").getextrema() != ((255, 255),) * 3
    assert client.get("/api/project").content == before
    assert context(client) == headers
