# SPDX-License-Identifier: MIT
"""Windows ownership through dedicated synthetic Python processes only."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

import pytest


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows native profile ownership")
MODULE = Path(__file__).resolve().parents[2] / "runtime/renulus/runtime/harness_profile_owner.py"

# Load the bootstrap module alone: its public seam must work before app assembly.
CHILD = r'''
import copy, ctypes, importlib.util, json, os, pathlib, subprocess, sys, threading, time, traceback
from dataclasses import asdict
spec = importlib.util.spec_from_file_location("synthetic_profile_owner", sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
boot = {}
try:
    spec.loader.exec_module(module)
    boot = json.loads(sys.stdin.readline())
    scope = module.ProfileOwnerScope(pathlib.Path(boot["root"]),
        boot.get("profile_id", "synthetic-profile"),
        boot.get("domain_store_id", "synthetic-domain"),
        boot.get("runtime_store_id", "synthetic-runtime"))
    if boot.get("worker_thread"):
        result = []
        def acquire_in_worker():
            try:
                result.append(module.acquire_profile_owner(scope, initialize_new=boot.get("initialize_new", False)))
            except Exception as error:
                result.append(error)
        worker = threading.Thread(target=acquire_in_worker)
        worker.start()
        worker.join()
        if isinstance(result[0], Exception):
            raise result[0]
        owner = result[0]
    else:
        owner = module.acquire_profile_owner(scope, initialize_new=boot.get("initialize_new", False))
    print(json.dumps({"ready": True, "actual_pid": os.getpid(), "generation": owner.generation,
        "python": asdict(owner.python_identity), "fence_kind": owner.predecessor.kind,
        "previous_generation": owner.predecessor.previous_generation}), flush=True)
    children = []
    for line in sys.stdin:
        command = json.loads(line)
        if command["action"] == "exit":
            break
        if command["action"] == "fence":
            try:
                candidate = (copy.copy(owner.predecessor) if command.get("copy")
                    else True if command.get("boolean") else owner.predecessor)
                issuer = copy.copy(owner) if command.get("copy_issuer") else owner
                issuer.require_predecessor(candidate)
                print(json.dumps({"accepted": True}), flush=True)
            except Exception as error:
                print(json.dumps({"error": getattr(error, "code", type(error).__name__)}), flush=True)
        if command["action"] == "immutable":
            result = []
            for target, field, value in ((owner.python_identity, "pid", 1),
                    (owner.python_identity, "creation_filetime", 1),
                    (owner.predecessor, "kind", "new_profile"), (owner, "generation", "forged")):
                try:
                    setattr(target, field, value)
                    result.append("mutable")
                except Exception as error:
                    result.append(type(error).__name__)
            print(json.dumps({"mutations": result}), flush=True)
        if command["action"] == "register":
            try:
                reference = owner.register_native(command["pid"], generation=command["generation"])
                print(json.dumps({"identity": asdict(reference)}), flush=True)
            except Exception as error:
                print(json.dumps({"error": getattr(error, "code", type(error).__name__)}), flush=True)
        if command["action"] == "breakaway":
            try:
                child = subprocess.Popen([sys.executable, "-u", "-c", "import time; time.sleep(120)"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_BREAKAWAY_FROM_JOB,
                    close_fds=True)
                print(json.dumps({"pid": child.pid}), flush=True)
            except OSError as error:
                print(json.dumps({"winerror": error.winerror}), flush=True)
        if command["action"] == "child":
            child = subprocess.Popen([sys.executable, "-u", "-c", "import time; time.sleep(120)"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
            children.append(child)
            result = {"pid": child.pid}
            if command.get("register"):
                result["identity"] = asdict(owner.register_native(child.pid,
                    generation=command.get("generation", "synthetic-native-generation")))
            print(json.dumps(result), flush=True)
except Exception as error:
    failure = {"error": getattr(error, "code", type(error).__name__)}
    if boot.get("report_error"):
        failure.update(message=str(error), traceback="".join(traceback.format_exception(error)))
    if boot.get("hold_failure"):
        failure["actual_pid"] = os.getpid()
    print(json.dumps(failure), flush=True)
    if boot.get("hold_failure"):
        # Production must abort bootstrap. The fixture traps only to observe that
        # failure cleanup did not close the assigned job or release the mutex.
        for line in sys.stdin:
            command = json.loads(line)
            if command["action"] == "exit":
                break
            if command["action"] == "retry":
                try:
                    module.acquire_profile_owner(scope)
                    print(json.dumps({"unexpected_lease": True}), flush=True)
                except Exception as retry_error:
                    print(json.dumps({"error": getattr(retry_error, "code", type(retry_error).__name__)}), flush=True)
            if command["action"] == "child":
                child = subprocess.Popen([sys.executable, "-u", "-c", "import time; time.sleep(120)"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
                print(json.dumps({"pid": child.pid}), flush=True)
'''


class DedicatedOwner:
    def __init__(self, root, *, initialize_new=False, direct_interpreter=False, **identity):
        # This is the actual CPython backing the managed venv, not another cohort.
        # Its redirector adds a separate ancestor job that can end the child tree.
        interpreter = sys._base_executable if direct_interpreter else sys.executable
        self.process = subprocess.Popen([interpreter, "-B", "-u", "-c", CHILD, str(MODULE)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
        self.messages = queue.Queue()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        self.send({"root": str(root), "initialize_new": initialize_new, **identity})
        self.initial = self.receive()
        self.actual = (ObservedChild(self.initial["actual_pid"],
            creation=self.initial.get("python", {}).get("creation_filetime"))
            if "actual_pid" in self.initial else None)

    def _read(self):
        for line in self.process.stdout:
            self.messages.put(line)
        self.messages.put(None)

    def send(self, message):
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def receive(self):
        line = self.messages.get(timeout=10)
        assert line is not None, "The owned synthetic Python child exited without a result"
        return json.loads(line)

    def command(self, **message):
        self.send(message)
        return self.receive()

    def stop(self, *, crash=False):
        if self.actual and self.actual.wait(0) == 258:
            if crash:
                self.actual.terminate()
            else:
                self.send({"action": "exit"})
            assert self.actual.wait(5000) == 0
        elif self.process.poll() is None and not self.actual:
            self.process.terminate()  # Only the fixture's retained launcher handle.
        self.process.wait(timeout=10)
        self.reader.join(timeout=2)
        if not self.process.stdin.closed:
            self.process.stdin.close()
        if not self.process.stdout.closed:
            self.process.stdout.close()


@pytest.fixture
def owners():
    owned = []

    def create(root, **options):
        owner = DedicatedOwner(root, **options)
        owned.append(owner)
        return owner

    yield create
    for owner in reversed(owned):
        owner.stop(crash=True)
        if owner.actual:
            owner.actual.close()


class ObservedChild:
    """Independent kernel observation, only for PIDs returned by owned fixtures."""
    def __init__(self, pid, *, creation=None):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel.TerminateProcess.restype = wintypes.BOOL
        self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        self.kernel.GetProcessTimes.restype = wintypes.BOOL
        self.handle = self.kernel.OpenProcess(0x00100000 | 0x1000 | 1, False, pid)
        assert self.handle, "Cannot observe our owned synthetic child"
        if creation is not None:
            times = [wintypes.FILETIME() for _ in range(4)]
            assert self.kernel.GetProcessTimes(self.handle, *(ctypes.byref(value) for value in times))
            assert times[0].dwLowDateTime | times[0].dwHighDateTime << 32 == creation

    def wait(self, milliseconds):
        return self.kernel.WaitForSingleObject(self.handle, milliseconds)

    def close(self):
        self.kernel.CloseHandle(self.handle)

    def terminate(self):
        assert self.kernel.TerminateProcess(self.handle, 9)


class ObservedJob:
    """Hold only an owned generation's existing job, without assigning any process."""
    def __init__(self, name):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel.OpenJobObjectW.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.OpenJobObjectW(0x04, False, name)
        assert self.handle, "Cannot observe our owned generation's job"

    def close(self):
        if self.handle:
            assert self.kernel.CloseHandle(self.handle)
            self.handle = None


