"""The local IA client is exercised against an isolated real HTTP service."""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

from fat_studio.assistant import LocalClient, json_value, local_url, main


@pytest.fixture
def service(tmp_path):
    with socket.socket() as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        port = port_socket.getsockname()[1]
    process = subprocess.Popen([sys.executable, "-m", "fat_studio", "serve", "--host", "127.0.0.1",
                                "--port", str(port), "--data-dir", str(tmp_path / "data"), "--no-browser"],
                               cwd=Path(__file__).resolve().parents[1], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    client = LocalClient(f"http://127.0.0.1:{port}", tmp_path / "context.json")
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail("Temporary FAT HTTP service exited during startup")
            try:
                client.request("/api/health")
                break
            except ValueError:
                time.sleep(.05)
        else:
            pytest.fail("Temporary FAT HTTP service did not become ready")
        token = client.request("/api/session")[0]["token"]
        client.request("/api/demo/load", "POST", {}, headers={"X-FAT-Token": token})
        yield client
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.mark.parametrize("url", ["http://192.168.1.1:8765", "http://localhost:8765", "https://127.0.0.1:8765",
                                 "http://127.0.0.1", "http://user:password@127.0.0.1:8765", "http://127.0.0.1:8765/api",
                                 "http://127.0.0.1:8765?token=secret", "http://[::]:8765"])
def test_assistant_rejects_any_url_outside_the_explicit_local_http_service(url):
    with pytest.raises(argparse.ArgumentTypeError):
        local_url(url)


def test_helper_context_advances_only_after_success_and_never_stores_session_secret(service):
    with pytest.raises(ValueError, match="Capturer"):
        service.mutate("/api/pilot/load", body={})
    initial = service.capture()
    pilot = service.mutate("/api/pilot/load", body={})
    assert pilot["id"] == "public-io-lab"
    after = json.loads(service.context_path.read_text())
    assert after["project_id"] != initial["project_id"] and after["run_id"] is None
    assert "token" not in service.context_path.read_text()
    state = service.mutate("/api/run/start", body={})
    assert state["run_id"] == json.loads(service.context_path.read_text())["run_id"]
    service.mutate("/api/force/stimulus", body=dict(tag_id="lt101_raw", unit="mA", value=12))
    state, _ = service.request("/api/state")
    assert state["tags"]["lt101_raw"]["value"] == 13824
    service.mutate("/api/run/stop", body={})


def test_opening_the_active_workspace_preserves_the_clients_run_context(service):
    service.capture()
    started = service.mutate("/api/run/start", body={})
    stopped = service.mutate("/api/run/stop", body={})
    expected = service.context_path.read_bytes()
    project = service.mutate("/api/workspaces/default/open", body={})
    assert project["id"] == stopped["project_id"]
    assert service.context_path.read_bytes() == expected
    assert json.loads(expected)["run_id"] == started["run_id"]
    restarted = service.mutate("/api/run/start", body={})
    assert restarted["status"] == "running" and restarted["run_id"] != started["run_id"]
    service.mutate("/api/run/stop", body={})


def test_context_refuses_a_cross_tab_project_or_run_change_without_retry(service):
    service.capture()
    service.mutate("/api/pilot/load", body={})
    saved = service.context_path.read_bytes()
    session, _ = service.request("/api/session")
    service.request("/api/demo/load", "POST", {}, headers={"X-FAT-Token": session["token"]})
    with pytest.raises(ValueError, match="périmé"):
        service.mutate("/api/run/start", body={})
    assert service.context_path.read_bytes() == saved
    state, _ = service.request("/api/state")
    assert state["status"] == "idle" and state["run_id"] is None


def test_import_rechecks_context_on_server_when_project_changes_after_client_baseline(service, monkeypatch):
    service.capture()
    original, _ = service.request("/api/project")
    saved = service.context_path.read_bytes()
    request = service.request
    fresh = {**original, "name": "Concurrent operator revision"}
    raced = False

    def change_after_baseline(path, *args, **kwargs):
        nonlocal raced
        response = request(path, *args, **kwargs)
        if path == "/api/session" and not raced:
            raced = True
            request("/api/project", "PUT", fresh, headers={"X-FAT-Token": response[0]["token"]})
        return response

    monkeypatch.setattr(service, "request", change_after_baseline)
    with pytest.raises(ValueError, match="HTTP 409"):
        service.mutate("/api/project/import", body=original)
    assert raced
    assert service.context_path.read_bytes() == saved
    assert request("/api/project")[0] == fresh
    assert request("/api/state")[0]["run_id"] is None


def test_context_is_not_updated_after_a_rejected_prepared_step(service):
    service.capture()
    service.mutate("/api/pilot/load", body={})
    service.mutate("/api/run/start", body=dict(scenario_id="demo-guided-io"))
    saved = service.context_path.read_bytes()
    with pytest.raises(ValueError, match="HTTP 409"):
        service.mutate("/api/run/steps/guided-stop/execute", body={})
    assert service.context_path.read_bytes() == saved
    result = service.mutate("/api/run/steps/guided-initial/execute", body={})
    assert result["guided_steps"][0]["state"] == "queued"
    service.mutate("/api/run/stop", body={})


def test_cli_round_trip_and_export_do_not_overwrite_a_file(service, tmp_path, capsys):
    options = ["--url", service.url, "--context", str(service.context_path)]
    assert main([*options, "context"]) == 0
    assert main([*options, "pilot"]) == 0
    assert main([*options, "start"]) == 0
    state, _ = service.request("/api/state")
    assert main([*options, "stimulus", "--tag", "lt101_raw", "--value", "50", "--unit", "percent"]) == 0
    assert main([*options, "pulse", "--tag", "p101_request", "--value", "false"]) == 0
    assert main([*options, "stop"]) == 0
    output = tmp_path / "evidence.json"
    assert main([*options, "export", "--run", state["run_id"], "--kind", "json", "--output", str(output)]) == 0
    original = output.read_bytes()
    assert json.loads(original)["result"]["verdict"] == "not_evaluated"
    assert main([*options, "export", "--run", state["run_id"], "--kind", "json", "--output", str(output)]) == 2
    assert output.read_bytes() == original
    assert "écrasé" in capsys.readouterr().err


def test_nonfinite_cli_values_are_rejected():
    for value in ("NaN", "Infinity", "-Infinity", '{"x":NaN}'):
        with pytest.raises(argparse.ArgumentTypeError):
            json_value(value)


def test_source_helper_writes_utf8_json_even_when_windows_starts_with_cp1252(service):
    service.capture()
    project, _ = service.request("/api/project")
    project["name"] = "Échange → cuve 水"
    service.mutate("/api/project/import", body=project)
    root = Path(__file__).resolve().parents[1]
    run = subprocess.run([sys.executable, str(root / "scripts/fat-api.py"), "--url", service.url,
                          "--context", str(service.context_path), "project"], cwd=root,
                         env={**os.environ, "PYTHONIOENCODING": "cp1252"}, capture_output=True, check=True)
    assert json.loads(run.stdout.decode("utf-8"))["name"] == project["name"]
