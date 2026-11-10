"""Saved local identities and finite read-only connection checks."""

import json

import httpx
import pytest
from asyncua.server.internal_session import InternalSession

from fat_studio.adapters.opcua import IdentityClient, MappingError
from fat_studio.app import create_app
from fat_studio.known_targets import check_known_target, known_targets, preview_known_target
from fat_studio.models import Project
from fat_studio.opcua_browser import MetadataBrowser
from fat_studio.security import MachinePolicy, TargetDenied, atomic_json
from test_opcua import build_fixture


def entry(**changes):
    return {"endpoint": "opc.tcp://127.0.0.1:4867", "expected_application_uri": "urn:local:test",
            "approved_virtual_target": "Local fixture", "isolated_virtual_adapter_confirmed": True,
            "allow_insecure": True, "server_certificate_sha256": "", **changes}


def saved(tmp_path, **changes):
    policy = MachinePolicy(tmp_path / "machine-policy.json")
    policy.add(entry(**changes))
    return policy


def test_targets_are_only_machine_policy_and_never_expose_auth_references(tmp_path, monkeypatch):
    policy = saved(tmp_path, allow_insecure=False, server_certificate_sha256="ab" * 32,
                   username_env="TEST_TARGET_USER", password_env="TEST_TARGET_PASSWORD",
                   client_certificate="C:/private/client.der", client_private_key="C:/private/client.key")
    monkeypatch.setenv("TEST_TARGET_PASSWORD", "private-password-value")
    before = policy.path.read_bytes()
    response = known_targets(policy)
    serialized = json.dumps(response)
    assert response["editable_from_browser"] is False
    target = response["targets"][0]
    assert target["authentication_required"] and target["selectable"]
    assert target["security_policy"] == "Basic256Sha256" and len(target["id"]) == 64
    for private in ("TEST_TARGET_USER", "TEST_TARGET_PASSWORD", "private-password-value", "C:/private", "client_private_key", "password_env"):
        assert private not in serialized
    assert policy.path.read_bytes() == before
    assert known_targets(MachinePolicy(tmp_path / "other-post-policy.json"))["targets"] == []


def test_target_selection_previews_only_and_clears_other_identity_references(tmp_path):
    policy = saved(tmp_path)
    project = Project(id="select", name="Untouched project")
    project.plc.namespace_uri = "urn:old:namespace"
    project.plc.username_env, project.plc.password_env = "OLD_USER", "OLD_PASSWORD"
    project.plc.client_certificate, project.plc.client_private_key = "old.der", "old.key"
    project.simulation.speed = 5
    original = project.model_dump()
    before = policy.path.read_bytes()
    target = known_targets(policy)["targets"][0]
    result = preview_known_target(project, policy, target["id"])
    configured = Project.model_validate(result["project"])
    assert configured.plc.endpoint == entry()["endpoint"]
    assert configured.plc.expected_application_uri == "urn:local:test"
    assert configured.plc.approved_virtual_target == "Local fixture"
    assert configured.plc.mode == "opcua" and configured.plc.security_policy == "None"
    assert configured.simulation.speed == 1
    assert not any(getattr(configured.plc, field) for field in ("username_env", "password_env", "client_certificate", "client_private_key", "namespace_uri"))
    assert not result["authentication_required"]
    assert project.model_dump() == original and policy.path.read_bytes() == before


def test_same_exact_identity_keeps_only_matching_authentication(tmp_path):
    policy = saved(tmp_path, allow_insecure=False, server_certificate_sha256="ab" * 32,
                   username_env="TEST_USER", password_env="TEST_PASSWORD",
                   client_certificate="client.der", client_private_key="client.key")
    project = Project(id="exact", name="Exact target")
    for key in ("endpoint", "expected_application_uri", "approved_virtual_target", "server_certificate_sha256",
                "username_env", "password_env", "client_certificate", "client_private_key"):
        setattr(project.plc, key, policy.entries()[0].get(key, ""))
    project.plc.mode, project.plc.security_policy = "opcua", "Basic256Sha256"
    project.plc.namespace_uri = "urn:kept:namespace"
    target = known_targets(policy)["targets"][0]
    result = preview_known_target(project, policy, target["id"])
    assert result["project"]["plc"] == project.plc.model_dump()
    assert result["authentication_required"] is False
    project.plc.password_env = "OLD_PASSWORD"
    result = preview_known_target(project, policy, target["id"])
    assert result["authentication_required"] is True
    assert result["project"]["plc"]["password_env"] == ""
    assert result["project"]["plc"]["client_private_key"] == ""
    assert "client.key" not in json.dumps(result)


