# SPDX-License-Identifier: MIT
"""Public canonical writer barrier used while paired-store IPC settles."""
from pathlib import Path
import sys
import asyncio
import json

import pytest

from renulus.storage import Database
from renulus.runtime.harness_profile import prepare_harness_profile


def test_initial_selection_can_reopen_active_stores_without_repreparing(tmp_path):
    from renulus.runtime.harness_profile import load_harness_profile
    root = tmp_path / "profile"
    options = dict(profile_id="synthetic-profile", domain_store_id="synthetic-domain",
                   runtime_store_id="synthetic-runtime", domain_path="domain/renulus.sqlite3")
    manifest = prepare_harness_profile(root, **options).model_dump(mode="json")
    manifest.update(state="active")
    manifest["domain_store"]["validation"] = "valid"
    manifest["runtime_store"]["validation"] = "valid"
    import json
    file = root / "state/harness/manifest.json"
    file.write_text(json.dumps(manifest), encoding="utf-8")
    original = file.read_bytes()
    assert load_harness_profile(root, **options).state == "active"
    assert file.read_bytes() == original
    with pytest.raises(ValueError):
        load_harness_profile(root, **{**options, "domain_store_id": "wrong-store"})


def test_activation_seals_new_canonical_writers_without_holding_a_transaction(tmp_path):
    db = Database(tmp_path / "domain.sqlite3")
    with db.quiesce_writes():
        assert db.fetch_one("PRAGMA user_version")["user_version"] == 2
        with pytest.raises(RuntimeError, match="quiescence"):
            db.execute("INSERT INTO preferences VALUES('blocked','value','2026-10-11')")
    db.execute("INSERT INTO preferences VALUES('accepted','value','2026-10-11')")
    assert db.fetch_one("SELECT value FROM preferences WHERE key='accepted'")["value"] == "value"


def test_activation_requires_admitted_writers_to_settle_before_sealing(tmp_path):
    db = Database(tmp_path / "domain.sqlite3")
    with db.transaction() as conn:
        conn.execute("INSERT INTO preferences VALUES('before','value','2026-10-11')")
        with pytest.raises(RuntimeError, match="settled writers"):
            with db.quiesce_writes():
                pytest.fail("An admitted writer cannot be overtaken")
    with db.quiesce_writes():
        with pytest.raises(RuntimeError, match="quiescence"):
            with db.quiesce_writes():
                pytest.fail("A second selection cannot acquire the barrier")
    assert db.fetch_one("SELECT value FROM preferences WHERE key='before'")["value"] == "value"


def test_fixed_interruption_writer_cannot_bypass_initial_activation(tmp_path):
    from renulus.storage.publication import record_interrupted_conversation
    db = Database(tmp_path / "domain.sqlite3")
    db.apply_migration("synthetic-owner", "CREATE TABLE learn_threads(id TEXT PRIMARY KEY);")
    with db.quiesce_writes():
        with pytest.raises(RuntimeError, match="quiescence"):
            record_interrupted_conversation(db, "learning", "absent-thread", "absent-run")


async def test_process_death_settles_ownership_without_claiming_clean_close(tmp_path):
    from renulus.runtime.harness_process import HarnessProcessConfig, ManagedHarnessProcess
    process = ManagedHarnessProcess()
    await process.start(HarnessProcessConfig(node_executable=Path(sys.executable),
        host_entry=Path(__file__).parent / "fixtures/harness_child.py",
        profile_root=tmp_path / "profile", profile_id="synthetic-profile",
        store_id="synthetic-runtime", domain_store_id="synthetic-domain",
        domain_path="domain/renulus.sqlite3"))
    try:
        assert (await process.settlement(0))["state"] == "pending"
        response = await process.request("session.get", {"exit": True}, "crash", "1", 2)
        assert response["outcome"] == "uncertain_after_disconnect"
        assert await process.settlement(2) == {"state": "settled", "exit_code": 23}
        assert (await process.close(1))["outcome"] == "uncertain_after_disconnect"
    finally:
        await process.close(2)


async def test_cancelled_activation_observer_retains_writer_lease_until_command_settles(tmp_path):
    from renulus.runtime.harness_activation import HarnessProfileActivation
    from renulus.runtime.harness_process import HarnessProcessConfig
    config = HarnessProcessConfig(node_executable=Path(sys.executable),
        host_entry=Path(__file__).parent / "fixtures/harness_child.py",
        profile_root=tmp_path / "profile", profile_id="synthetic-profile",
        store_id="synthetic-runtime", domain_store_id="synthetic-domain",
        domain_path="domain/renulus.sqlite3")
    db = Database(config.profile_root / config.domain_path)
    entered, release = asyncio.Event(), asyncio.Event()

    class SyntheticActivationCommand:
        # Explicit scripted transport delay; actual store/SDK activation has a
        # separate end-to-end receipt. No fabricated engine proof here.
        async def request(self, command, payload, operation_id, attempt_id, timeout):
            assert command == "host.stores.activate" and payload == {}
            entered.set()
            await release.wait()
            file = config.profile_root / "state/harness/manifest.json"
            manifest = json.loads(file.read_text(encoding="utf-8"))
            manifest["state"] = "active"
            manifest["domain_store"]["validation"] = "valid"
            manifest["runtime_store"]["validation"] = "valid"
            file.write_text(json.dumps(manifest), encoding="utf-8")
            return {"outcome": "committed_reference", "result": manifest}

    owner = HarnessProfileActivation(db, SyntheticActivationCommand(), config)
    observer = asyncio.create_task(owner.activate())
    await entered.wait()
    observer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await observer
    assert owner.status()["state"] == "validating"
    with pytest.raises(RuntimeError, match="quiescence"):
        db.execute("INSERT INTO preferences VALUES('blocked','value','2026-10-11')")
    release.set()
    assert (await owner.activate()).state == "active"
    db.execute("INSERT INTO preferences VALUES('after','value','2026-10-11')")
