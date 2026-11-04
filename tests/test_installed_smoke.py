"""The installed-service check must wait for the worker that holds SQLite open."""

import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time


SMOKE = Path(__file__).resolve().parents[1] / "scripts" / "smoke-installed.py"
namespace = runpy.run_path(str(SMOKE))


def test_installed_worker_shutdown_releases_sqlite_before_cleanup(tmp_path):
    data = tmp_path / "FAT data épreuve"
    data.mkdir()
    worker = (
        "import os,sqlite3,sys,time;from pathlib import Path;"
        "data=Path(sys.argv[1]);db=sqlite3.connect(data/'history.sqlite3');"
        "db.execute('CREATE TABLE samples(value REAL)');db.commit();"
        "(data/'worker.pid').write_text(str(os.getpid()),encoding='ascii');"
        "time.sleep(60)"
    )
    process = subprocess.Popen([sys.executable, "-X", "utf8", "-c", worker, str(data)],
                               cwd=tmp_path, env={**os.environ, "PYTHONUTF8": "1"})
    handle = None
    try:
        deadline = time.monotonic() + 10
        pid_file = data / "worker.pid"
        while not pid_file.exists() or not pid_file.read_text(encoding="ascii"):
            assert process.poll() is None, "SQLite worker exited before becoming ready"
            assert time.monotonic() < deadline, "SQLite worker did not become ready"
            time.sleep(0.02)
        handle = namespace["open_worker_handle"](int(pid_file.read_text(encoding="ascii")))
        assert (data / "history.sqlite3").is_file()
    finally:
        namespace["shutdown"](process, handle)
    # Windows refuses this while the real Python worker still holds SQLite open.
    shutil.rmtree(data)
    assert not data.exists()
    assert process.poll() is not None
