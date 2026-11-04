"""Exercise generic loopback OPC UA only; no Siemens software or user policy."""
from __future__ import annotations

import asyncio
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import logging
import os
from pathlib import Path
import platform
import runpy
import socket
import struct
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path('C:/FAT_Studio')
sys.path.insert(0, str(ROOT))
from asyncua import Server, ua
from asyncua.crypto.cert_gen import setup_self_signed_certificate
from cryptography.x509.oid import ExtendedKeyUsageOID
from fat_studio.adapters.opcua import VARIANT_TYPES
from fat_studio.cli import default_data_dir
from fat_studio.models import PLCConfig, Project
from fat_studio.reporting import csv_stream, html_report, json_stream
from fat_studio.runtime import Runtime, RunConflict
from fat_studio.security import MachinePolicy
from fat_studio.storage import Store

WORK = ROOT / '.local/opcua-extended' / ('run-' + uuid4().hex)
WORK.mkdir()
EVIDENCE = ROOT / 'evidence/reprises/2026-11-02-windows-extended'
EVIDENCE.mkdir(parents=True, exist_ok=True)
SMOKE = runpy.run_path(str(ROOT / 'scripts/smoke-installed.py'))
BENCHMARK = runpy.run_path(str(ROOT / 'scripts/benchmark.py'))
RESULT = {
    'started_at_utc': datetime.now(timezone.utc).isoformat(),
    'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'platform': platform.platform(), 'python': platform.python_version(),
    'asyncua': importlib.metadata.version('asyncua'),
    'scope': 'Generic OPC UA loopback, no Siemens, no production target, no browser',
    'working_directory': str(WORK), 'phases': [],
}


def progress(message):
    print(message, flush=True)
    (WORK / 'progress.json').write_text(json.dumps({'time': datetime.now(timezone.utc).isoformat(),
                                                  'message': message}, indent=2), encoding='utf-8')


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def float32(value):
    return struct.unpack('!f', struct.pack('!f', value))[0]


def policy_for(project, directory):
    plc = project.plc
    policy = MachinePolicy(directory / 'machine-policy.json')
    policy.add({key: getattr(plc, key) for key in (
        'endpoint', 'expected_application_uri', 'approved_virtual_target',
        'server_certificate_sha256', 'client_certificate', 'client_private_key',
        'username_env', 'password_env',
    )} | {'allow_insecure': plc.security_policy == 'None', 'isolated_virtual_adapter_confirmed': True})
    return policy


async def wait_sample(runtime, count, timeout=200):
    deadline = time.monotonic() + timeout
    while runtime.store.run(runtime.run_id)['sample_count'] < count:
        assert runtime.status == 'running', runtime.error
        assert time.monotonic() < deadline, 'Sample deadline exceeded'
        await asyncio.sleep(.05)


async def wait_terminal(runtime, timeout=90):
    deadline = time.monotonic() + timeout
    while runtime.status == 'running':
        assert time.monotonic() < deadline, 'Runtime termination deadline exceeded'
        await asyncio.sleep(.05)


async def exact_image(runtime, nodes):
    async with runtime.lock:
        for tag in runtime.project.tags:
            if tag.direction != 'input':
                continue
            actual = await nodes[tag.id].read_value()
            expected = runtime.engine.values[tag.id]
            assert type(actual) is type(expected) and actual == expected, (tag.id, actual, expected)
            if tag.data_type == 'REAL':
                assert expected == float32(expected), (tag.id, expected)
        return dict(runtime.engine.values)