class ReceiptDeleteBlock:
    """Deny atomic replacement of one owned synthetic receipt, without mocks."""
    def __init__(self, path):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.CreateFileW(str(path), 0x80000000, 0x03, None, 3, 0x80, None)
        assert self.handle != ctypes.c_void_p(-1).value, "Cannot hold our owned receipt"

    def close(self):
        if self.handle:
            assert self.kernel.CloseHandle(self.handle)
            self.handle = None


@pytest.mark.parametrize("existing_empty", [False, True])
def test_new_profile_fence_and_inherited_child_crash_cleanup(tmp_path, owners, existing_empty):
    root = tmp_path / "new-profile"
    if existing_empty:
        root.mkdir()
    owner = owners(root, initialize_new=True)
    assert owner.initial.get("ready") is True, owner.initial
    assert owner.initial["fence_kind"] == "new_profile"
    assert owner.initial["previous_generation"] is None
    assert owner.initial["python"]["pid"] == owner.initial["actual_pid"]
    assert owner.initial["python"]["creation_filetime"] > 0
    child = owner.command(action="child")
    observed = ObservedChild(child["pid"])
    try:
        assert observed.wait(0) == 258  # WAIT_TIMEOUT: the inherited child is alive.
        owner.stop(crash=True)
        assert observed.wait(5000) == 0  # WAIT_OBJECT_0: actual child termination.
    finally:
        observed.close()