def test_revoked_or_changed_target_requires_refresh(tmp_path):
    policy = saved(tmp_path)
    target_id = known_targets(policy)["targets"][0]["id"]
    project = Project(id="revoked", name="Local draft")
    policy.add(entry(approved_virtual_target="Changed locally"))
    with pytest.raises(TargetDenied, match="Actualisez"):
        preview_known_target(project, policy, target_id)
    current = known_targets(policy)["targets"][0]["id"]
    atomic_json(policy.path, {"version": 1, "targets": []})
    with pytest.raises(TargetDenied, match="Actualisez"):
        preview_known_target(project, policy, current)
    assert known_targets(policy)["targets"] == []


@pytest.mark.parametrize("changes", [{"isolated_virtual_adapter_confirmed": False},
                                     {"allow_insecure": False, "server_certificate_sha256": "bad"},
                                     {"username_env": "USER", "password_env": "PASSWORD"}])
def test_incomplete_policy_entries_cannot_be_selected(tmp_path, changes):
    policy = saved(tmp_path, **changes)
    target = known_targets(policy)["targets"][0]
    assert not target["selectable"] and target["reason"]
    with pytest.raises(TargetDenied):
        preview_known_target(Project(id="incomplete", name="Draft"), policy, target["id"])


def test_duplicate_policy_endpoint_is_visible_but_unselectable(tmp_path):
    policy = saved(tmp_path)
    atomic_json(policy.path, {"version": 1, "targets": [entry(), entry(approved_virtual_target="Other identity")]})
    assert len(known_targets(policy)["targets"]) == 2
    assert not any(target["selectable"] for target in known_targets(policy)["targets"])


@pytest.mark.parametrize("encrypted", [False, True])
async def test_real_check_verifies_identity_without_process_reads_or_writes(tmp_path, unused_tcp_port, monkeypatch, encrypted):
    fixture = await build_fixture(tmp_path, unused_tcp_port, encrypted=encrypted)
    writes, process_reads = [], []
    original_write, original_read = InternalSession.write, InternalSession.read
    process_ids = {node.nodeid for node in fixture.nodes.values()}

    async def write(session, params):
        writes.extend(params.NodesToWrite)
        return await original_write(session, params)

    async def read(session, params):
        process_reads.extend(node for node in params.NodesToRead if node.NodeId in process_ids)
        return await original_read(session, params)

    monkeypatch.setattr(InternalSession, "write", write)
    monkeypatch.setattr(InternalSession, "read", read)
    try:
        # Missing mappings are permitted here; this test must not imply tag validation.
        fixture.project.tags[0].node_id = ""
        confirmation = f"{fixture.project.plc.approved_virtual_target} @ {fixture.project.plc.endpoint}"
        result = await check_known_target(fixture.project, fixture.policy, confirmation)
        assert result["connected"] and result["identity_verified"] and not result["mapping_checked"]
        assert result["namespace_index"] is not None
        assert writes == [] and process_reads == []
    finally:
        await fixture.stop()


async def test_actual_identity_is_checked_before_activation(tmp_path, unused_tcp_port, monkeypatch):
    fixture = await build_fixture(tmp_path, unused_tcp_port)
    fixture.project.plc.expected_application_uri = "urn:wrong:identity"
    local = fixture.policy.entries()[0]
    local["expected_application_uri"] = "urn:wrong:identity"
    fixture.policy.add(local)
    activated = []
    original = IdentityClient.activate_session

    async def activate(client, *args, **kwargs):
        activated.append(True)
        return await original(client, *args, **kwargs)

    monkeypatch.setattr(IdentityClient, "activate_session", activate)
    confirmation = f"{fixture.project.plc.approved_virtual_target} @ {fixture.project.plc.endpoint}"
    try:
        with pytest.raises(TargetDenied, match="ApplicationUri"):
            await check_known_target(fixture.project, fixture.policy, confirmation)
        assert activated == []
        with pytest.raises(TargetDenied, match="Confirmer"):
            await check_known_target(fixture.project, fixture.policy, "Wrong target")
        assert activated == []
    finally:
        await fixture.stop()


