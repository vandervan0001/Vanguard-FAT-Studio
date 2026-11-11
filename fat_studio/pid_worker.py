"""Bounded child process for local drawing parsers, never a PLC client."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


def limit_resources():
    if os.name != "nt":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
        return None
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    class Limits(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount",
                    "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Limits), ("IoInfo", IO), ("Memory", Basic)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    handle = kernel.CreateJobObjectW(None, None)
    limits = Extended()
    limits.BasicLimitInformation.LimitFlags = 0x2000 | 0x100 | 0x200  # kill on close, process/job memory
    limits.Memory.ProcessMemoryLimit = 2 * 1024**3
    limits.Memory.JobMemoryLimit = 2 * 1024**3
    if not handle or not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        raise ValueError("Isolation mémoire du lecteur P&ID indisponible.")
    if not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
        raise ValueError("Isolation du processus P&ID indisponible.")
    return handle  # Keep the kill-on-close job alive until this process exits.


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    job_handle = limit_resources()
    try:
        request = json.load(sys.stdin)
        from .pid_import import inspect_pid
        data = Path(request["path"]).read_bytes()
        document = inspect_pid(data, request["filename"], pages=request["pages"], ocr=request["ocr"])
        print(json.dumps({"document": document.model_dump(mode="json")}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"error": str(exc)[:2000] or "Lecture P&ID impossible."}, ensure_ascii=False))
    finally:
        _ = job_handle


if __name__ == "__main__":
    main()
