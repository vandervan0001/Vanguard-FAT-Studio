#!/usr/bin/env python3
"""Generate editable examples and real demonstration evidence from the shipped engine."""

import asyncio
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fat_studio.demo import demo_project  # noqa: E402
from fat_studio.models import Project  # noqa: E402
from fat_studio.reporting import csv_stream, html_report  # noqa: E402
from fat_studio.runtime import Runtime  # noqa: E402
from fat_studio.security import MachinePolicy  # noqa: E402
from fat_studio.storage import Store  # noqa: E402


async def main():
    output = ROOT / "examples"
    output.mkdir(exist_ok=True)
    project = demo_project()
    (output / "tank-demo.json").write_text(project.model_dump_json(indent=2) + "\n", encoding="utf-8")
    (output / "project.schema.json").write_text(json.dumps(Project.model_json_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    results = []
    with tempfile.TemporaryDirectory(prefix="fat-examples-") as temporary:
        folder = Path(temporary)
        store = Store(folder)
        runtime = Runtime(store, project, MachinePolicy(folder / "policy.json"))
        try:
            for scenario in project.scenarios:
                await runtime.start(scenario.id, background=False)
                while runtime.status == "running":
                    await runtime.tick()
                if runtime.status == "error":
                    raise RuntimeError(runtime.error)
                results.append({"scenario": scenario.id, "duration_s": runtime.engine.time_s,
                                "assertions": runtime.assertions, "final_values": runtime.engine.values.copy(),
                                "user_verdict": "not_evaluated", "mode": "demo"})
                if scenario.id == "reference":
                    (output / "reference-report.html").write_text(html_report(store, runtime.run_id), encoding="utf-8")
                    with (output / "reference.csv").open("w", encoding="utf-8", newline="") as stream:
                        stream.writelines(csv_stream(store, runtime.run_id))
                await runtime.reset()
        finally:
            store.close()
    if not all(item["passed"] for result in results for item in result["assertions"]):
        raise RuntimeError("A demonstration assertion failed.")
    (ROOT / "evidence" / "demo-scenarios.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(results)} real demonstration runs; {sum(len(r['assertions']) for r in results)} assertions passed.")


if __name__ == "__main__":
    asyncio.run(main())
