# SPDX-License-Identifier: MIT
"""Windows process-lifetime profile ownership, before any app/engine assembly.

Call only on the main thread of the dedicated Python profile process. Acquisition
assigns that process to a no-breakaway job; the handles have no release API and
remain held until process exit. Nothing here opens SQLite or provider state.

Primary Windows contracts:
https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
https://learn.microsoft.com/en-us/windows/win32/sync/mutex-objects
https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from threading import RLock, current_thread, main_thread
from uuid import uuid4


_JOURNAL = ".renulus-profile-owner.json"
_POLICY = "kill_on_close_no_breakaway_v1"
_KILL_ON_CLOSE = 0x2000
_BREAKAWAY = 0x0800 | 0x1000
_MAX_RECEIPT = 16384
_MAX_NATIVE = 32
_BOUND_OWNER = None
_LIFETIME_HANDLES = []
_ACQUIRE_LOCK = RLock()


class ProfileOwnerError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _deny(code):
    raise ProfileOwnerError(code) from None


@dataclass(frozen=True)
class ProfileOwnerScope:
    root: Path
    profile_id: str
    domain_store_id: str
    runtime_store_id: str


@dataclass(frozen=True)
class ProcessIdentity:
    """PID paired with the exact unsigned Windows creation FILETIME."""
    pid: int
    creation_filetime: int


@dataclass(frozen=True, init=False)
class SettledOwnerFence:
    """Issuer-only evidence; copied fields or deserialized values grant nothing."""
    scope: ProfileOwnerScope
    kind: str
    previous_generation: str | None
    receipt_sha256: str | None


class _BasicLimits(ctypes.Structure):
    _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
        ("flags", wintypes.DWORD), ("minimum", ctypes.c_size_t),
        ("maximum", ctypes.c_size_t), ("active_limit", wintypes.DWORD),
        ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
        ("scheduling", wintypes.DWORD)]


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
        ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [("basic", _BasicLimits), ("io", _IoCounters),
        ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
        ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]


class _Accounting(ctypes.Structure):
    _fields_ = [(name, ctypes.c_int64) for name in
        ("user", "kernel", "period_user", "period_kernel")] + [(name, wintypes.DWORD)
        for name in ("page_faults", "total", "active", "terminated")]


class _Kernel:
    def __init__(self):
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        declarations = {
            "CreateMutexW": ([ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
            "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            "ReleaseMutex": ([wintypes.HANDLE], wintypes.BOOL),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
            "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            "SetInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                wintypes.DWORD], wintypes.BOOL),
            "AssignProcessToJobObject": ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            "IsProcessInJob": ([wintypes.HANDLE, wintypes.HANDLE,
                ctypes.POINTER(wintypes.BOOL)], wintypes.BOOL),
            "GetCurrentProcess": ([], wintypes.HANDLE),
            "OpenProcess": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            "OpenJobObjectW": ([wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
            "QueryInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            "GetProcessTimes": ([wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4,
                wintypes.BOOL),
            "MoveFileExW": ([wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD], wintypes.BOOL),
        }
        for name, (arguments, result) in declarations.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = arguments, result

    def identity(self, process, pid):
        values = [wintypes.FILETIME() for _ in range(4)]
        if not self.api.GetProcessTimes(process, *(ctypes.byref(value) for value in values)):
            _deny("profile_owner_process_uncertain")
        creation = values[0].dwLowDateTime | values[0].dwHighDateTime << 32
        return ProcessIdentity(pid, creation)

    def mutex(self, key):
        handle = self.api.CreateMutexW(None, False, "Global\\RenulusProfileOwner-" + key)
        if not handle:
            _deny("profile_owner_mutex_unavailable")
        result = self.api.WaitForSingleObject(handle, 0)
        if result not in (0, 0x80):  # Acquired, including abandoned ownership.
            self.api.CloseHandle(handle)
            _deny("profile_owner_busy" if result == 258 else "profile_owner_mutex_uncertain")
        return handle

    def job(self, name):
        handle = self.api.CreateJobObjectW(None, name)
        if not handle:
            _deny("profile_owner_job_unavailable")
        if ctypes.get_last_error() == 183:  # Never adopt an existing job as new evidence.
            self.api.CloseHandle(handle)
            _deny("profile_owner_job_conflict")
        limits = _ExtendedLimits()
        limits.basic.flags = _KILL_ON_CLOSE
        if not self.api.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.api.CloseHandle(handle)
            _deny("profile_owner_job_unavailable")
        return handle

    def require_terminated(self, reference):
        process = self.api.OpenProcess(0x00100000 | 0x1000, False, reference["pid"])
        if not process:
            if ctypes.get_last_error() == 87:  # This recorded PID no longer exists.
                return
            _deny("profile_owner_process_uncertain")
        try:
            actual = self.identity(process, reference["pid"])
            if actual.creation_filetime != reference["creation_filetime"]:
                return  # PID reuse: this is not the recorded process; never signal it.
            result = self.api.WaitForSingleObject(process, 0)
            if result != 0:
                _deny("profile_owner_predecessor_pending" if result == 258
                    else "profile_owner_process_uncertain")
        finally:
            self.api.CloseHandle(process)

    def require_job_terminated(self, name):
        job = self.api.OpenJobObjectW(0x04, False, name)  # JOB_OBJECT_QUERY
        if not job:
            if ctypes.get_last_error() == 2:  # The recorded job object has ceased to exist.
                return
            _deny("profile_owner_job_uncertain")
        try:
            limits, accounting = _ExtendedLimits(), _Accounting()
            if (not self.api.QueryInformationJobObject(job, 9, ctypes.byref(limits),
                    ctypes.sizeof(limits), None)
                    or not self.api.QueryInformationJobObject(job, 1, ctypes.byref(accounting),
                    ctypes.sizeof(accounting), None)):
                _deny("profile_owner_job_uncertain")
            if not limits.basic.flags & _KILL_ON_CLOSE or limits.basic.flags & _BREAKAWAY:
                _deny("profile_owner_receipt_invalid")
            if accounting.active:
                _deny("profile_owner_predecessor_pending")
        finally:
            self.api.CloseHandle(job)

    def require_member(self, process, job):
        member = wintypes.BOOL()
        if not self.api.IsProcessInJob(process, job, ctypes.byref(member)) or not member.value:
            _deny("profile_owner_native_unbound")

    def native_identity(self, pid, job):
        process = self.api.OpenProcess(0x00100000 | 0x1000, False, pid)
        if not process:
            _deny("profile_owner_native_unavailable")
        try:
            self.require_member(process, job)
            reference = self.identity(process, pid)
            if self.api.WaitForSingleObject(process, 0) != 258:
                _deny("profile_owner_native_unavailable")
            return reference
        finally:
            self.api.CloseHandle(process)


def _scope_keys(scope):
    return {"root_key": hashlib.sha256(str(scope.root).casefold().encode()).hexdigest(),
        "profile_id": scope.profile_id, "domain_store_id": scope.domain_store_id,
        "runtime_store_id": scope.runtime_store_id}


def _validate_scope(scope):
    if (type(scope) is not ProfileOwnerScope or not isinstance(scope.root, Path)
            or not scope.root.is_absolute() or scope.root == Path(scope.root.anchor)
            or scope.root.resolve() != scope.root
            or any(not isinstance(value, str) or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}", value) for value in
                (scope.profile_id, scope.domain_store_id, scope.runtime_store_id))):
        _deny("profile_owner_scope_invalid")


def _wire(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _job_name(keys, generation):
    return "Global\\RenulusProfileJob-" + keys["root_key"] + "-" + generation


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _deny("profile_owner_receipt_invalid")
        result[key] = value
    return result


def _process_reference(value):
    return (type(value) is dict and set(value) == {"pid", "creation_filetime"}
        and type(value["pid"]) is int and 0 < value["pid"] <= 0xffffffff
        and type(value["creation_filetime"]) is int and 0 < value["creation_filetime"] < 1 << 64)


def _previous(root, keys, kernel):
    path = root / _JOURNAL
    if not path.exists():
        _deny("profile_owner_receipt_missing")
    try:
        info = path.lstat()
        if (path.is_symlink() or not path.is_file() or info.st_nlink != 1
                or getattr(info, "st_file_attributes", 0) & 0x400 or info.st_size > _MAX_RECEIPT):
            _deny("profile_owner_receipt_invalid")
        with path.open("rb") as source:
            payload = source.read(_MAX_RECEIPT + 1)
        if len(payload) > _MAX_RECEIPT:
            _deny("profile_owner_receipt_invalid")
        record = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique)
        if (type(record) is not dict or set(record) != {"version", *keys, "generation",
                "python", "job_name", "job_policy", "native", "native_count"}
                or type(record["version"]) is not int or record["version"] != 1
                or not isinstance(record["generation"], str)
                or not re.fullmatch(r"[0-9a-f]{32}", record["generation"])
                or any(record[key] != value for key, value in keys.items())
                or record["job_name"] != _job_name(keys, record["generation"])
                or record["job_policy"] != _POLICY or not _process_reference(record["python"])
                or type(record["native"]) is not list or len(record["native"]) > _MAX_NATIVE
                or type(record["native_count"]) is not int
                or record["native_count"] != len(record["native"])
                or any(type(item) is not dict or set(item) != {"generation", "process"}
                    or not isinstance(item["generation"], str)
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}", item["generation"])
                    or not _process_reference(item["process"]) for item in record["native"])):
            _deny("profile_owner_receipt_invalid")
        native = record["native"]
        if (len({item["generation"] for item in native}) != len(native)
                or len({(item["process"]["pid"], item["process"]["creation_filetime"])
                    for item in native}) != len(native)
                or any(item["process"] == record["python"] for item in native)):
            _deny("profile_owner_receipt_invalid")
    except (OSError, UnicodeError, ValueError, RecursionError):
        _deny("profile_owner_receipt_invalid")
    kernel.require_terminated(record["python"])
    for item in record["native"]:
        kernel.require_terminated(item["process"])
    kernel.require_job_terminated(record["job_name"])
    return record["generation"], hashlib.sha256(payload).hexdigest()


def _publish(root, record, kernel):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=root, prefix=".profile-owner-", suffix=".tmp",
                delete=False) as staged:
            temporary = Path(staged.name)
            staged.write(_wire(record))
            staged.flush()
            os.fsync(staged.fileno())
        if not kernel.api.MoveFileExW(str(temporary), str(root / _JOURNAL), 0x01 | 0x08):
            _deny("profile_owner_journal_failed")
        temporary = None
    except OSError:
        _deny("profile_owner_journal_failed")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class ProfileOwnerLease:
    """A retained process scope. It cannot be released by an observer or GC."""
    scope: ProfileOwnerScope
    generation: str
    python_identity: ProcessIdentity
    predecessor: SettledOwnerFence
    _kernel: _Kernel = field(repr=False, compare=False)
    _mutex: int = field(repr=False, compare=False)
    _job: int = field(repr=False, compare=False)
    _record: dict = field(repr=False, compare=False)
    _lock: object = field(default_factory=RLock, repr=False, compare=False)

    def _require_current(self):
        if self is not _BOUND_OWNER or os.getpid() != self.python_identity.pid:
            _deny("profile_owner_lease_unbound")
        process = self._kernel.api.GetCurrentProcess()
        if self._kernel.identity(process, os.getpid()) != self.python_identity:
            _deny("profile_owner_lease_unbound")
        self._kernel.require_member(process, self._job)

    def require_predecessor(self, fence: SettledOwnerFence) -> None:
        """Accept only this live issuer's opaque predecessor evidence."""
        self._require_current()
        if fence is not self.predecessor:
            _deny("profile_owner_fence_unbound")

    def register_native(self, pid: int, *, generation: str) -> ProcessIdentity:
        """Record a live current-job identity before admitting native work.

        Exact replay is idempotent; conflicting generations/identities fail closed.
        Registration publication errors are fatal to bootstrap/native admission.
        The whole inherited tree remains contained even before registration.
        """
        self._require_current()
        if (type(pid) is not int or not 0 < pid <= 0xffffffff or pid == self.python_identity.pid
                or not isinstance(generation, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}", generation)):
            _deny("profile_owner_native_invalid")
        with self._lock:
            identity = self._kernel.native_identity(pid, self._job)
            item = {"generation": generation, "process": {
                "pid": identity.pid, "creation_filetime": identity.creation_filetime}}
            if item in self._record["native"]:
                return identity
            if any(value["generation"] == generation or value["process"] == item["process"]
                    for value in self._record["native"]):
                _deny("profile_owner_native_conflict")
            if len(self._record["native"]) >= _MAX_NATIVE:
                _deny("profile_owner_native_capacity")
            updated = {**self._record, "native": [*self._record["native"], item],
                "native_count": len(self._record["native"]) + 1}
            _publish(self.scope.root, updated, self._kernel)
            self._record.update(updated)
            return identity


def acquire_profile_owner(scope: ProfileOwnerScope, *, initialize_new: bool = False,
                          adopt_legacy: bool = False) -> ProfileOwnerLease:
    """Bind once on the dedicated process's main thread, before any app writes.

    Every acquisition error is fatal to bootstrap. If assignment already passed,
    its job and mutex handles stay retained until Python exits; cleanup must not
    close the assigned job and kill the current process. No lease is returned
    until the reference-only journal is durably published.
    """
    with _ACQUIRE_LOCK:
        try:
            return _acquire(scope, initialize_new=initialize_new, adopt_legacy=adopt_legacy)
        except OSError:
            _deny("profile_owner_storage_unavailable")


def _acquire(scope, *, initialize_new, adopt_legacy=False):
    global _BOUND_OWNER
    if os.name != "nt":
        _deny("profile_owner_windows_required")
    if current_thread() is not main_thread():
        _deny("profile_owner_main_thread_required")
    if _BOUND_OWNER is not None or _LIFETIME_HANDLES:
        _deny("profile_owner_process_bound")
    _validate_scope(scope)
    if type(initialize_new) is not bool or type(adopt_legacy) is not bool:
        _deny("profile_owner_scope_invalid")
    kernel = _Kernel()
    keys = _scope_keys(scope)
    mutex = kernel.mutex(keys["root_key"])
    job, assigned = None, False
    try:
        empty = not scope.root.exists() or (scope.root.is_dir() and not any(scope.root.iterdir()))
        # Ordinary desktop startup already owns Electron's profile instance lock.
        # A pre-OpenCode profile has no native store or prior issuer to recover.
        legacy = (adopt_legacy and not (scope.root / _JOURNAL).exists()
                  and not (scope.root / 'state/harness').exists())
        previous_generation, receipt_sha256 = (None, None) if (initialize_new and empty) or legacy else (
            _previous(scope.root, keys, kernel))
        generation = uuid4().hex
        job_name = _job_name(keys, generation)
        job = kernel.job(job_name)
        process = kernel.api.GetCurrentProcess()
        python = kernel.identity(process, os.getpid())
        if not kernel.api.AssignProcessToJobObject(job, process):
            _deny("profile_owner_job_assignment_failed")
        assigned = True
        # Handle closure would kill this process and its descendants. Keep all
        # lifetime handles even if durable publication fails and the caller exits.
        _LIFETIME_HANDLES.extend((kernel, mutex, job))
        scope.root.mkdir(parents=True, exist_ok=True)
        record = {"version": 1, **keys, "generation": generation,
            "python": {"pid": python.pid, "creation_filetime": python.creation_filetime},
            # Zero declares no completed native registration yet, not an empty
            # process tree. The recorded job also guards unregistered descendants.
            "job_name": job_name, "job_policy": _POLICY, "native": [], "native_count": 0}
        _publish(scope.root, record, kernel)
        fence = object.__new__(SettledOwnerFence)
        for name, value in {"scope": scope,
                "kind": "settled_predecessor" if previous_generation else "new_profile",
                "previous_generation": previous_generation, "receipt_sha256": receipt_sha256}.items():
            object.__setattr__(fence, name, value)
        lease = ProfileOwnerLease(scope, generation, python, fence, kernel, mutex, job, record)
        _BOUND_OWNER = lease
        return lease
    finally:
        if not assigned:
            if job:
                kernel.api.CloseHandle(job)
            kernel.api.ReleaseMutex(mutex)
            kernel.api.CloseHandle(mutex)