async def test_check_rejects_demo_and_unknown_policy_without_transport(tmp_path, monkeypatch):
    project = Project(id="no-target", name="Draft")
    policy = MachinePolicy(tmp_path / "empty.json")
    with pytest.raises(MappingError, match="mode OPC UA"):
        await check_known_target(project, policy, "none")
    project.plc.mode = "opcua"
    project.plc.expected_application_uri = "urn:imported"
    project.plc.approved_virtual_target = "Imported identity"

    def unexpected(*args, **kwargs):
        raise AssertionError("Policy refusal must precede transport creation")

    monkeypatch.setattr(MetadataBrowser, "_create_client", unexpected)
    with pytest.raises(TargetDenied, match="politique"):
        await check_known_target(project, policy, f"{project.plc.approved_virtual_target} @ {project.plc.endpoint}")


async def test_api_target_preview_is_context_guarded_and_never_saves(tmp_path):
    app = create_app(tmp_path)
    async with app.router.lifespan_context(app):
        app.state.policy.add(entry())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            original_response = await client.get("/api/project")
            original = original_response.json()
            headers = {"X-FAT-Token": (await client.get("/api/session")).json()["token"],
                       "X-FAT-Project-ID": original["id"], "X-FAT-Project-Revision": original_response.headers["X-FAT-Project-Revision"], "X-FAT-Run-ID": ""}
            target = (await client.get("/api/connection/targets")).json()["targets"][0]
            body = {"project": original, "target_id": target["id"]}
            assert (await client.post("/api/connection/targets/preview", json=body)).status_code == 403
            assert (await client.post("/api/connection/targets/preview", json=body, headers={"X-FAT-Token": headers["X-FAT-Token"]})).status_code == 409
            response = await client.post("/api/connection/targets/preview", json=body, headers=headers)
            assert response.status_code == 200, response.text
            assert response.json()["project"]["plc"]["mode"] == "opcua"
            assert "X-FAT-Project-Revision" not in response.headers
            assert (await client.get("/api/project")).json() == original
            stale = {**headers, "X-FAT-Project-Revision": "stale"}
            assert (await client.post("/api/connection/targets/preview", json=body, headers=stale)).status_code == 409
            imported = {**original, "id": "different-project"}
            assert (await client.post("/api/connection/targets/preview", json={**body, "project": imported}, headers=headers)).status_code == 409
            atomic_json(app.state.policy.path, {"version": 1, "targets": []})
            assert (await client.post("/api/connection/targets/preview", json=body, headers=headers)).status_code == 403
            assert (await client.get("/api/connection/targets")).json()["targets"] == []


async def test_api_read_only_check_keeps_runtime_and_project_unchanged(tmp_path, unused_tcp_port):
    fixture = await build_fixture(tmp_path / "ua", unused_tcp_port)
    app = create_app(tmp_path / "app")
    try:
        async with app.router.lifespan_context(app):
            app.state.policy.add(fixture.policy.entries()[0])
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
                before = await client.get("/api/project")
                original = before.json()
                draft = fixture.project.model_dump(mode="json")
                draft["id"] = original["id"]
                headers = {"X-FAT-Token": (await client.get("/api/session")).json()["token"],
                           "X-FAT-Project-ID": draft["id"], "X-FAT-Project-Revision": before.headers["X-FAT-Project-Revision"], "X-FAT-Run-ID": ""}
                body = {"project": draft, "confirmation": f"{fixture.project.plc.approved_virtual_target} @ {fixture.project.plc.endpoint}"}
                result = await client.post("/api/connection/check", json=body, headers=headers)
                assert result.status_code == 200, result.text
                assert result.json()["identity_verified"] and not result.json()["mapping_checked"]
                assert (await client.get("/api/project")).json() == original
                assert "X-FAT-Project-Revision" not in result.headers
                state = (await client.get("/api/state")).json()
                assert state["status"] == "idle" and state["run_id"] is None and state["write_count"] == 0
                stale = {**headers, "X-FAT-Run-ID": "stale-run"}
                assert (await client.post("/api/connection/check", json=body, headers=stale)).status_code == 409
                started = await client.post("/api/run/start", json={}, headers=headers)
                assert started.status_code == 200
                headers["X-FAT-Run-ID"] = started.json()["run_id"]
                assert (await client.post("/api/connection/check", json=body, headers=headers)).status_code == 409
                await client.post("/api/run/stop", headers=headers)
    finally:
        await fixture.stop()