def test_reopen_issues_fence_for_recorded_terminated_predecessor(tmp_path, owners):
    root = tmp_path / "reopen-profile"
    previous = owners(root, initialize_new=True)
    assert previous.initial.get("ready") is True, previous.initial
    previous.stop()
    reopened = owners(root)
    assert reopened.initial.get("ready") is True, reopened.initial
    assert reopened.initial["fence_kind"] == "settled_predecessor"
    assert reopened.initial["previous_generation"] == previous.initial["generation"]
    assert reopened.initial["generation"] != previous.initial["generation"]


def test_registered_native_identity_survives_crash_reopen_without_body(tmp_path, owners):
    root = tmp_path / "native-profile"
    owner = owners(root, initialize_new=True)
    assert owner.initial.get("ready") is True, owner.initial
    child = owner.command(action="child", register=True, unused_body="PRIVATE_BODY_CANARY")
    assert "identity" in child, child
    assert child.get("identity", {}).get("pid") == child.get("pid"), child
    observed = ObservedChild(child["pid"], creation=child["identity"]["creation_filetime"])
    try:
        assert observed.wait(0) == 258
        assert "PRIVATE_BODY_CANARY" not in (root / ".renulus-profile-owner.json").read_text()
        owner.stop(crash=True)
        assert observed.wait(5000) == 0
        reopened = owners(root)
        assert reopened.initial.get("ready") is True, reopened.initial
        assert reopened.initial["previous_generation"] == owner.initial["generation"]
    finally:
        observed.close()


def test_predecessor_fence_requires_exact_current_issuer(tmp_path, owners):
    owner = owners(tmp_path / "issuer-profile", initialize_new=True)
    assert owner.initial.get("ready") is True, owner.initial
    assert owner.command(action="fence") == {"accepted": True}
    assert owner.command(action="fence", copy=True) == {"error": "profile_owner_fence_unbound"}
    assert owner.command(action="fence", boolean=True) == {"error": "profile_owner_fence_unbound"}
    assert owner.command(action="fence", copy_issuer=True) == {"error": "profile_owner_lease_unbound"}
    assert owner.command(action="immutable") == {"mutations": ["FrozenInstanceError"] * 4}


def test_worker_thread_acquisition_is_denied_before_root_mutation(tmp_path, owners):
    root = tmp_path / "thread-profile"
    rejected = owners(root, initialize_new=True, worker_thread=True)
    assert rejected.initial == {"error": "profile_owner_main_thread_required"}
    assert not root.exists()
    permitted = owners(root, initialize_new=True)
    assert permitted.initial.get("ready") is True, permitted.initial