def export_check(store, run_id, tag_count, label):
    run = store.run(run_id)
    text = ''.join(json_stream(store, run_id, run=run))
    data = json.loads(text)
    rows = list(csv.reader(io.StringIO(''.join(csv_stream(store, run_id, run=run)).lstrip('\ufeff'))))
    report = html_report(store, run_id, run=run)
    assert data['sample_count'] == len(data['samples']) == run['sample_count']
    assert len(rows) == 1 + run['sample_count'] * tag_count
    assert data['result']['verdict'] == 'not_evaluated'
    assert 'NON ÉVALUÉ' in report
    assert all(len(sample['values']) == tag_count for sample in data['samples'])
    times = [sample['sim_time_s'] for sample in data['samples']]
    assert times == sorted(times)
    for sample in data['samples']:
        for tag in data['project']['tags']:
            if tag['data_type'] == 'REAL':
                value = sample['values'][tag['id']]
                assert value == float32(value), (sample['id'], tag['id'], value)
    (WORK / (label + '.json')).write_text(text, encoding='utf-8')
    return {'sample_count': run['sample_count'], 'csv_rows': len(rows),
            'json_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'human_verdict': data['result']['verdict'], 'status': run['status']}


def reopen_check(directory, run_ids):
    store = Store(directory)
    try:
        assert store.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        records = [store.run(run_id) for run_id in run_ids]
        assert all(r['sample_count'] > 0 for r in records)
        return {'sqlite_integrity': 'ok', 'reopened_runs': len(records),
                'statuses': [r['status'] for r in records],
                'sample_counts': [r['sample_count'] for r in records]}
    finally:
        store.close()


async def fixture_phase():
    directory = WORK / 'fixture-cli'
    directory.mkdir()
    project_path, ready_path, pid_path = (directory / name for name in ('project.json', 'ready.json', 'worker.pid'))
    port = free_port()
    env = {**os.environ, 'PYTHONUTF8': '1', 'FAT_PROTOCOL_PID_FILE': str(pid_path)}
    bootstrap = ("import os,sys,runpy;from pathlib import Path;"
                 "Path(os.environ['FAT_PROTOCOL_PID_FILE']).write_text(str(os.getpid()),encoding='ascii');"
                 "sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')")
    log = (directory / 'fixture.log').open('w', encoding='utf-8')
    process = subprocess.Popen([sys.executable, '-X', 'utf8', '-c', bootstrap,
                                str(ROOT / 'scripts/opcua-fixture.py'), '--port', str(port),
                                '--project', str(project_path), '--ready-file', str(ready_path)],
                               cwd=directory, env=env, stdout=log, stderr=subprocess.STDOUT)
    worker_handle = None
    store = None
    runtime = None
    monitor = None
    stopped = False
    started = time.monotonic()
    run_ids, scenarios = [], []
    try:
        deadline = time.monotonic() + 30
        while not ready_path.exists():
            assert process.poll() is None, 'Fixture exited during startup'
            if worker_handle is None and pid_path.exists() and pid_path.read_text(encoding='ascii'):
                worker_handle = SMOKE['open_worker_handle'](int(pid_path.read_text(encoding='ascii')))
            assert time.monotonic() < deadline, 'Fixture did not become ready'
            await asyncio.sleep(.05)
        if worker_handle is None:
            worker_handle = SMOKE['open_worker_handle'](int(pid_path.read_text(encoding='ascii')))
        project = Project.model_validate_json(project_path.read_text(encoding='utf-8'))
        project.plc.timeout_s = 1.0
        policy = policy_for(project, directory)
        store = Store(directory / 'data')
        runtime = Runtime(store, project, policy)
        confirmation = f'{project.plc.approved_virtual_target} @ {project.plc.endpoint}'
        from asyncua import Client
        monitor = Client(project.plc.endpoint, timeout=1)
        await monitor.connect()
        nodes = {tag.id: monitor.get_node(tag.node_id) for tag in project.tags}
        for scenario in ('reference', 'motor-trip', 'sensor-freeze'):
            await runtime.start(scenario, confirmation=confirmation, background=True)
            run_ids.append(runtime.run_id)
            await wait_terminal(runtime)
            assert runtime.scenario_state == 'completed', runtime.error
            assert runtime.assertions and all(a['passed'] for a in runtime.assertions), runtime.assertions
            record = export_check(store, runtime.run_id, 13, 'fixture-' + scenario)
            record.update({'scenario': scenario, 'assertions': runtime.assertions,
                           'sim_time_s': runtime.engine.time_s})
            scenarios.append(record)
            progress('Fixture CLI scenario passed: ' + scenario)
            await runtime.reset()
        await runtime.start(confirmation=confirmation, background=True)
        run_ids.append(runtime.run_id)
        await wait_sample(runtime, 10)
        await runtime.force('level', 40.1)
        await wait_sample(runtime, 15)
        image = await exact_image(runtime, nodes)
        assert image['level'] == float32(40.1)
        await runtime.release('level')
        await runtime.fault('P101', 'motor_trip')
        await wait_sample(runtime, 20)
        image = await exact_image(runtime, nodes)
        assert image['pump_fault'] is True and image['pump_running'] is False
        await runtime.clear_fault('P101')
        await wait_sample(runtime, 30)
        await runtime.pause()
        paused_time, paused_writes = runtime.engine.time_s, runtime.write_count
        await asyncio.sleep(.5)
        assert runtime.engine.time_s == paused_time and runtime.write_count == paused_writes
        await runtime.resume(background=True)
        await wait_sample(runtime, 40)
        async with runtime.lock:
            captured = store.run(runtime.run_id)
            stream = json_stream(store, runtime.run_id, run=captured)
        await runtime.marker('Marker after export snapshot')
        await wait_sample(runtime, 45)
        captured_export = json.loads(''.join(stream))
        assert len(captured_export['samples']) == captured_export['sample_count'] == captured['sample_count']
        assert not any(e['message'] == 'Marker after export snapshot' for e in captured_export['events'])
        assert store.run(runtime.run_id)['sample_count'] > captured['sample_count']
        await monitor.disconnect()
        monitor = None
        before_failure_writes = runtime.write_count
        SMOKE['shutdown'](process, worker_handle)
        worker_handle = None
        stopped = True
        await wait_terminal(runtime, timeout=10)
        assert runtime.status == 'error'
        writes_after_failure = runtime.write_count
        assert writes_after_failure >= before_failure_writes
        await asyncio.sleep(1)
        assert runtime.write_count == writes_after_failure
        assert all(t['quality'] == 'bad' for t in runtime.snapshot()['tags'].values())
        assert not runtime.connection['connected']
        try:
            await runtime.resume(background=False)
        except RunConflict:
            pass
        else:
            raise AssertionError('Failed runtime resumed without explicit new run')
        failure_record = export_check(store, runtime.run_id, 13, 'fixture-link-loss')
        failure_error = runtime.error
        assert store.run(runtime.run_id)['status'] == 'error'
        await runtime.reset()
        assert store.run(run_ids[-1])['status'] == 'error'
        await runtime.close()
        runtime = None
        store.close()
        store = None
        reopen = reopen_check(directory / 'data', run_ids)
        return {'phase': 'actual_fixture_cli', 'status': 'passed',
                'tag_count': 13, 'equipment_count': 8, 'wall_time_s': round(time.monotonic() - started, 3),
                'scenarios': scenarios, 'manual_force_float32': float32(40.1),
                'manual_motor_fault_observed_on_server': True, 'pause_no_writes': True,
                'finite_running_export': {'samples': captured['sample_count'], 'later_sample_count_increased': True},
                'loss': {'error': failure_error, 'writes_after_error': writes_after_failure,
                         'no_automatic_resume': True, 'all_tag_qualities_bad': True,
                         'archived': failure_record}, 'persistence': reopen,
                'fixture_process_stopped': process.poll() is not None}
    finally:
        if monitor is not None:
            await monitor.disconnect()
        if runtime is not None:
            await runtime.close()
        if store is not None:
            store.close()
        if not stopped:
            SMOKE['shutdown'](process, worker_handle)
        log.close()


async def load_phase():
    directory = WORK / 'load-50x200'
    directory.mkdir()
    project = BENCHMARK['benchmark_project']()
    endpoint = f'opc.tcp://127.0.0.1:{free_port()}/fat-extended-load/'
    app_uri = 'urn:fat-studio:extended-load-fixture'
    namespace_uri = 'urn:fat-studio:extended-load-exchange'
    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name('Generic 200-tag load fixture, no Siemens')
    await server.set_application_uri(app_uri)
    server_key, server_cert = directory / 'server-key.pem', directory / 'server.der'
    client_key, client_cert = directory / 'client-key.pem', directory / 'client.der'
    await setup_self_signed_certificate(server_key, server_cert, app_uri, 'localhost',
                                       [ExtendedKeyUsageOID.SERVER_AUTH], {'commonName': 'Generic loopback load fixture'})
    await setup_self_signed_certificate(client_key, client_cert, 'urn:fat-studio:client', 'localhost',
                                       [ExtendedKeyUsageOID.CLIENT_AUTH], {'commonName': 'Generic load client'})
    await server.load_certificate(server_cert)
    await server.load_private_key(server_key)
    server.set_security_policy([ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt])
    ns = await server.register_namespace(namespace_uri)
    obj = await server.nodes.objects.add_object(ns, 'Exchange')
    nodes = {}
    for tag in project.tags:
        node_id = ua.NodeId(tag.id, ns)
        node = await obj.add_variable(node_id, tag.id, ua.Variant(tag.initial_value, VARIANT_TYPES[tag.data_type]))
        if tag.direction == 'input':
            await node.set_writable()
        tag.node_id = node_id.to_string()
        nodes[tag.id] = node
    project.plc = PLCConfig(mode='opcua', endpoint=endpoint, expected_application_uri=app_uri,
                            namespace_uri=namespace_uri, approved_virtual_target='Generic encrypted load fixture',
                            security_policy='Basic256Sha256',
                            server_certificate_sha256=hashlib.sha256(server_cert.read_bytes()).hexdigest(),
                            client_certificate=str(client_cert), client_private_key=str(client_key), timeout_s=2.0)
    policy = policy_for(project, directory)
    store = Store(directory / 'data')
    runtime = Runtime(store, project, policy)
    outputs = [tag for tag in project.tags if tag.direction == 'output']
    confirmation = f'{project.plc.approved_virtual_target} @ {project.plc.endpoint}'
    running = False
    closed = False
    controller = None
    timings = []
    started = time.monotonic()
    run_ids = []
    try:
        await server.start()
        running = True

        async def command_loop():
            index = 0
            while True:
                values = BENCHMARK['commands'](index)
                for tag in outputs:
                    await nodes[tag.id].write_value(ua.Variant(values[tag.id], VARIANT_TYPES[tag.data_type]))
                index += 1
                await asyncio.sleep(.1)

        controller = asyncio.create_task(command_loop())
        original_tick = runtime.tick

        async def measured_tick():
            begin = time.perf_counter_ns()
            await original_tick()
            timings.append((time.perf_counter_ns() - begin) / 1_000_000)

        runtime.tick = measured_tick
        await runtime.start(confirmation=confirmation, background=True)
        run_ids.append(runtime.run_id)
        await wait_sample(runtime, 100)
        assert not controller.done(), controller.exception() if controller.done() else None
        await exact_image(runtime, nodes)
        await runtime.force('valve0_0_position', 0.1)
        await wait_sample(runtime, 110)
        image = await exact_image(runtime, nodes)
        assert image['valve0_0_position'] == float32(.1)
        await runtime.release('valve0_0_position')
        await runtime.fault('valve0_0', 'valve_stuck', 45.6)
        await wait_sample(runtime, 120)
        image = await exact_image(runtime, nodes)
        assert image['valve0_0_position'] == float32(45.6)
        await runtime.clear_fault('valve0_0')
        await wait_sample(runtime, 300)
        progress('Encrypted load: 300 cycles, 200 tags, exact Float32/server image verified')
        await wait_sample(runtime, 600)
        assert not controller.done(), controller.exception() if controller.done() else None
        await exact_image(runtime, nodes)
        progress('Encrypted load: 600 cycles, 200 tags')
        await wait_sample(runtime, 1000)
        assert not controller.done(), controller.exception() if controller.done() else None
        await exact_image(runtime, nodes)
        healthy = store.run(runtime.run_id)
        assert healthy['sample_count'] >= 1000
        assert runtime.write_count == healthy['sample_count'] * 160
        observed_commands = {sample['values']['valve0_0_command'] for sample in store.samples(runtime.run_id)}
        assert len(observed_commands) == 4, observed_commands
        controller.cancel()
        await asyncio.gather(controller, return_exceptions=True)
        controller = None
        await server.stop()
        running = False
        await wait_terminal(runtime, timeout=15)
        assert runtime.status == 'error', runtime.snapshot()
        failed_writes, failed_error = runtime.write_count, runtime.error
        assert all(t['quality'] == 'bad' for t in runtime.snapshot()['tags'].values())
        failure_record = export_check(store, runtime.run_id, 200, 'encrypted-load-link-loss')
        await server.start()
        running = True
        before = {tag.id: await nodes[tag.id].read_value() for tag in project.tags if tag.direction == 'input'}
        await asyncio.sleep(2)
        after = {tag.id: await nodes[tag.id].read_value() for tag in project.tags if tag.direction == 'input'}
        assert before == after and runtime.write_count == failed_writes and runtime.status == 'error'
        assert runtime.adapter.client is None
        try:
            await runtime.resume(background=False)
        except RunConflict:
            pass
        else:
            raise AssertionError('Link-loss run resumed after server restart')
        await runtime.reset()
        await runtime.start(confirmation=confirmation, background=True)
        run_ids.append(runtime.run_id)
        await wait_sample(runtime, 20)
        await exact_image(runtime, nodes)
        await runtime.stop()
        second_record = export_check(store, runtime.run_id, 200, 'encrypted-load-explicit-restart')
        assert store.run(run_ids[0])['status'] == 'error'
        overruns = [event for event in store.run(run_ids[0])['events'] if event['kind'] == 'timing_overrun']
        await runtime.close()
        store.close()
        closed = True
        reopen = reopen_check(directory / 'data', run_ids)
        sorted_timings = sorted(timings[:healthy['sample_count']])
        return {'phase': 'encrypted_load_50x200', 'status': 'passed', 'equipment_count': 50,
                'tag_count': 200, 'read_outputs': 40, 'written_inputs': 160,
                'security_policy': 'Basic256Sha256/SignAndEncrypt',
                'healthy_cycles': healthy['sample_count'],
                'successful_tag_writes_before_loss': healthy['sample_count'] * 160,
                'nominal_step_ms': 100, 'wall_time_s': round(time.monotonic() - started, 3),
                'measured_tick_ms': {'p50': sorted_timings[len(sorted_timings)//2],
                                     'p95': sorted_timings[int((len(sorted_timings)-1)*.95)],
                                     'max': max(sorted_timings)},
                'timing_overrun_events': len(overruns), 'server_and_evidence_float32_equal': True,
                'distinct_command_values_observed': sorted(observed_commands),
                'forced_float32_value': float32(.1), 'stuck_valve_float32_value': float32(45.6),
                'loss': {'error': failed_error, 'writes_after_error': failed_writes,
                         'server_restart_did_not_resume_writes': True, 'archived': failure_record},
                'explicit_new_run': second_record, 'persistence': reopen,
                'limitations': ['Generic server fixture only, not Siemens',
                                'No browser/HTTP measured',
                                'Measured latency is specific to this run; no real-time guarantee']}
    finally:
        if controller is not None:
            controller.cancel()
            await asyncio.gather(controller, return_exceptions=True)
        if not closed:
            await runtime.close()
            store.close()
        if running:
            await server.stop()


async def main():
    default_policy = default_data_dir() / 'machine-policy.json'
    original_policy = default_policy.read_bytes() if default_policy.exists() else None
    logging.basicConfig(level=logging.ERROR)
    try:
        progress('Starting actual CLI fixture, real loopback sockets, isolated policy')
        fixture_saved = WORK.parent / 'fixture-phase-complete.json'
        if '--load-only' in sys.argv and fixture_saved.exists():
            RESULT['phases'].append(json.loads(fixture_saved.read_text(encoding='utf-8')))
        else:
            phase = await fixture_phase()
            RESULT['phases'].append(phase)
            fixture_saved.write_text(json.dumps(phase, ensure_ascii=False, indent=2), encoding='utf-8')
        progress('Starting encrypted 50-equipment/200-tag protocol load')
        RESULT['phases'].append(await load_phase())
        RESULT['status'] = 'passed'
    except BaseException as exc:
        RESULT['status'] = 'failed'
        RESULT['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        current_policy = default_policy.read_bytes() if default_policy.exists() else None
        assert current_policy == original_policy, 'Default personal machine policy changed'
        RESULT['default_user_policy_unchanged'] = True
        RESULT['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        target = EVIDENCE / 'opcua-extended.json'
        target.write_text(json.dumps(RESULT, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(RESULT, ensure_ascii=False, indent=2), flush=True)


asyncio.run(main())
