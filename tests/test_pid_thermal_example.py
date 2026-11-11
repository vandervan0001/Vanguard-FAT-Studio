"""Run the public example through the real FAT runtime and evidence store."""

import json
from pathlib import Path

import pytest

from fat_studio.adapters.demo import DemoAdapter
from fat_studio.exchange import read_project
from fat_studio.runtime import Runtime
from fat_studio.security import MachinePolicy
from fat_studio.storage import Store


async def test_public_thermal_example_executes_without_assigning_a_human_fat_verdict(tmp_path):
    payload = json.loads((Path(__file__).resolve().parents[1] / "examples/pid-thermal-loop.project.json").read_text(encoding="utf-8"))
    project = read_project(payload)
    store = Store(tmp_path)
    runtime = Runtime(store, project, MachinePolicy(tmp_path / "policy.json"))
    try:
        await runtime.start("thermal-routing", background=False)
        for _ in range(1001):
            if runtime.status != "running":
                break
            await runtime.tick()
        assert runtime.status == "paused", runtime.error
        assert runtime.scenario_state == "completed"
        assert len(runtime.assertions) == 5
        assert all(item["passed"] for item in runtime.assertions), runtime.assertions
        assert isinstance(runtime.adapter, DemoAdapter)
        assert runtime.connection["connected"] is False
        assert runtime.engine.equipment_state["HX"]["secondary_flow_l_s"] == runtime.engine.equipment_state["V3"]["flow_a_l_s"]
        total = sum(state.get("volume_l", 0) + state.get("overflow_l", 0) for state in runtime.engine.equipment_state.values())
        assert total == pytest.approx(8000.0)
        run_id = runtime.run_id
        record = store.run(run_id)
        assert record["status"] == "completed"
        assert record["result"]["verdict"] == "not_evaluated"
        assert record["sample_count"] == 1000
        await runtime.reset()
        assert store.run(run_id)["status"] == "completed"
        assert runtime.engine.time_s == 0
        assert runtime.engine.faults == {}
    finally:
        await runtime.close()
        store.close()
