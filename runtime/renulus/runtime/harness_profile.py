# SPDX-License-Identifier: MIT
"""Prepare an explicitly owned Harness profile without opening either database."""
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from ..harness_contracts import CONTRACT_VERSION, OPENCODE_SOURCE, PairedStoreManifest


def prepare_harness_profile(owned_root: Path, *, profile_id: str, domain_store_id: str,
                            runtime_store_id: str, domain_path: str) -> PairedStoreManifest:
    """Initialize a prepared selection; validation/activation belong to the host."""
    if not isinstance(owned_root, Path) or not owned_root.is_absolute():
        raise ValueError("Profile root must be an explicit absolute Path")
    manifest = PairedStoreManifest.model_validate({
        "contract_version": CONTRACT_VERSION, "profile_id": profile_id,
        "snapshot_generation": 1, "cohort_source": OPENCODE_SOURCE, "state": "prepared",
        "domain_store": {
            "store_id": domain_store_id, "engine": "renulus-sqlite", "schema_version": 2,
            "generation": 1, "path": domain_path, "validation": "pending",
        },
        "runtime_store": {
            "store_id": runtime_store_id,
            "engine": {"name": "opencode", "version": "2.0.26", "source_commit": OPENCODE_SOURCE},
            "schema_version": "source:" + OPENCODE_SOURCE, "generation": 1,
            "path": "state/harness/opencode.sqlite", "validation": "pending",
        },
    })
    domain_location = manifest.domain_store.path.casefold()
    if domain_location in {"state", "state/harness"} or domain_location.startswith("state/harness/"):
        raise ValueError("Domain store path is reserved for the harness manifest and ownership controls")
    destination = owned_root / "state/harness/manifest.json"
    for path in (owned_root, destination, owned_root / manifest.domain_store.path,
                 owned_root / manifest.runtime_store.path):
        if path.resolve() != path:
            raise ValueError("Profile/store paths must not redirect through links or traversal")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=destination.parent, prefix=".manifest-", suffix=".tmp",
                            delete=False) as staged:
        staged_path = Path(staged.name)
        try:
            staged.write((manifest.model_dump_json(indent=2) + "\n").encode("utf-8"))
            staged.flush()
            os.fsync(staged.fileno())
        except BaseException:
            staged.close()
            staged_path.unlink(missing_ok=True)
            raise
    try:
        try:
            # Same-directory, create-if-absent publication: never replace an owner.
            os.link(staged_path, destination)
        except FileExistsError:
            existing = PairedStoreManifest.model_validate_json(destination.read_bytes())
            if existing != manifest:
                raise ValueError("Existing manifest is active or differs from the prepared selection")
            return existing
        return manifest
    finally:
        staged_path.unlink(missing_ok=True)
