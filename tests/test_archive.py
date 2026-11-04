"""Archive boundaries use temporary stores, never an operator's runtime or PLC."""

from hashlib import sha256
from pathlib import Path
import io
import json
import sqlite3
import zipfile

import pytest

from fat_studio import archive as archives
from fat_studio.archive import capture_archive, export_archive, prepare_archive, restore_archive
from fat_studio.demo import demo_project
from fat_studio.models import Project
from fat_studio.demo_lab import demo_lab_project
from fat_studio.runtime import Runtime
from fat_studio.security import MachinePolicy
from fat_studio.storage import Store


def populate(store, *, project_id="archive-demo", run_id="run-archive", ended=True):
    project = demo_project()
    project.id = project_id
    store.save_project(project)
    store.start_run(run_id, project, project.scenarios[0], {"target": "demo", "mode": "demo"})
    values = {tag.id: tag.initial_value for tag in project.tags}
    qualities = {tag.id: "good" for tag in project.tags}
    store.sample(run_id, .1, values, qualities)
    store.event(run_id, .1, "marker", "Observed example", {"source": "test fixture"})
    if ended:
        store.set_status(run_id, "stopped", ended=True)
    return project


def rewritten(payload, change):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(entries.pop("manifest.json"))
    change(entries, manifest)
    manifest["files"] = [{"path": name, "size": len(value), "sha256": sha256(value).hexdigest()}
                         for name, value in sorted(entries.items())]
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name, value in entries.items():
            archive.writestr(name, value)
    return output.getvalue()


def test_archive_selects_only_project_and_restores_original_evidence_ids(tmp_path):
    source = Store(tmp_path / "source")
    target = Store(tmp_path / "target")
    try:
        project = populate(source)
        populate(source, project_id="other-project", run_id="run-other")
        (source.root / "machine-policy.json").write_text('{"private":"excluded"}')
        (source.root / "client.key").write_text("excluded private credential")
        plan = prepare_archive(export_archive(source, project))
        assert plan.project_id == project.id and plan.run_count == 1
        assert set(dict(plan.files)) == {"project.json", "scenarios.json", "mapping.csv",
                                        "runs/run-archive/evidence.json", "runs/run-archive/samples.csv",
                                        "runs/run-archive/report.html"}
        restored = restore_archive(target, plan)
        assert restored.id == project.id and restored.plc.mode == "demo"
        assert not (target.root / "machine-policy.json").exists()
        assert not (target.root / "client.key").exists()
        original, recovered = source.run("run-archive"), target.run("run-archive")
        for key in ("id", "started_at", "ended_at", "result", "events", "scenario", "project", "connection"):
            assert original[key] == recovered[key]
        assert list(source.samples("run-archive")) == list(target.samples("run-archive"))
        assert target.last_project().id == project.id
        assert (target.root / "archive-source.fat.zip").read_bytes() == plan.payload
    finally:
        source.close()
        target.close()


def test_pre_branding_real_archive_keeps_its_original_reports_and_history(tmp_path):
    fixture = (Path(__file__).resolve().parents[1] / "evidence/reprises/2026-11-03-public-demo"
               / "final-live/project-with-real-history.fat.zip")
    payload = fixture.read_bytes()
    assert sha256(payload).hexdigest() == "5c38800d698626d7a4700465c7e41bf711b9f328afe68d49cbf48752ed3f5bb1"
    plan = prepare_archive(payload)
    store = Store(tmp_path / "restored")
    try:
        project = restore_archive(store, plan)
        assert project.plc.mode == "demo"
        assert len(store.runs()) == plan.run_count
        for name, content in plan.files:
            if name.endswith("/evidence.json"):
                original = json.loads(content)
                recovered = store.run(original["id"])
                assert recovered["project"] == original["project"]
                assert recovered["result"] == original["result"]
                assert recovered["events"] == original["events"]
                assert list(store.samples(original["id"])) == original["samples"]
                if original["ended_at"] is not None:
                    assert recovered["status"] == original["status"]
                    assert recovered["ended_at"] == original["ended_at"]
        assert (store.root / "archive-source.fat.zip").read_bytes() == payload
        assert not (store.root / "machine-policy.json").exists()
    finally:
        store.close()


def test_empty_project_can_be_archived_without_a_fake_scenario(tmp_path):
    source, target = Store(tmp_path / "source"), Store(tmp_path / "target")
    try:
        project = Project(id="empty", name="Empty draft")
        plan = prepare_archive(export_archive(source, project))
        assert plan.run_count == 0 and "scenarios.json" not in dict(plan.files)
        assert plan.validation["valid"] is False
        restored = restore_archive(target, plan)
        assert restored.id == project.id and restored.scenarios == []
    finally:
        source.close()
        target.close()