def test_reopen_denies_recorded_job_with_unregistered_live_child(tmp_path, owners):
    root = tmp_path / "retained-job-profile"
    owner = owners(root, initialize_new=True, direct_interpreter=True)
    assert owner.initial.get("ready") is True, owner.initial
    receipt = root / ".renulus-profile-owner.json"
    prior_bytes = receipt.read_bytes()
    record = json.loads(prior_bytes)
    assert record["native"] == []
    job = ObservedJob(record["job_name"])
    child = owner.command(action="child")
    observed = ObservedChild(child["pid"])
    try:
        owner.stop(crash=True)
        assert owner.actual.wait(0) == 0
        assert observed.wait(0) == 258  # The retained previous job still owns live work.
        denied = owners(root)
        assert denied.initial == {"error": "profile_owner_predecessor_pending"}
        assert receipt.read_bytes() == prior_bytes
        assert observed.wait(0) == 258
        job.close()
        assert observed.wait(5000) == 0
        reopened = owners(root)
        assert reopened.initial.get("ready") is True, reopened.initial
        assert reopened.initial["previous_generation"] == owner.initial["generation"]
        assert reopened.command(action="fence") == {"accepted": True}
    finally:
        job.close()
        observed.close()


def test_reopen_rejects_truncated_native_registration_receipt(tmp_path, owners):
    root = tmp_path / "truncated-native-profile"
    owner = owners(root, initialize_new=True)
    assert owner.initial.get("ready") is True, owner.initial
    child = owner.command(action="child", register=True)
    assert "identity" in child, child
    owner.stop()
    receipt = root / ".renulus-profile-owner.json"
    record = json.loads(receipt.read_bytes())
    assert len(record["native"]) == 1
    record["native"] = []  # Dropped process entries cannot become an empty-origin fence.
    receipt.write_text(json.dumps(record))
    damaged = receipt.read_bytes()
    denied = owners(root)
    assert denied.initial == {"error": "profile_owner_receipt_invalid"}
    assert receipt.read_bytes() == damaged


def test_profile_mutex_excludes_competitors_without_writes(tmp_path, owners):
    root = tmp_path / "exclusive-profile"
    owner = owners(root, initialize_new=True)
    assert owner.initial.get("ready") is True, owner.initial
    receipt = root / ".renulus-profile-owner.json"
    previous = receipt.read_bytes()
    competitor = owners(root, initialize_new=True)
    assert competitor.initial == {"error": "profile_owner_busy"}
    assert receipt.read_bytes() == previous
    separate = owners(tmp_path / "independent-profile", initialize_new=True)
    assert separate.initial.get("ready") is True, separate.initial
    assert owner.command(action="fence") == {"accepted": True}


@pytest.mark.parametrize("shape", ["absent_root", "empty_root", "nonempty", "legacy", "incomplete"])
def test_existing_profile_without_complete_receipt_fails_closed(tmp_path, owners, shape):
    root = tmp_path / "existing-profile"
    if shape != "absent_root":
        root.mkdir()
    receipt = root / ".renulus-profile-owner.json"
    if shape == "nonempty":
        (root / "owned-synthetic.txt").write_text("SYNTHETIC_CANARY")
    elif shape in ("legacy", "incomplete"):
        receipt.write_text('{"version":0}' if shape == "legacy" else '{"version":1,')
    previous = {file.name: file.read_bytes() for file in root.iterdir()} if root.exists() else None
    # Explicit new initialization cannot override a nonempty existing profile.
    denied = owners(root, initialize_new=shape in ("nonempty", "legacy", "incomplete"))
    expected = "profile_owner_receipt_invalid" if shape in ("legacy", "incomplete") else "profile_owner_receipt_missing"
    assert denied.initial == {"error": expected}
    current = {file.name: file.read_bytes() for file in root.iterdir()} if root.exists() else None
    assert current == previous


