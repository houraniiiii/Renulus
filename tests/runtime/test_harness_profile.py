# SPDX-License-Identifier: MIT
"""Public prepared-profile writer checks using only owned synthetic state."""
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest

from renulus.runtime.harness_profile import prepare_harness_profile


SCRATCH = Path("C:/Renulus/scratch/oc-foundations/contracts").resolve()
SELECTION = dict(profile_id="synthetic-profile", domain_store_id="synthetic-domain-store",
                 runtime_store_id="synthetic-runtime-store", domain_path="domain/renulus.sqlite3")


@pytest.fixture
def owned_root():
    root = SCRATCH / ("profile-" + uuid4().hex)
    assert root.is_relative_to(SCRATCH)
    return root


def test_profile_prepares_both_stores_before_any_sdk_database_write(owned_root):
    manifest = prepare_harness_profile(owned_root, **SELECTION)
    document = json.loads((owned_root / "state/harness/manifest.json").read_text("utf-8"))
    assert document["state"] == "prepared"
    assert document["profile_id"] == "synthetic-profile"
    assert document["snapshot_generation"] == 1
    assert document["domain_store"] == {
        "store_id": "synthetic-domain-store", "engine": "renulus-sqlite",
        "schema_version": 2, "generation": 1, "path": "domain/renulus.sqlite3",
        "validation": "pending",
    }
    assert document["runtime_store"]["path"] == "state/harness/opencode.sqlite"
    assert document["runtime_store"]["validation"] == "pending"
    assert manifest.runtime_store.store_id == "synthetic-runtime-store"
    assert not (owned_root / "state/harness/opencode.sqlite").exists()
    assert not (owned_root / "domain/renulus.sqlite3").exists()


@pytest.mark.parametrize("change", ["identical", "profile", "domain", "runtime", "path",
                                    "active", "schema", "malformed"])
def test_preparation_preserves_every_existing_manifest_without_overwriting(owned_root, change):
    prepare_harness_profile(owned_root, **SELECTION)
    path = owned_root / "state/harness/manifest.json"
    existing = json.loads(path.read_text("utf-8"))
    if change == "profile":
        existing["profile_id"] = "other-profile"
    elif change in ("domain", "runtime"):
        existing[change + "_store"]["store_id"] = "other-store"
    elif change == "path":
        existing["domain_store"]["path"] = "other/domain.sqlite3"
    elif change == "active":
        existing["state"] = "active"
        existing["domain_store"]["validation"] = "valid"
        existing["runtime_store"]["validation"] = "valid"
    elif change == "schema":
        existing["domain_store"]["schema_version"] = 99
    original = b"incomplete{" if change == "malformed" else json.dumps(existing).encode("utf-8")
    path.write_bytes(original)
    if change == "identical":
        assert prepare_harness_profile(owned_root, **SELECTION).state == "prepared"
    else:
        with pytest.raises(ValueError):
            prepare_harness_profile(owned_root, **SELECTION)
    assert path.read_bytes() == original


def test_competing_initializers_publish_one_complete_selection(owned_root):
    start = Barrier(16)

    def prepare(index):
        start.wait(timeout=15)
        try:
            return prepare_harness_profile(
                owned_root, **{**SELECTION, "profile_id": f"contender-{index}"}).profile_id
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=16) as workers:
        results = list(workers.map(prepare, range(16)))
    stored = json.loads((owned_root / "state/harness/manifest.json").read_text("utf-8"))
    assert [result for result in results if result is not None] == [stored["profile_id"]]
    assert stored["state"] == "prepared"
    assert sorted(path.name for path in (owned_root / "state/harness").iterdir()) == [
        "manifest.json"]


def test_profile_root_must_be_explicit_and_absolute_before_writing(owned_root, monkeypatch):
    owned_root.mkdir(parents=True)
    monkeypatch.chdir(owned_root)
    with pytest.raises(ValueError, match="absolute"):
        prepare_harness_profile(Path("relative-profile"), **SELECTION)
    assert list(owned_root.iterdir()) == []


def test_redirected_state_directory_is_rejected_before_touching_its_target(owned_root):
    owned_root.mkdir(parents=True)
    other = SCRATCH / ("other-" + uuid4().hex)
    other.mkdir()
    redirect = owned_root / "state"
    if os.name == "nt":
        subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(redirect), str(other)],
                       check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        redirect.symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError, match="redirect"):
        prepare_harness_profile(owned_root, **SELECTION)
    assert list(other.iterdir()) == []


@pytest.mark.parametrize("path", ["state/harness/manifest.json", "STATE/HARNESS/MANIFEST.JSON",
                                  "state/harness/manifest.json/child.db"])
def test_domain_store_cannot_alias_manifest_metadata(owned_root, path):
    with pytest.raises(ValueError, match="manifest"):
        prepare_harness_profile(owned_root, **{**SELECTION, "domain_path": path})
    assert not owned_root.exists()


@pytest.mark.parametrize("path", [
    "state", "state/harness", "state/harness/owner.json", "state/harness/ownership-guard",
    "state/harness/leases/guard", "STATE/HARNESS/other.sqlite", "state/harness/runtime.log",
])
def test_domain_store_cannot_alias_any_harness_operational_path(owned_root, path):
    with pytest.raises(ValueError):
        prepare_harness_profile(owned_root, **{**SELECTION, "domain_path": path})
    assert not owned_root.exists()