def test_pinned_archive_survives_new_samples_results_runs_and_store_close(tmp_path):
    store = Store(tmp_path)
    reader = None
    try:
        project = populate(store, ended=False)
        before = store.run("run-archive")
        reader = capture_archive(store, project)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            reader.db.execute("UPDATE runs SET status='stopped'")
        project.name = "Edited after capture"
        store.sample("run-archive", .2, {tag.id: tag.initial_value for tag in project.tags},
                     {tag.id: "good" for tag in project.tags})
        store.set_status("run-archive", "stopped", ended=True)
        store.set_result("run-archive", "fail", "Synthetic tester result after archive capture")
        store.start_run("run-later", project, None, {"target": "demo"})
    finally:
        store.close()
    try:
        # The writer is closed, while the read-only transaction still owns its exact view.
        payload = export_archive(reader, reader.project)
        plan = prepare_archive(payload)
        assert plan.run_count == 1 and plan.project.name != project.name
        record = json.loads(dict(plan.files)["runs/run-archive/evidence.json"])
        assert record["sample_count"] == 1
        assert record["status"] == "running" and record["ended_at"] is None
        assert record["result"]["verdict"] == "not_evaluated"
        assert record["events"] == before["events"]
        assert record["snapshot"]["captured_at"] == reader.captured_at
        assert len(record["samples"]) == 1
    finally:
        if reader is not None:
            reader.close()
            reader.close()


@pytest.mark.asyncio
async def test_archive_restores_guided_wire_evidence_without_creating_an_observation(tmp_path):
    source, target = Store(tmp_path / "source"), Store(tmp_path / "target")
    runtime = Runtime(source, demo_lab_project(), MachinePolicy(source.root / "policy.json"))
    try:
        await runtime.start("demo-guided-io", background=False)
        await runtime.execute_fat_step("guided-initial")
        await runtime.tick()
        await runtime.tick()
        run_id = runtime.run_id
        await runtime.stop()
        plan = prepare_archive(export_archive(source, runtime.project))
        restore_archive(target, plan)
        recovered = target.run(run_id)
        applied = next(event for event in recovered["events"] if event["kind"] == "fat_step_applied")
        level = next(action for action in applied["details"]["actions"] if action["target"] == "lt101_raw")
        assert level["actual_wire_value"] == level["raw_value"] == 13824
        assert not any(event["kind"] == "fat_step_observed" for event in recovered["events"])
        assert recovered["result"]["verdict"] == "not_evaluated"
    finally:
        if runtime.status in {"running", "paused"}:
            await runtime.stop()
        source.close()
        target.close()


@pytest.mark.asyncio
async def test_mixed_completed_timed_guided_and_stopped_history_round_trips(tmp_path):
    source, target = Store(tmp_path / "source"), Store(tmp_path / "target")
    runtime = Runtime(source, demo_lab_project(), MachinePolicy(source.root / "policy.json"))
    run_ids = []
    try:
        await runtime.start("demo-fill-source", background=False)
        run_ids.append(runtime.run_id)
        for _ in range(80):
            if runtime.status != "running":
                break
            await runtime.tick()
        assert source.run(run_ids[-1])["status"] == "completed"
        await runtime.stop()
        await runtime.reset()
        await runtime.start("demo-guided-io", background=False)
        run_ids.append(runtime.run_id)
        for step in runtime.scenario.fat_steps:
            await runtime.execute_fat_step(step.id)
            for _ in range(15):
                await runtime.tick()
            # Explicit synthetic tester input in this fixture, never a human FAT acceptance.
            await runtime.observe_fat_step(step.id, "pass", "Synthetic tester observation for archive regression")
        assert source.run(run_ids[-1])["status"] == "completed"
        await runtime.stop()
        await runtime.reset()
        await runtime.start(background=False)
        run_ids.append(runtime.run_id)
        await runtime.tick()
        await runtime.stop()
        assert source.run(run_ids[-1])["status"] == "stopped"
        plan = prepare_archive(export_archive(source, runtime.project))
        assert plan.run_count == 3
        restore_archive(target, plan)
        for run_id in run_ids:
            original, restored = source.run(run_id), target.run(run_id)
            for key in ("status", "started_at", "ended_at", "result", "events", "scenario", "project"):
                assert original[key] == restored[key]
            assert list(source.samples(run_id)) == list(target.samples(run_id))
        assert all(target.run(run_id)["result"]["verdict"] == "not_evaluated" for run_id in run_ids)
    finally:
        if runtime.status in {"running", "paused"}:
            await runtime.stop()
        source.close()
        target.close()


def test_archive_uses_same_finite_run_snapshot_for_all_exports(tmp_path, monkeypatch):
    source = Store(tmp_path / "source")
    try:
        project = populate(source, ended=False)
        samples = source.samples
        added = False

        def later(run_id, *, through_id=None):
            nonlocal added
            if not added:
                added = True
                source.sample(run_id, .2, {tag.id: tag.initial_value for tag in project.tags},
                              {tag.id: "good" for tag in project.tags})
            return samples(run_id, through_id=through_id)

        monkeypatch.setattr(source, "samples", later)
        plan = prepare_archive(export_archive(source, project))
        files = dict(plan.files)
        evidence = json.loads(files["runs/run-archive/evidence.json"])
        assert source.run("run-archive")["sample_count"] == 2
        assert evidence["sample_count"] == len(evidence["samples"]) == 1
        assert len(files["runs/run-archive/samples.csv"].decode("utf-8-sig").splitlines()) == len(project.tags) + 1
        assert b"1 cycles" in files["runs/run-archive/report.html"]
    finally:
        source.close()