@pytest.mark.parametrize("field", ["profile_id", "domain_store_id", "runtime_store_id"])
def test_reopen_rejects_different_canonical_scope_without_writes(tmp_path, owners, field):
    root = tmp_path / "scope-profile"
    owner = owners(root, initialize_new=True)
    assert owner.initial.get("ready") is True, owner.initial
    owner.stop()
    receipt = root / ".renulus-profile-owner.json"
    previous = receipt.read_bytes()
    denied = owners(root, **{field: "other-synthetic-identity"})
    assert denied.initial == {"error": "profile_owner_receipt_invalid"}
    assert receipt.read_bytes() == previous


def test_native_registration_is_bound_idempotent_and_conflicts_fail_closed(tmp_path, owners):
    root = tmp_path / "native-guard-profile"
    owner = owners(root, initialize_new=True)
    foreign = owners(tmp_path / "foreign-profile", initialize_new=True)
    assert owner.initial.get("ready") is True, owner.initial
    assert foreign.initial.get("ready") is True, foreign.initial
    first = owner.command(action="child")
    second = owner.command(action="child")
    registered = owner.command(action="register", pid=first["pid"], generation="native-first")
    assert registered.get("identity", {}).get("pid") == first["pid"], registered
    receipt = root / ".renulus-profile-owner.json"
    previous = receipt.read_bytes()
    assert json.loads(previous)["native_count"] == 1
    assert owner.command(action="register", pid=first["pid"], generation="native-first") == registered
    for pid, generation, code in (
            (first["pid"], "other-generation", "profile_owner_native_conflict"),
            (second["pid"], "native-first", "profile_owner_native_conflict"),
            (foreign.initial["actual_pid"], "foreign-generation", "profile_owner_native_unbound"),
            (True, "boolean-pid", "profile_owner_native_invalid"),
            (owner.initial["actual_pid"], "self-pid", "profile_owner_native_invalid")):
        assert owner.command(action="register", pid=pid, generation=generation) == {"error": code}
        assert receipt.read_bytes() == previous
    assert foreign.actual.wait(0) == 258


def test_reused_pid_creation_pair_does_not_signal_new_owned_process(tmp_path, owners):
    root = tmp_path / "reuse-profile"
    previous = owners(root, initialize_new=True)
    assert previous.initial.get("ready") is True, previous.initial
    previous.stop()
    newer = owners(tmp_path / "newer-profile", initialize_new=True)
    assert newer.initial.get("ready") is True, newer.initial
    receipt = root / ".renulus-profile-owner.json"
    record = json.loads(receipt.read_bytes())
    record["python"] = newer.initial["python"]
    receipt.write_text(json.dumps(record))
    alive_reference = receipt.read_bytes()
    denied = owners(root)
    assert denied.initial == {"error": "profile_owner_predecessor_pending"}
    assert receipt.read_bytes() == alive_reference
    assert newer.actual.wait(0) == 258
    # A controlled reused-PID reference: this exact live creation is not the old owner.
    record["python"] = {"pid": newer.initial["actual_pid"],
        "creation_filetime": newer.initial["python"]["creation_filetime"] - 1}
    receipt.write_text(json.dumps(record))
    reopened = owners(root)
    assert reopened.initial.get("ready") is True, reopened.initial
    assert reopened.initial["previous_generation"] == previous.initial["generation"]
    assert newer.actual.wait(0) == 258
    assert newer.command(action="fence") == {"accepted": True}


