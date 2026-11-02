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
            return json.loads(request(path, {} if body is None else body)[0])

        def boot(log):
            process = subprocess.Popen([python, "-m", "fat_studio", "serve", "--host", "127.0.0.1",
                                        "--port", str(port), "--data-dir", str(data), "--no-browser"],
                                       cwd=directory, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError(f"Installed service exited with {process.returncode}")
                    try:
                        health = json.loads(request("/api/health")[0])
                        result["health"] = health
                        return process
                    except (URLError, ConnectionError, TimeoutError):
                        time.sleep(0.1)
                raise TimeoutError("Installed service did not become healthy within 25 seconds")
            except BaseException:
                shutdown(process)
                raise

        def shutdown(process):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

        with (directory / "service.log").open("w", encoding="utf-8") as log:
            process = boot(log)
            try:
                html = request("/")[0].decode()
                assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html)
                assert len(assets) >= 2, "Production HTML does not reference JS/CSS"
                for asset in assets:
                    assert request(asset)[0], "Empty bundled asset"
                result["checks"].append("production HTML and local JS/CSS served outside source tree")
                context["X-FAT-Token"] = json.loads(request("/api/session")[0])["token"]
                raw, headers = request("/api/project")
                project = json.loads(raw)
                assert len(project["equipment"]) == 8 and len(project["tags"]) == 13
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
                assert "Installed distribution smoke test" in request("/api/export/report")[0].decode()
                assert b"timestamp" in request("/api/export/csv")[0]
                assert command("/api/run/stop")["status"] == "stopped"
                assert command("/api/run/reset")["run_id"] is None
                archived = json.loads(request("/api/runs/" + run_id + "/json")[0])
                assert archived["id"] == run_id and archived["sample_count"] == evidence["sample_count"]
                result["checks"].extend(["demo start, pause, marker and explicit unevaluated verdict",
                                         "consistent CSV, HTML and JSON exports", "stop/reset preserve archived evidence"])
                result["sample_count"] = evidence["sample_count"]
            finally:
                shutdown(process)
            context.clear()
            process = boot(log)
            try:
                context["X-FAT-Token"] = json.loads(request("/api/session")[0])["token"]
                history = json.loads(request("/api/runs")[0])
                assert any(item["id"] == run_id for item in history)
                assert json.loads(request("/api/state")[0])["status"] == "idle"
                result["checks"].append("fresh process reopens saved evidence and remains idle")
            finally:
                shutdown(process)
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
