"""Cancellable import isolation; drawing conversion never holds the FAT lock."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory

from .pid_models import PidDocument


async def inspect_isolated(data: bytes, filename: str, pages: str, ocr: bool) -> PidDocument:
    with TemporaryDirectory(prefix="fat-pid-") as folder:
        path = Path(folder) / "source.bin"
        path.write_bytes(data)
        payload = json.dumps({"path": str(path), "filename": filename, "pages": pages, "ocr": ocr})
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
               "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"}
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-B", "-m", "fat_studio.pid_worker",
            cwd=Path(__file__).resolve().parent.parent, env=env,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}),
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(payload.encode("utf-8")), timeout=90)
        except (TimeoutError, asyncio.CancelledError) as exc:
            if process.returncode is None:
                try:
                    if os.name == "nt":
                        process.kill()  # The child job object terminates its CAD descendants too.
                    else:
                        os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            await process.wait()
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise ValueError("Lecture P&ID arrêtée après 90 secondes ; réduire le nombre de pages.") from exc
        if process.returncode or len(stdout) > 5 * 1024 * 1024:
            raise ValueError("Le lecteur P&ID a été arrêté ; réduire la taille ou la complexité du document.")
        try:
            result = json.loads(stdout)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("Le lecteur P&ID n'a pas fourni de résultat valide.") from exc
        if "error" in result:
            raise ValueError(result["error"])
        return PidDocument.model_validate(result["document"])