def test_publication_failure_preserves_receipt_and_retains_process_lifetime_handles(tmp_path, owners):
    root = tmp_path / "publication-profile"
    previous = owners(root, initialize_new=True)
    assert previous.initial.get("ready") is True, previous.initial
    previous.stop()
    receipt = root / ".renulus-profile-owner.json"
    original = receipt.read_bytes()
    blocker = ReceiptDeleteBlock(receipt)
    try:
        failed = owners(root, direct_interpreter=True, hold_failure=True)
        assert failed.initial.get("error") == "profile_owner_journal_failed", failed.initial
        assert "ready" not in failed.initial
        assert failed.actual.wait(0) == 258  # Cleanup has not killed its current Python.
        assert receipt.read_bytes() == original
        assert sorted(file.name for file in root.iterdir()) == [receipt.name]
        assert failed.command(action="retry") == {"error": "profile_owner_process_bound"}
        denied = owners(root)
        assert denied.initial == {"error": "profile_owner_busy"}
        child = failed.command(action="child")
        observed = ObservedChild(child["pid"])
        try:
            assert observed.wait(0) == 258
            failed.stop(crash=True)
            assert observed.wait(5000) == 0
        finally:
            observed.close()
    finally:
        blocker.close()
    reopened = owners(root)
    assert reopened.initial.get("ready") is True, reopened.initial
    assert reopened.initial["previous_generation"] == previous.initial["generation"]


def test_duplicate_native_registration_origins_fail_closed_on_reopen(tmp_path, owners):
    root = tmp_path / "duplicate-origin-profile"
    previous = owners(root, initialize_new=True)
    assert previous.initial.get("ready") is True, previous.initial
    assert "identity" in previous.command(action="child", register=True)
    previous.stop()
    receipt = root / ".renulus-profile-owner.json"
    record = json.loads(receipt.read_bytes())
    record["native"].append(record["native"][0])
    record["native_count"] = 2
    receipt.write_text(json.dumps(record))
    original = receipt.read_bytes()
    denied = owners(root)
    assert denied.initial == {"error": "profile_owner_receipt_invalid"}
    assert receipt.read_bytes() == original


def test_filesystem_error_is_sanitized_without_underlying_path_context(tmp_path, owners):
    root = tmp_path / "SYNTHETIC_PATH_CANARY<invalid>"
    rejected = owners(root, initialize_new=True, report_error=True)
    assert rejected.initial.get("error") == "profile_owner_storage_unavailable", rejected.initial
    assert rejected.initial["message"] == "profile_owner_storage_unavailable"
    assert "SYNTHETIC_PATH_CANARY" not in rejected.initial["traceback"]
    assert not root.exists()


@pytest.mark.parametrize("damage", ["native_missing", "count_missing", "count_boolean",
    "count_mismatch", "native_null", "version_boolean", "body_field", "duplicate_key"])
def test_incomplete_or_unclassified_receipt_is_denied_without_replacement(tmp_path, owners, damage):
    root = tmp_path / "receipt-shape-profile"
    previous = owners(root, initialize_new=True)
    assert previous.initial.get("ready") is True, previous.initial
    previous.stop()
    receipt = root / ".renulus-profile-owner.json"
    record = json.loads(receipt.read_bytes())
    assert record["native"] == [] and record["native_count"] == 0
    if damage == "native_missing":
        del record["native"]
    elif damage == "count_missing":
        del record["native_count"]
    elif damage == "count_boolean":
        record["native_count"] = False
    elif damage == "count_mismatch":
        record["native_count"] = 1
    elif damage == "native_null":
        record["native"] = None
    elif damage == "version_boolean":
        record["version"] = True
    elif damage == "body_field":
        record["body"] = "SYNTHETIC_BODY_CANARY"
    payload = json.dumps(record)
    if damage == "duplicate_key":
        payload = payload[:-1] + ',"native_count":0}'
    receipt.write_text(payload)
    damaged = receipt.read_bytes()
    rejected = owners(root)
    assert rejected.initial == {"error": "profile_owner_receipt_invalid"}
    assert receipt.read_bytes() == damaged


def test_native_child_cannot_break_away_from_current_owner_job(tmp_path, owners):
    owner = owners(tmp_path / "no-breakaway-profile", initialize_new=True, direct_interpreter=True)
    assert owner.initial.get("ready") is True, owner.initial
    result = owner.command(action="breakaway")
    if "pid" in result:  # Cleanup remains restricted to this fixture's own child.
        escaped = ObservedChild(result["pid"])
        try:
            escaped.terminate()
            assert escaped.wait(5000) == 0
        finally:
            escaped.close()
    assert result == {"winerror": 5}
    assert owner.command(action="fence") == {"accepted": True}
