"""Record local package fidelity and demo results without Siemens or user data."""
import asyncio
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from zipfile import ZipFile

if len(sys.argv) != 2:
    raise SystemExit('Usage: python reproduce-package-demo.py PATH_TO_SOURCE_ROOT')
ROOT = Path(sys.argv[1]).resolve(strict=True)
sys.path.insert(0, str(ROOT))
from fat_studio.demo import demo_project
from fat_studio.runtime import Runtime
from fat_studio.security import MachinePolicy
from fat_studio.storage import Store

OUTPUT = ROOT / 'evidence/reprises/2026-11-02-windows-local'


async def main():
    wheel = ROOT / 'dist/local_fat_studio-0.2.1-py3-none-any.whl'
    expected = {
        p.relative_to(ROOT).as_posix(): p.read_bytes()
        for package in ('fat_studio', 'integrations')
        for p in (ROOT / package).rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'
    }
    with ZipFile(wheel) as archive:
        actual = {n: archive.read(n) for n in archive.namelist()
                  if n.startswith(('fat_studio/', 'integrations/'))}
    assert actual.keys() == expected.keys(), (actual.keys() - expected.keys(), expected.keys() - actual.keys())
    assert all(actual[name] == data for name, data in expected.items())
    result = {
        'platform': platform.platform(), 'python': platform.python_version(),
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'scope': 'Windows local application, demo and packaging only; no Siemens',
        'wheel': {'name': wheel.name, 'sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
                  'application_files': len(actual), 'all_names_and_contents_match': True},
        'scenarios': [],
    }
    with tempfile.TemporaryDirectory(prefix='fat-demo-evidence-') as temporary:
        for scenario in ('reference', 'motor-trip', 'sensor-freeze'):
            data = Path(temporary) / scenario
            store = Store(data)
            runtime = Runtime(store, demo_project(), MachinePolicy(data / 'machine-policy.json'))
            try:
                await runtime.start(scenario, background=False)
                for _ in range(400):
                    if runtime.status != 'running':
                        break
                    await runtime.tick()
                assert runtime.scenario_state == 'completed'
                assert runtime.assertions and all(a['passed'] for a in runtime.assertions)
                record = store.run(runtime.run_id)
                assert record['result']['verdict'] == 'not_evaluated'
                result['scenarios'].append({
                    'id': scenario, 'sim_time_s': runtime.engine.time_s,
                    'sample_count': record['sample_count'], 'assertions': runtime.assertions,
                    'human_verdict': record['result']['verdict'],
                })
            finally:
                await runtime.stop()
                store.close()
    target = OUTPUT / 'package-and-demo.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'wheel_files': len(actual), 'scenarios': len(result['scenarios']),
                      'assertions': sum(len(s['assertions']) for s in result['scenarios']), 'status': 'passed'}))


asyncio.run(main())
