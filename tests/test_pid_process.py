"""The isolated reader is killed before its temporary input is released."""

import asyncio
import json
from pathlib import Path

import pytest

from fat_studio.pid_process import inspect_isolated


@pytest.mark.asyncio
async def test_cancelling_reader_terminates_worker_and_releases_input(monkeypatch):
    entered = asyncio.Event()
    observed = {}

    class Process:
        returncode = None

        async def communicate(self, payload):
            observed.update(json.loads(payload))
            assert Path(observed["path"]).read_bytes() == b"private drawing"
            entered.set()
            await asyncio.sleep(60)

        def kill(self):
            observed["killed"] = True
            assert Path(observed["path"]).exists()
            self.returncode = -1

        async def wait(self):
            observed["waited"] = True

    async def spawn(*args, **kwargs):
        assert kwargs["stdin"] == asyncio.subprocess.PIPE
        assert kwargs["cwd"].resolve() == Path(__file__).resolve().parents[1]
        return Process()

    monkeypatch.setattr("fat_studio.pid_process.asyncio.create_subprocess_exec", spawn)
    # Simulate the group termination too on Unix without touching a real PID.
    monkeypatch.setattr("fat_studio.pid_process.os.killpg", lambda *args: observed.update(killed=True), raising=False)
    task = asyncio.create_task(inspect_isolated(b"private drawing", "plan.svg", "1", False))
    await asyncio.wait_for(entered.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert observed["killed"] and observed["waited"]
    assert not Path(observed["path"]).exists()
