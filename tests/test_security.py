"""Local authorization is independent of imported projects and web requests."""

import json

import pytest

from fat_studio.models import PLCConfig
from fat_studio.security import MachinePolicy, TargetDenied, atomic_json, safe_id, validate_endpoint


@pytest.mark.parametrize("endpoint", [
    "opc.tcp://127.0.0.1:4840/fat/", "opc.tcp://192.168.25.10:4840", "opc.tcp://[::1]:4840",
    "opc.tcp://10.12.34.5:4840", "opc.tcp://172.16.1.2:4840",
])
def test_explicit_private_or_loopback_endpoint(endpoint):
    assert validate_endpoint(endpoint)


@pytest.mark.parametrize("endpoint", [
    "http://127.0.0.1:4840", "opc.tcp://example.com:4840", "opc.tcp://8.8.8.8:4840",
    "opc.tcp://0.0.0.0:4840", "opc.tcp://[::]:4840", "opc.tcp://239.1.2.3:4840",
    "opc.tcp://user:secret@127.0.0.1:4840", "opc.tcp://@127.0.0.1:4840", "opc.tcp://127.0.0.1", "opc.tcp://127.0.0.1:0",
    "opc.tcp://127.0.0.1:99999", "opc.tcp://127.0.0.1:4840?q=x", "opc.tcp://127.0.0.1:4840#x",
    " opc.tcp://127.0.0.1:4840", "opc.tcp://127.0.0.1:4840\n", "opc.tcp://127.0.0.1\t:4840", "",
])
def test_unapproved_address_forms_are_denied(endpoint):
    with pytest.raises(TargetDenied):
        validate_endpoint(endpoint)


@pytest.fixture
def entry():
    return {"endpoint": "opc.tcp://127.0.0.1:4840", "expected_application_uri": "urn:fat:protocol-test",
            "approved_virtual_target": "Generic OPC UA fixture", "isolated_virtual_adapter_confirmed": True,
            "allow_insecure": True, "server_certificate_sha256": ""}


def config(entry):
    return PLCConfig(mode="opcua", **{key: value for key, value in entry.items()
                                     if key in PLCConfig.model_fields})


def test_imported_project_cannot_authorize_target(tmp_path, entry):
    policy = MachinePolicy(tmp_path / "policy.json")
    with pytest.raises(TargetDenied, match="absente"):
        policy.authorize(config(entry), "Generic OPC UA fixture @ opc.tcp://127.0.0.1:4840")
    assert not policy.path.exists()


def test_policy_requires_identity_and_exact_confirmation(tmp_path, entry):
    policy = MachinePolicy(tmp_path / "policy.json")
    policy.add(entry)
    plc = config(entry)
    assert policy.authorize(plc, f"{plc.approved_virtual_target} @ {plc.endpoint}") == entry
    with pytest.raises(TargetDenied, match="exactement"):
        policy.authorize(plc, "yes")
    plc.expected_application_uri = "urn:another:server"
    with pytest.raises(TargetDenied, match="identité"):
        policy.authorize(plc)


@pytest.mark.parametrize("field", ["username_env", "password_env", "client_certificate", "client_private_key"])
def test_imported_project_cannot_select_arbitrary_machine_secrets(tmp_path, entry, field):
    policy = MachinePolicy(tmp_path / "policy.json")
    policy.add(entry)
    plc = config(entry)
    setattr(plc, field, "UNAPPROVED_SECRET" if field.endswith("env") else "C:\\unapproved\\secret.pem")
    with pytest.raises(TargetDenied, match=field):
        policy.authorize(plc)
    policy.add({**entry, field: getattr(plc, field)})
    assert policy.authorize(plc)


def test_policy_revocation_is_reloaded(tmp_path, entry):
    policy = MachinePolicy(tmp_path / "policy.json")
    policy.add(entry)
    assert policy.authorize(config(entry))
    atomic_json(policy.path, {"version": 1, "targets": []})
    with pytest.raises(TargetDenied, match="absente"):
        policy.authorize(config(entry))


@pytest.mark.parametrize("value", [None, [], {"version": 2, "targets": []}, {"version": True, "targets": []}, {"version": 1, "targets": [None]}])
def test_malformed_local_policy_fails_closed(tmp_path, value):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(TargetDenied, match="Politique locale invalide"):
        MachinePolicy(path).entries()


def test_duplicate_or_unconfirmed_target_is_denied(tmp_path, entry):
    path = tmp_path / "policy.json"
    atomic_json(path, {"version": 1, "targets": [entry, entry]})
    with pytest.raises(TargetDenied):
        MachinePolicy(path).authorize(config(entry))
    policy = MachinePolicy(path)
    policy.add({**entry, "isolated_virtual_adapter_confirmed": False})
    with pytest.raises(TargetDenied, match="isolation"):
        policy.authorize(config(entry))


def test_encryption_requires_pinned_server_certificate(tmp_path, entry):
    policy = MachinePolicy(tmp_path / "policy.json")
    policy.add({**entry, "allow_insecure": False})
    plc = config(entry)
    with pytest.raises(TargetDenied, match="sans chiffrement"):
        policy.authorize(plc)
    plc.security_policy = "Basic256Sha256"
    with pytest.raises(TargetDenied, match="empreinte serveur"):
        policy.authorize(plc)
    plc.server_certificate_sha256 = "1" * 64
    with pytest.raises(TargetDenied, match="empreinte du certificat"):
        policy.authorize(plc)
    policy.add({**entry, "allow_insecure": False, "server_certificate_sha256": "1" * 64})
    assert policy.authorize(plc)


@pytest.mark.parametrize("value", ["../x", "x/y", "x\\y", "/etc/passwd", "..", "a\n", "a" * 81])
def test_file_identifiers_cannot_escape(value):
    with pytest.raises(ValueError):
        safe_id(value)
