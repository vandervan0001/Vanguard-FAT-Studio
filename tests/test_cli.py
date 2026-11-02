import json
from pathlib import Path

import pytest

from fat_studio.cli import default_data_dir, main, parser
from fat_studio.models import PLCConfig
from fat_studio.security import MachinePolicy


def authorization_args(tmp_path):
    return ["authorize-target", "--name", "PLCSIM_Test", "--endpoint", "opc.tcp://127.0.0.1:4840",
            "--application-uri", "urn:local:test:virtual", "--data-dir", str(tmp_path),
            "--isolated-virtual-adapter", "--allow-insecure"]


def test_network_listening_cannot_be_enabled_by_cli():
    with pytest.raises(SystemExit) as caught:
        parser().parse_args(["serve", "--host", "0.0.0.0"])
    assert caught.value.code == 2


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_loopback_hosts_are_available(host):
    assert parser().parse_args(["serve", "--host", host]).host == host


@pytest.mark.parametrize("port", ["0", "65536", "-1"])
def test_invalid_port_refused(port):
    with pytest.raises(SystemExit):
        parser().parse_args(["serve", "--port", port])


def test_data_directory_environment_is_respected(tmp_path, monkeypatch):
    monkeypatch.setenv("FAT_STUDIO_DATA", str(tmp_path / "chosen"))
    assert default_data_dir() == (tmp_path / "chosen").resolve()


def test_wrong_target_confirmation_never_creates_policy(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    assert main(authorization_args(tmp_path)) == 2
    assert not (tmp_path / "machine-policy.json").exists()


def test_target_authorization_requires_explicit_isolation(tmp_path, monkeypatch):
    arguments = authorization_args(tmp_path)
    arguments.remove("--isolated-virtual-adapter")
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("Must be refused before confirmation"))
    assert main(arguments) == 2
    assert not (tmp_path / "machine-policy.json").exists()


def test_target_authorization_persists_exact_identity(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "PLCSIM_Test @ opc.tcp://127.0.0.1:4840")
    assert main(authorization_args(tmp_path)) == 0
    policy = MachinePolicy(tmp_path / "machine-policy.json")
    config = PLCConfig(mode="opcua", approved_virtual_target="PLCSIM_Test", expected_application_uri="urn:local:test:virtual")
    entry = policy.authorize(config, "PLCSIM_Test @ opc.tcp://127.0.0.1:4840")
    assert entry["isolated_virtual_adapter_confirmed"] is True
    assert entry["allow_insecure"] is True
    assert entry["username_env"] == ""
    assert entry["client_private_key"] == ""


def test_public_target_refused_without_prompt(tmp_path, monkeypatch):
    arguments = authorization_args(tmp_path)
    arguments[arguments.index("--endpoint") + 1] = "opc.tcp://8.8.8.8:4840"
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("Must be refused before confirmation"))
    assert main(arguments) == 2


def test_insecure_credentials_are_not_authorized(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("Must be refused before confirmation"))
    assert main(authorization_args(tmp_path) + ["--username-env", "FAT_USER", "--password-env", "FAT_PASSWORD"]) == 2
    assert not (tmp_path / "machine-policy.json").exists()


def test_secure_authorization_pins_local_cert_paths_and_env_names(tmp_path, monkeypatch):
    certificate = tmp_path / "client.der"
    key = tmp_path / "private.pem"
    certificate.write_bytes(b"test file, no TLS connection is attempted by authorization")
    key.write_bytes(b"test key file")
    arguments = authorization_args(tmp_path)
    arguments.remove("--allow-insecure")
    arguments += ["--server-certificate-sha256", "a" * 64, "--client-certificate", str(certificate),
                  "--client-private-key", str(key), "--username-env", "FAT_USER", "--password-env", "FAT_PASSWORD"]
    monkeypatch.setattr("builtins.input", lambda _: "PLCSIM_Test @ opc.tcp://127.0.0.1:4840")
    assert main(arguments) == 0
    entry = MachinePolicy(tmp_path / "machine-policy.json").entries()[0]
    assert entry["client_private_key"] == str(key.resolve())
    assert entry["server_certificate_sha256"] == "a" * 64
    assert entry["allow_insecure"] is False
    assert entry["username_env"] == "FAT_USER"


def test_doctor_reports_installation_without_claiming_siemens_validation(tmp_path, capsys):
    result = main(["doctor", "--json", "--data-dir", str(tmp_path)])
    report = json.loads(capsys.readouterr().out)
    assert result in (0, 1)
    assert report["authorized_target_count"] == 0
    assert report["data_dir"] == str(tmp_path.resolve())
    assert "Non vérifiée" in report["siemens_validation"]
    assert not (tmp_path / "machine-policy.json").exists()


def test_siemens_exchange_declarations_match_demo_tags():
    import re
    from fat_studio.demo import demo_project
    source = (Path(__file__).parents[1] / "siemens" / "DB_FAT.scl").read_text(encoding="utf-8")
    declarations = dict(re.findall(r"^\s+(\w+)\s*:\s*(Bool|Real);", source, flags=re.MULTILINE))
    expected = {tag.name: {"BOOL": "Bool", "REAL": "Real"}[tag.data_type] for tag in demo_project().tags}
    assert declarations == expected
