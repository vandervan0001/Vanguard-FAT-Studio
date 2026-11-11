"""Passive CLI commands exercise a real, isolated loopback service."""

import json
import socket
import subprocess
import sys
import time

import pytest

from fat_studio.assistant import LocalClient, main


@pytest.fixture
def pid_service(tmp_path):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen([sys.executable, "-B", "-m", "fat_studio", "serve", "--host", "127.0.0.1",
        "--port", str(port), "--data-dir", str(tmp_path / "data")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    client = LocalClient(f"http://127.0.0.1:{port}", tmp_path / "context.json")
    try:
        deadline = time.monotonic() + 15
        while True:
            try:
                client.request("/api/health")
                break
            except ValueError:
                if process.poll() is not None or time.monotonic() > deadline:
                    pytest.fail("Le service temporaire P&ID n'a pas démarré.")
                time.sleep(.05)
        client.capture()
        yield client
    finally:
        process.terminate()
        process.wait(timeout=10)


def arguments(client):
    return ["--url", client.url, "--context", str(client.context_path)]


def test_pid_cli_inspect_prepare_export_never_advances_context(pid_service, tmp_path, capsys):
    client = pid_service
    original_context = client.context_path.read_bytes()
    original_project, _ = client.request("/api/project")
    source = tmp_path / "source.svg"
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="300">'
                      '<text x="100" y="150">P-101</text><text x="400" y="150">TK-101</text></svg>')
    inspected, prepared, exported = (tmp_path / name for name in ("drawing.json", "project.json", "drawing.dxf"))
    assert main(arguments(client) + ["pid-inspect", str(source), "--no-ocr", "--output", str(inspected)]) == 0
    document = json.loads(inspected.read_text(encoding="utf-8"))
    assert len(document["equipment"]) == 2
    first = document["equipment"][0]["id"]
    assert main(arguments(client) + ["pid-prepare", str(inspected), "--select", first,
                                  "--name", "Brouillon CLI", "--output", str(prepared)]) == 0
    package = json.loads(prepared.read_text(encoding="utf-8"))
    assert package["format"] == "fat-studio/project"
    assert package["project"]["id"] != original_project["id"]
    assert package["project"]["tags"] == []
    assert main(arguments(client) + ["pid-export", "--format", "dxf", "--output", str(exported)]) == 0
    assert b"SECTION" in exported.read_bytes()
    assert client.context_path.read_bytes() == original_context
    assert client.request("/api/project")[0] == original_project
    assert main(arguments(client) + ["pid-export", "--format", "dxf", "--output", str(exported)]) == 2
    assert "écrasé" in capsys.readouterr().err


def test_pid_cli_stale_context_keeps_output_and_draft_unmodified(pid_service, tmp_path):
    client = pid_service
    stale = client.context_path.read_bytes()
    client.mutate("/api/demo/load", body={})
    client.context_path.write_bytes(stale)
    source, output = tmp_path / "source.json", tmp_path / "draft.json"
    source.write_text('{"nodes":[],"edges":[]}')
    assert main(arguments(client) + ["pid-inspect", str(source), "--output", str(output)]) == 2
    assert not output.exists()
    assert client.context_path.read_bytes() == stale
