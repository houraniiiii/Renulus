# SPDX-License-Identifier: MIT
"""One owned initial activation, with logical domain admission across IPC."""
import asyncio
from pathlib import Path
from uuid import uuid4

from ..harness_contracts import OPENCODE_SOURCE, validate_paired_store_manifest
from .harness_profile import load_harness_profile


class HarnessActivationError(RuntimeError):
    pass


class HarnessProfileActivation:
    """Observers may leave; this owner retains the selection/writer lease.

    Use after domain assembly and before starting producers. Native activation
    separately seals admission and verifies actual runtime quiescence. Neither
    side holds a canonical transaction or physical thread lock across IPC.
    """
    def __init__(self, database, process, config):
        self.database, self.process, self.config = database, process, config
        self._task = None
        self._state = "prepared"
        self._error = None

    def status(self):
        return {"state": self._state, "error_code": self._error}

    async def activate(self):
        if self._task is None:
            self._task = asyncio.create_task(self._select(), name="renulus-harness-store-activation")
            self._task.add_done_callback(lambda task: None if task.cancelled() else task.exception())
        return await asyncio.shield(self._task)

    def _bind_domain(self, selection):
        if self.database.path != (self.config.profile_root / selection.domain_store.path).resolve():
            raise HarnessActivationError("harness_domain_path_mismatch")
        schema = Path(__file__).parent / "migrations/003-harness-stores.sql"
        self.database.apply_migration("runtime-003-harness-stores", schema.read_text(encoding="utf-8"))
        expected = (selection.profile_id, selection.domain_store.store_id,
                    selection.snapshot_generation, OPENCODE_SOURCE)
        with self.database.transaction() as conn:
            if conn.execute("PRAGMA user_version").fetchone()[0] != 2:
                raise HarnessActivationError("harness_domain_schema_mismatch")
            current = conn.execute("SELECT profile_id,store_id,snapshot_generation,cohort_source "
                                   "FROM harness_store_identity WHERE singleton=1").fetchone()
            if current is not None and tuple(current) != expected:
                raise HarnessActivationError("harness_store_identity_mismatch")
            if current is None:
                if selection.state == "active":
                    raise HarnessActivationError("harness_store_identity_missing")
                conn.execute("INSERT INTO harness_store_identity VALUES(1,?,?,?,?)", expected)

    async def _select(self):
        self._state = "validating"
        try:
            selection = load_harness_profile(self.config.profile_root,
                profile_id=self.config.profile_id, domain_store_id=self.config.domain_store_id,
                runtime_store_id=self.config.store_id, domain_path=self.config.domain_path)
            self._bind_domain(selection)
            with self.database.quiesce_writes():
                response = await self.process.request("host.stores.activate", {},
                    "activation-" + uuid4().hex, "initial-selection", 5)
                while response["outcome"] == "accepted_pending":
                    await asyncio.sleep(0.02)
                    response = await self.process.query_result(response["request_id"])
                if response["outcome"] == "uncertain_after_disconnect":
                    self._state = "settlement_pending"
                    # An observer losing its reply is not permission to release
                    # canonical writers while the native owner may still work.
                    while True:
                        if (await self.process.close(1))["state"] == "closed":
                            break
                        if (await self.process.settlement(1))["state"] == "settled":
                            break
                if response["outcome"] != "committed_reference":
                    code = response.get("error", {}).get("code", response["outcome"])
                    raise HarnessActivationError("harness_store_activation_failed:" + code)
                selected = validate_paired_store_manifest(response["result"],
                    profile_id=self.config.profile_id, domain_store_id=self.config.domain_store_id,
                    runtime_store_id=self.config.store_id, snapshot_generation=1)
                stored = load_harness_profile(self.config.profile_root,
                    profile_id=self.config.profile_id, domain_store_id=self.config.domain_store_id,
                    runtime_store_id=self.config.store_id, domain_path=self.config.domain_path)
                if stored != selected:
                    raise HarnessActivationError("harness_selection_changed")
            self._state = "active"
            return selected
        except Exception as error:
            self._state, self._error = "failed", "harness_store_activation_failed"
            raise HarnessActivationError(self._error) from error