def test_restore_is_disconnected_and_frozen_run_never_resumes(tmp_path):
    source = Store(tmp_path / "source")
    target = Store(tmp_path / "target")
    try:
        project = populate(source, ended=False)
        project.plc.client_private_key = "private/client.key"
        project.plc.client_certificate = "private/client.cer"
        project.plc.password_env = "PRIVATE_PLC_PASSWORD"
        plan = prepare_archive(export_archive(source, project))
        restored = restore_archive(target, plan)
        assert restored.plc.mode == "demo"
        assert not restored.plc.client_private_key and not restored.plc.client_certificate
        assert not restored.plc.password_env and not restored.plc.username_env
        assert target.run("run-archive")["status"] == "interrupted"
        assert target.run("run-archive")["result"]["verdict"] == "not_evaluated"
        archived = json.loads(dict(plan.files)["runs/run-archive/evidence.json"])
        assert archived["status"] == "running" and archived["ended_at"] is None
    finally:
        source.close()
        target.close()


@pytest.mark.parametrize("collision", ["project", "run", "policy"])
def test_restore_refuses_populated_target_before_any_mutation(tmp_path, collision):
    source, target = Store(tmp_path / "source"), Store(tmp_path / "target")
    try:
        project = populate(source)
        plan = prepare_archive(export_archive(source, project))
        if collision == "project":
            target.save_project(project)
        elif collision == "run":
            target.start_run("run-archive", project, None, {"target": "demo"})
        else:
            (target.root / "machine-policy.json").write_text("{}")
        before = (list(target.db.execute("SELECT * FROM runs")), list(target.projects_dir.iterdir()))
        with pytest.raises(ValueError, match="new empty"):
            restore_archive(target, plan)
        assert list(target.db.execute("SELECT * FROM runs")) == before[0]
        assert list(target.projects_dir.iterdir()) == before[1]
        assert not (target.root / "archive-source.fat.zip").exists()
    finally:
        source.close()
        target.close()


@pytest.mark.parametrize("path", ["../escape.json", "/absolute.json", "C:/escape.json", "runs\\bad.json",
                                  "runs/CON.json", "runs/item. /evidence.json"])
def test_archive_rejects_traversal_ambiguous_and_reserved_paths(tmp_path, path):
    store = Store(tmp_path)
    try:
        project = populate(store)
        data = export_archive(store, project)
        bad = rewritten(data, lambda files, _: files.update({path: b"{}"}))
        with pytest.raises(ValueError):
            prepare_archive(bad)
    finally:
        store.close()


@pytest.mark.parametrize("damage", ["version", "hash", "private", "run_identity", "sample_type", "scenario", "mapping"])
def test_archive_rejects_corruption_or_contract_mismatch(tmp_path, damage):
    store = Store(tmp_path)
    try:
        project = populate(store)
        data = export_archive(store, project)

        def change(files, manifest):
            if damage == "version":
                manifest["version"] = "99.0"
            elif damage == "hash":
                files["project.json"] = b"not JSON"
            elif damage == "private":
                files["machine-policy.json"] = b"{}"
            elif damage in {"run_identity", "sample_type"}:
                name = "runs/run-archive/evidence.json"
                document = json.loads(files[name])
                if damage == "run_identity":
                    document["id"] = "another-run"
                else:
                    tag = next(tag for tag in project.tags if tag.data_type == "BOOL")
                    document["samples"][0]["values"][tag.id] = "true"
                files[name] = json.dumps(document).encode()
            elif damage == "scenario":
                files["scenarios.json"] = b"{}"
            else:
                files["mapping.csv"] = b"invalid,mapping\n"

        with pytest.raises(ValueError):
            prepare_archive(rewritten(data, change))
    finally:
        store.close()


def test_archive_rejects_links_duplicate_paths_and_bombs(tmp_path, monkeypatch):
    source = Store(tmp_path)
    try:
        project = populate(source)
        payload = export_archive(source, project)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = [(item, archive.read(item)) for item in archive.infolist()]
        for kind in ("link", "duplicate"):
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w") as archive:
                for item, content in entries:
                    archive.writestr(item, content)
                if kind == "link":
                    link = zipfile.ZipInfo("linked")
                    link.external_attr = 0o120777 << 16
                    archive.writestr(link, b"outside")
                else:
                    # Case collision is also ambiguous on target Windows filesystems.
                    archive.writestr("PROJECT.JSON", b"{}")
            with pytest.raises(ValueError):
                prepare_archive(output.getvalue())
        monkeypatch.setattr(archives, "MAX_EXPANDED_BYTES", 10)
        with pytest.raises(ValueError, match="expansion"):
            prepare_archive(payload)
    finally:
        source.close()
