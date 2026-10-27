"""Bounded Windows process lineage proof over live handles and creation times.

Uses the same OpenProcess/GetProcessTimes primitives as the existing profile
owner. NtQueryInformationProcess reads each live process's inherited parent PID;
we inspect only the actual worker's ancestors, never enumerate other processes.
Handles stay open until the complete chain has been checked, preventing PID
reuse during attestation. No executable paths or command lines enter the reply.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os

from renulus.worker_contracts import ProcessAttestation


class BasicInformation(ctypes.Structure):
    _fields_ = [("exit_status", ctypes.c_long), ("peb", ctypes.c_void_p),
                ("affinity", ctypes.c_size_t), ("priority", ctypes.c_long),
                ("pid", ctypes.c_size_t), ("parent_pid", ctypes.c_size_t)]


def attest_launcher(launcher_pid: int) -> ProcessAttestation:
    if os.name != "nt":
        # Renulus is Windows only; no guessed ancestry on other platforms.
        raise ValueError("Windows process attestation unavailable")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    native = ctypes.WinDLL("ntdll")
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    native.NtQueryInformationProcess.argtypes = [wintypes.HANDLE, wintypes.ULONG,
        ctypes.c_void_p, wintypes.ULONG, ctypes.POINTER(wintypes.ULONG)]
    native.NtQueryInformationProcess.restype = ctypes.c_long
    handles, seen, times = [], set(), []
    current, actual_creation = os.getpid(), None
    try:
        for depth in range(17):  # Actual process plus at most sixteen ancestors.
            if current in seen or not 0 < current <= 0xFFFFFFFF:
                raise ValueError("invalid process lineage")
            seen.add(current)
            handle = kernel.OpenProcess(0x1000 | 0x0400, False, current)
            if not handle:
                raise ValueError("uncertain process lineage")
            handles.append(handle)
            creation, exit_time, cpu, user = (wintypes.FILETIME() for _ in range(4))
            if not kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in (creation, exit_time, cpu, user))):
                raise ValueError("uncertain process identity")
            if exit_time.dwLowDateTime or exit_time.dwHighDateTime:
                raise ValueError("terminated process lineage")
            created = creation.dwLowDateTime | creation.dwHighDateTime << 32
            if actual_creation is None:
                actual_creation = created
            if times and created > times[-1]:
                raise ValueError("reused ancestor PID")
            times.append(created)
            if current == launcher_pid:
                return ProcessAttestation(launcher_pid=launcher_pid, actual_pid=os.getpid(),
                    launcher_creation_filetime=str(created), actual_creation_filetime=str(actual_creation),
                    ancestry_depth=depth)
            info, length = BasicInformation(), wintypes.ULONG()
            status = native.NtQueryInformationProcess(handle, 0, ctypes.byref(info),
                ctypes.sizeof(info), ctypes.byref(length))
            if status != 0 or info.pid != current:
                raise ValueError("uncertain process parent")
            current = info.parent_pid
        raise ValueError("process lineage bound exceeded")
    finally:
        for handle in reversed(handles):
            kernel.CloseHandle(handle)
