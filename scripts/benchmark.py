#!/usr/bin/env python3
"""Measure actual plant and evidence costs at 50 equipment / 200 mapped tags.

This is a reproducible measurement, not a real-time certification or a CI gate.
No Siemens, network transport, HTTP rendering or browser work is measured.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sqlite3
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fat_studio.engine import ProcessEngine  # noqa: E402
from fat_studio.models import Project, validate_project  # noqa: E402
from fat_studio.storage import Store  # noqa: E402


def benchmark_project() -> Project:
    """Ten independent tanks, each with four dynamic modulating valves.

    Each tank produces level/volume/high/low. Each valve reads a command and
    produces position/open/closed. All 200 tags are connected to actual ports:
    40 PLC commands and 160 simulated inputs, with no dummy/manual padding.
    """
    equipment, tags = [], []

    def tag(id, data_type, initial, direction="input", unit="", high=None):
        tags.append({"id": id, "name": id, "direction": direction, "data_type": data_type,
                     "initial_value": initial, "unit": unit, "min": None if data_type == "BOOL" else 0,
                     "max": high, "writable": direction == "input"})

    for n in range(10):
        tank_id = f"tank{n}"
        capacity = 1000.0 + n * 100
        bindings = {}
        for port, dtype, initial, unit, high in [
            ("level", "REAL", 40.0, "%", 100), ("volume", "REAL", capacity * 0.4, "L", capacity),
            ("high", "BOOL", False, "", None), ("low", "BOOL", False, "", None),
        ]:
            name = f"{tank_id}_{port}"
            tag(name, dtype, initial, unit=unit, high=high)
            bindings[port] = name
        equipment.append({"id": tank_id, "name": tank_id, "type": "tank", "position": {"x": n * 100, "y": 0},
                          "params": {"capacity_l": capacity, "initial_level_pct": 40.0}, "bindings": bindings})
        for j in range(4):
            valve_id = f"valve{n}_{j}"
            bindings = {}
            for port, dtype, initial, direction, unit, high in [
                ("command", "REAL", 0.0, "output", "%", 100),
                ("position", "REAL", 0.0, "input", "%", 100),
                ("open", "BOOL", False, "input", "", None),
                ("closed", "BOOL", True, "input", "", None),
            ]:
                name = f"{valve_id}_{port}"
                tag(name, dtype, initial, direction=direction, unit=unit, high=high)
                bindings[port] = name
            equipment.append({"id": valve_id, "name": valve_id, "type": "valve_control", "position": {"x": n * 100, "y": 100 + j * 80},
                              "params": {"tank_id": tank_id, "role": "inlet" if j < 2 else "outlet", "flow_group": f"branch{j}",
                                         "max_flow_l_s": 10.0 + j, "response_s": 0.2 + j * 0.1}, "bindings": bindings})
    return Project.model_validate({"id": "benchmark50x200", "name": "Benchmark 50 équipements / 200 tags actifs",
                                   "equipment": equipment, "tags": tags, "simulation": {"step_ms": 100, "speed": 1}})


def commands(cycle: int) -> dict:
    phase = (cycle // 100) % 4
    positions = ((70.0, 40.0, 30.0, 20.0), (0.0, 100.0, 80.0, 20.0),
                 (100.0, 50.0, 40.0, 40.0), (30.0, 0.0, 10.0, 70.0))[phase]
    return {f"valve{n}_{j}_command": positions[j] for n in range(10) for j in range(4)}


def summary(samples_ns: list[int], elapsed_s: float) -> dict:
    samples = sorted(value / 1_000_000 for value in samples_ns)

    def percentile(q):
        position = (len(samples) - 1) * q
        lower = int(position)
        upper = min(lower + 1, len(samples) - 1)
        return samples[lower] + (samples[upper] - samples[lower]) * (position - lower)

    return {"cycles": len(samples), "unit": "ms", "p50": round(statistics.median(samples), 6),
            "p95": round(percentile(0.95), 6), "max": round(max(samples), 6),
            "min": round(min(samples), 6), "mean": round(statistics.mean(samples), 6),
            "elapsed_wall_s": round(elapsed_s, 6)}


def value_hash(values: dict) -> str:
    payload = json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


def measure(project: Project, cycles: int, warmup: int, work_dir: Path | None) -> dict:
    engine = ProcessEngine(project)
    for index in range(warmup):
        engine.step(commands(index), 0.1)
    engine.reset()
    timings = []
    started = time.perf_counter()
    for index in range(cycles):
        image = commands(index)
        begin = time.perf_counter_ns()
        engine.step(image, 0.1)
        timings.append(time.perf_counter_ns() - begin)
    results = {"plant_only": summary(timings, time.perf_counter() - started)}
    expected_hash = value_hash(engine.values)
    last_values, last_qualities = dict(engine.values), dict(engine.qualities)

    for label in ("sqlite_only", "plant_and_sqlite"):
        with tempfile.TemporaryDirectory(prefix="fat-studio-benchmark-", dir=work_dir) as folder:
            store = Store(Path(folder))
            try:
                store.start_run("warmup", project, None, {"mode": "benchmark"})
                engine.reset()
                for index in range(warmup):
                    engine.step(commands(index), 0.1)
                    store.sample("warmup", engine.time_s, engine.values, engine.qualities)
                store.set_status("warmup", "completed", ended=True)
                store.start_run("measurement", project, None, {"mode": "benchmark"})
                engine.reset()
                timings = []
                started = time.perf_counter()
                for index in range(cycles):
                    image = commands(index)
                    begin = time.perf_counter_ns()
                    if label == "plant_and_sqlite":
                        engine.step(image, 0.1)
                        store.sample("measurement", engine.time_s, engine.values, engine.qualities)
                    else:
                        store.sample("measurement", (index + 1) * 0.1, last_values, last_qualities)
                    timings.append(time.perf_counter_ns() - begin)
                result = summary(timings, time.perf_counter() - started)
                result["sample_count"] = store.run("measurement")["sample_count"]
                result["sqlite_journal_mode"] = store.db.execute("PRAGMA journal_mode").fetchone()[0]
                result["sqlite_synchronous"] = store.db.execute("PRAGMA synchronous").fetchone()[0]
                result["db_and_journal_bytes"] = sum(path.stat().st_size for path in Path(folder).glob("history.sqlite3*"))
                if result["sample_count"] != cycles:
                    raise RuntimeError("Le nombre d'échantillons enregistrés ne correspond pas aux cycles mesurés.")
                if label == "plant_and_sqlite" and value_hash(engine.values) != expected_hash:
                    raise RuntimeError("La trajectoire du moteur diffère entre les deux mesures.")
                store.set_status("measurement", "completed", ended=True)
                results[label] = result
            finally:
                store.close()
    return {"phases": results, "deterministic_final_values_sha256": expected_hash}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=1000)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--output", type=Path, default=ROOT / "evidence" / "benchmark.json")
    parser.add_argument("--work-dir", type=Path, help="Support de stockage à mesurer ; dossier temporaire système par défaut")
    args = parser.parse_args()
    if not 100 <= args.cycles <= 100000 or not 0 <= args.warmup <= 10000:
        parser.error("cycles entre 100 et 100000 ; warmup entre 0 et 10000")
    if args.work_dir:
        args.work_dir.mkdir(parents=True, exist_ok=True)
    project = benchmark_project()
    validation = validate_project(project)
    if not validation["valid"]:
        raise RuntimeError(validation)
    versions = {}
    for package in ("pydantic", "asyncua"):
        versions[package] = importlib.metadata.version(package)
    result = {
        "schema_version": 1, "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "system": {"platform": platform.platform(), "python": platform.python_version(),
                   "machine": platform.machine(), "processor": platform.processor(), "logical_cpus": os.cpu_count(),
                   "affinity_cpu_count": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
                   "sqlite": sqlite3.sqlite_version, "dependencies": versions},
        "workload": {"equipment": len(project.equipment), "tags": len(project.tags), "plc_commands": 40,
                     "modeled_inputs": 160, "unmapped_tags": 0, "description": "10 cuves, 40 vannes modulantes ; tous les ports associés",
                     "step_ms": 100, "cycles": args.cycles, "warmup_cycles": args.warmup,
                     "simulated_time_s": args.cycles * 0.1, "sqlite_commit": "un commit réel par échantillon",
                     "storage_location": str(args.work_dir.resolve()) if args.work_dir else "répertoire temporaire système",
                     "project_sha256": value_hash(project.model_dump(mode="json"))},
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                          ("fat_studio/engine.py", "fat_studio/models.py", "fat_studio/storage.py", "scripts/benchmark.py")},
        "limitations": ["Mesure sur cet environnement uniquement ; refaire sur le poste Windows cible et son disque.",
                        "OPC UA, PLCSIM, navigateur, rendu HTTP, ordonnancement et latence réseau exclus.",
                        "Une latence de modèle faible ne constitue pas une garantie temps réel ou de déterminisme PLC.",
                        "La phase SQLite seule réécrit une image de 200 valeurs afin d'isoler sérialisation, insertion et commit.",
                        "Aucun seuil de succès de performance n'est imposé ; les objectifs du site restent à qualifier."],
    }
    result.update(measure(project, args.cycles, args.warmup, args.work_dir))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result["phases"], indent=2, ensure_ascii=False))
    print(f"Mesure enregistrée dans {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
