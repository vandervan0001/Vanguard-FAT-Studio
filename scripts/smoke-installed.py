#!/usr/bin/env python3
"""Exercise an installed distribution from outside its source tree, using stdlib HTTP.

Runs only on loopback, creates temporary test data, and never authorizes a PLC.
Used by the Windows offline installation CI gate and the local release check.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def open_worker_handle(pid):
    """Keep the real Python process identity across its Windows venv redirector's exit."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE, no termination rights.
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


def wait_worker_handle(handle):
    if handle is None:
        return
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    try:
        status = kernel.WaitForSingleObject(handle, 10_000)
        if status == 258:
            raise TimeoutError("Installed Python worker did not terminate within 10 seconds")
        if status != 0:
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)


def shutdown(process, worker_handle):
    try:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    finally:
        # Popen.wait() can finish before the redirector's job has killed its worker.
        wait_worker_handle(worker_handle)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    # Do not resolve a venv Python symlink into its base interpreter.
    python = str(args.python.absolute())
    if not Path(python).is_file():
        raise SystemExit("Installed Python not found: " + python)
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "checks": []}
    with tempfile.TemporaryDirectory(prefix="fat-installed-") as temporary:
        directory = Path(temporary)
        data = directory / "FAT data épreuve"
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        context = {}

        def request(path, body=None):
            payload = json.dumps(body).encode() if body is not None else None
            headers = {**context, "Content-Type": "application/json"}
            with urlopen(Request(base + path, data=payload, headers=headers), timeout=5) as response:
                content = response.read()
                return content, response.headers

        def command(path, body=None):
            response = json.loads(request(path, {} if body is None else body)[0])
            # A successful mutation owns the new baseline, including reset's
            # explicitly empty run. Reads never recapture a different context.
            for field, header in (("project_id", "X-FAT-Project-ID"),
                                  ("project_revision", "X-FAT-Project-Revision"),
                                  ("run_id", "X-FAT-Run-ID")):
                if field in response:
                    context[header] = str(response[field] or "")
            return response

        def boot(log):
            pid_file = directory / ("worker-" + uuid4().hex + ".pid")
            bootstrap = (
                "import os,sys;from pathlib import Path;"
                "Path(sys.argv[1]).write_text(str(os.getpid()),encoding='ascii');"
                "from fat_studio.cli import main;raise SystemExit(main(sys.argv[2:]))"
            )
            process = subprocess.Popen([python, "-B", "-X", "utf8", "-c", bootstrap, str(pid_file),
                                        "serve", "--host", "127.0.0.1",
                                        "--port", str(port), "--data-dir", str(data), "--no-browser"],
                                       cwd=directory, env=env, stdout=log, stderr=subprocess.STDOUT)
            worker_pid, worker_handle = None, None
            try:
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError(f"Installed service exited with {process.returncode}")
                    if worker_pid is None:
                        if not pid_file.exists():
                            time.sleep(0.05)
                            continue
                        pid_text = pid_file.read_text(encoding="ascii")
                        if not pid_text:
                            time.sleep(0.05)
                            continue
                        worker_pid = int(pid_text)
                        worker_handle = open_worker_handle(worker_pid)
                    try:
                        health = json.loads(request("/api/health")[0])
                        result["health"] = health
                        return process, worker_handle
                    except (URLError, ConnectionError, TimeoutError):
                        time.sleep(0.1)
                raise TimeoutError("Installed service did not become healthy within 25 seconds")
            except BaseException:
                shutdown(process, worker_handle)
                raise

        with (directory / "service.log").open("w", encoding="utf-8") as log:
            process, worker_handle = boot(log)
            try:
                html = request("/")[0].decode()
                title = re.search(r"<title>([^<]+)</title>", html)
                assert title and title[1].startswith("Vanguard FAT Studio"), "Installed product title is missing"
                assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html)
                assert len(assets) >= 2, "Production HTML does not reference JS/CSS"
                for asset in assets:
                    assert request(asset)[0], "Empty bundled asset"
                for name in ("logo_vanguard.png", "logo_vanguard_wordmark_horizontal.png",
                             "logo_vanguard_wordmark_horizontal_white.png", "favicon.png",
                             "Geist-Regular.ttf", "Geist-Bold.ttf", "GeistMono-Regular.ttf", "OFL.txt"):
                    assert request("/brand/" + name)[0], "Missing local brand asset: " + name
                result["checks"].append("production HTML and local JS/CSS served outside source tree")
                context["X-FAT-Token"] = json.loads(request("/api/session")[0])["token"]
                raw, headers = request("/api/project")
                project = json.loads(raw)
                assert project["id"] == "public-io-lab"
                assert len(project["equipment"]) == 36 and len(project["tags"]) == 75
                assert project["plc"]["mode"] == "demo" and project["plc"]["demo_controller"] == "manual_lab_v1"
                context.update({"X-FAT-Project-ID": project["id"],
                                "X-FAT-Project-Revision": headers["X-FAT-Project-Revision"], "X-FAT-Run-ID": ""})
                started = command("/api/run/start")
                run_id = started["run_id"]
                context["X-FAT-Run-ID"] = run_id
                time.sleep(0.35)
                paused = command("/api/run/pause")
                assert paused["status"] == "paused" and paused["sim_time_s"] > 0
                command("/api/markers", {"message": "Installed distribution smoke test"})
                command("/api/result", {"verdict": "not_evaluated", "comment": "Installation check only, no FAT approval"})
                evidence = json.loads(request("/api/export/json")[0])
                assert evidence["sample_count"] >= 2 and evidence["sample_count"] == len(evidence["samples"])
                assert evidence["result"]["verdict"] == "not_evaluated"
                report = request("/api/export/report")[0].decode()
                assert "Installed distribution smoke test" in report and "Vanguard FAT Studio" in report
                assert "data:image/png;base64," in report and "data:font/ttf;base64," in report
                assert b"timestamp" in request("/api/export/csv")[0]
                assert command("/api/run/stop")["status"] == "stopped"
                assert command("/api/run/reset")["run_id"] is None
                archived = json.loads(request("/api/runs/" + run_id + "/json")[0])
                assert archived["id"] == run_id and archived["sample_count"] == evidence["sample_count"]
                result["checks"].extend(["demo start, pause, marker and explicit unevaluated verdict",
                                         "consistent CSV, HTML and JSON exports", "stop/reset preserve archived evidence"])
                result["sample_count"] = evidence["sample_count"]
            finally:
                shutdown(process, worker_handle)
            context.clear()
            process, worker_handle = boot(log)
            try:
                context["X-FAT-Token"] = json.loads(request("/api/session")[0])["token"]
                history = json.loads(request("/api/runs")[0])
                assert any(item["id"] == run_id for item in history)
                assert json.loads(request("/api/state")[0])["status"] == "idle"
                result["checks"].append("fresh process reopens saved evidence and remains idle")
            finally:
                shutdown(process, worker_handle)
    result["status"] = "passed"
    result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["scope"] = "Installed application and loopback HTTP; no Siemens or external PLC"
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
