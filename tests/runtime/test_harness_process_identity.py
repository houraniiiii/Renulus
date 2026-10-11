"""Scalar native identity over the public owned process lifecycle."""
import asyncio
import ctypes
from ctypes import wintypes
from dataclasses import FrozenInstanceError, asdict
import os
from pathlib import Path
import sys

import pytest

from renulus.runtime.harness_process import (
    HarnessProcessConfig, HarnessProcessError, ManagedHarnessProcess, NativeProcessIdentity,
)


def config(tmp_path, **settings):
    return HarnessProcessConfig(node_executable=Path(sys.executable),
        host_entry=Path(__file__).parent / "fixtures/harness_child.py",
        profile_root=tmp_path / "profile", profile_id="synthetic-profile",
        store_id="synthetic-runtime", domain_store_id="synthetic-domain",
        domain_path="state/renulus.sqlite", boot_settings={"test": settings})


@pytest.mark.skipif(os.name != "nt", reason="Actual Windows subprocess identity observation")
async def test_authenticated_native_identity_is_frozen_scalar_live_child_and_expires_on_close(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path))
    observed = None
    try:
        identity = process.native_identity()
        assert type(identity) is NativeProcessIdentity
        assert type(identity.pid) is int and identity.pid > 0 and identity.pid != os.getpid()
        ready = await process.request("host.status", {}, "status", "1", 1)
        assert asdict(identity) == {
            "pid": identity.pid, "profile_id": "synthetic-profile",
            "store_id": "synthetic-runtime", "generation": ready["generation"]}
        with pytest.raises(FrozenInstanceError):
            identity.pid = os.getpid()
        assert process.native_identity() == identity
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        observed = kernel.OpenProcess(0x00100000, False, identity.pid)
        assert observed
        assert kernel.WaitForSingleObject(observed, 0) == 258
        assert (await process.close(2))["state"] == "closed"
        assert (await process.settlement(0))["state"] == "settled"
        assert kernel.WaitForSingleObject(observed, 0) == 0
        with pytest.raises(HarnessProcessError, match=r"^Native child identity is unavailable\.$"):
            process.native_identity()
    finally:
        if observed:
            assert kernel.CloseHandle(observed)
        assert (await process.close(2))["state"] == "closed"


def test_unspawned_native_identity_denies_with_only_a_safe_error():
    process = ManagedHarnessProcess()
    with pytest.raises(HarnessProcessError) as denied:
        process.native_identity()
    assert denied.value.args == ("Native child identity is unavailable.",)


async def spawned_status(process):
    async with asyncio.timeout(2):
        while True:
            receipt = await process.request("host.status", {}, "spawn-status", "1", .05)
            if receipt["outcome"] == "committed_reference":
                return receipt
            await asyncio.sleep(.005)


async def test_foreign_and_malformed_readiness_cannot_issue_identity_before_authenticated_ready(tmp_path):
    process = ManagedHarnessProcess()
    start = asyncio.create_task(process.start(config(tmp_path, ready_delay=.5, malformed_ready=True)))
    try:
        status = await spawned_status(process)
        assert not start.done()
        with pytest.raises(HarnessProcessError, match=r"^Native child identity is unavailable\.$"):
            process.native_identity()
        ready = await start
        assert process.native_identity().generation == status["generation"] == ready["generation"]
    finally:
        if not start.done():
            start.cancel()
        await asyncio.gather(start, return_exceptions=True)
        assert (await process.close(2))["state"] == "closed"


async def test_cancelled_start_observer_keeps_owned_child_but_never_issues_identity(tmp_path):
    process = ManagedHarnessProcess()
    start = asyncio.create_task(process.start(config(tmp_path, ready_delay=.5, close_delay=.15)))
    try:
        await spawned_status(process)
        assert not start.done()
        start.cancel()
        with pytest.raises(asyncio.CancelledError):
            await start
        with pytest.raises(HarnessProcessError, match=r"^Native child identity is unavailable\.$"):
            process.native_identity()
        assert (await process.close(.01))["state"] == "blocked"
        assert (await process.settlement(0))["state"] == "pending"
        with pytest.raises(HarnessProcessError, match=r"^Native child identity is unavailable\.$"):
            process.native_identity()
        assert (await process.close(2))["state"] == "closed"
        assert (await process.settlement(0))["state"] == "settled"
    finally:
        if not start.done():
            start.cancel()
        await asyncio.gather(start, return_exceptions=True)
        assert (await process.close(2))["state"] == "closed"


@pytest.mark.parametrize("fault", [{"exit": True}, {"bad_frame": "json"}])
async def test_process_death_or_protocol_failure_revokes_identity_without_false_clean_close(tmp_path, fault):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path))
    try:
        identity = process.native_identity()
        receipt = await process.request("session.get", fault, "fault", "1", 2)
        assert receipt["outcome"] == "uncertain_after_disconnect"
        with pytest.raises(HarnessProcessError, match=r"^Native child identity is unavailable\.$"):
            process.native_identity()
        assert (await process.settlement(2))["state"] == "settled"
        assert (await process.close(2))["state"] == "blocked"
        assert identity.generation == receipt["generation"]
    finally:
        await process.close(2)
        assert (await process.settlement(2))["state"] == "settled"


async def test_authenticated_policy_blocked_child_identity_grants_no_extra_fields(tmp_path):
    process = ManagedHarnessProcess()
    ready = await process.start(config(tmp_path, ready_state="policy_blocked"))
    try:
        assert ready["state"] == "policy_blocked"
        assert set(asdict(process.native_identity())) == {
            "pid", "profile_id", "store_id", "generation"}
    finally:
        assert (await process.close(2))["state"] == "closed"


@pytest.mark.parametrize("state", ["closed", "unknown"])
async def test_unknown_or_closed_startup_state_cannot_issue_identity_while_child_is_live(tmp_path, state):
    process = ManagedHarnessProcess()
    ready = await process.start(config(tmp_path, ready_state=state))
    try:
        assert ready["state"] == state
        assert (await process.settlement(0))["state"] == "pending"
        with pytest.raises(HarnessProcessError, match=r"^Native child identity is unavailable\.$"):
            process.native_identity()
    finally:
        assert (await process.close(2))["state"] == "closed"


async def test_public_readiness_mutation_cannot_promote_authenticated_unknown_state(tmp_path):
    process = ManagedHarnessProcess()
    ready = await process.start(config(tmp_path, ready_state="unknown"))
    try:
        assert ready["state"] == "unknown"
        with pytest.raises(HarnessProcessError, match=r"^Native child identity is unavailable\.$"):
            process.native_identity()
        ready["state"] = "ready"
        with pytest.raises(HarnessProcessError, match=r"^Native child identity is unavailable\.$"):
            process.native_identity()
    finally:
        assert (await process.close(2))["state"] == "closed"


async def test_mutating_public_readiness_fields_cannot_change_authenticated_native_identity(tmp_path):
    process = ManagedHarnessProcess()
    ready = await process.start(config(tmp_path))
    try:
        identity = process.native_identity()
        assert set(ready) == {"protocol", "profile_id", "store_id", "generation", "kind", "state"}
        assert ready["profile_id"] == "synthetic-profile"
        assert ready["store_id"] == "synthetic-runtime"
        assert ready["generation"] == identity.generation
        ready.update(protocol="foreign-protocol", profile_id="foreign-profile",
            store_id="foreign-store", generation="foreign-generation", state="closed")
        assert process.native_identity() == identity
        ready.clear()
        assert process.native_identity() == identity
    finally:
        assert (await process.close(2))["state"] == "closed"
