# SPDX-License-Identifier: MIT
"""Immutable launch artifacts through their public seam and owned synthetic files."""
from dataclasses import FrozenInstanceError
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
from threading import Barrier

import pytest

from renulus.runtime.harness_configuration import (
    AttemptPolicy, ChildPolicy, ConnectionReference, ContextPolicy, InputHash, RolePolicy,
)


CANARY = "synthetic-" + "credential-canary-never-in-receipts"


def launch_arguments(**changes):
    return {
        "boot_settings": {"native": {"instructions": ["Synthetic nephrology learning"]},
                          "ipc": {"max_frame_bytes": 1048576}},
        "connection": ConnectionReference(provider="opencode-go",
            credential_reference="synthetic-selected-reference", credential_revision=2),
        "roles": (RolePolicy(purpose="explain", output_tokens=2048),),
        "inputs": (InputHash(kind="build", name="reviewed-native", sha256="a" * 64),),
        "capabilities": ("text", "tools"),
        "context": ContextPolicy(requested_window_tokens=8192, reserve_tokens=256),
        "attempts": AttemptPolicy(foreground_dispatches=4),
        "children": ChildPolicy(),
        **changes,
    }


def test_frozen_launch_reconstructs_boot_without_mutable_aliases():
    from renulus.runtime.harness_launch import FrozenLaunchInputs, finish_spec

    arguments = launch_arguments()
    inputs = FrozenLaunchInputs(**arguments)
    initial_sha = inputs.sha256
    arguments["boot_settings"]["native"]["instructions"][0] = "changed caller data"
    decoded = inputs.boot_settings
    decoded["native"]["instructions"].append("changed decoded data")
    assert inputs.boot_settings["native"]["instructions"] == ["Synthetic nephrology learning"]
    assert inputs.sha256 == initial_sha
    with pytest.raises((FrozenInstanceError, AttributeError)):
        inputs.sha256 = "b" * 64
    spec = finish_spec(inputs, "c" * 64)
    assert spec.connection.selected_model is None
    assert spec.connection.credential_revision == 2
    assert spec.roles[0].output_tokens == 2048
    assert spec.inputs == (*arguments["inputs"], inputs.launch_hash)
    assert inputs.launch_hash == InputHash(kind="artifact", name="launch", sha256=initial_sha)
    assert spec.registry_hash == "c" * 64


def test_saved_launch_reopens_identically_and_role_staging_freezes_a_new_artifact(tmp_path):
    from renulus.runtime.harness_launch import FrozenLaunchInputs, LaunchArtifactStore, finish_spec

    inputs = FrozenLaunchInputs(**launch_arguments())
    roots = dict(artifact_root=tmp_path / "artifacts", live_root=tmp_path / "live",
                 candidate_root=tmp_path / "candidates")
    store = LaunchArtifactStore(**roots)
    reference = store.save(inputs)
    assert store.save(inputs) == reference
    reopened = LaunchArtifactStore(**roots).load(reference.sha256)
    assert reopened == inputs
    assert reopened.boot_settings == launch_arguments()["boot_settings"]
    spec = finish_spec(reopened, "c" * 64)
    changed = spec.model_copy(update={"roles": (RolePolicy(purpose="explain", output_tokens=1024),)})
    proposed_inputs = FrozenLaunchInputs(boot_settings=reopened.boot_settings,
        connection=changed.connection, roles=changed.roles,
        inputs=tuple(item for item in changed.inputs
            if not (item.kind == "artifact" and item.name == "launch")),
        capabilities=changed.capabilities, context=changed.context,
        attempts=changed.attempts, children=changed.children)
    proposed_reference = store.save(proposed_inputs)
    proposed = finish_spec(store.load(proposed_reference.sha256), changed.registry_hash)
    assert proposed.roles == changed.roles
    assert proposed_reference.sha256 != reference.sha256
    assert proposed.inputs == (*spec.inputs[:-1], proposed_reference)
    assert store.load(proposed_reference.sha256).boot_settings == reopened.boot_settings
    assert finish_spec(reopened, proposed.registry_hash) != proposed
    assert store.load(reference.sha256).sha256 == inputs.sha256
    assert sorted(path.name for path in roots["artifact_root"].iterdir()) == sorted(
        [reference.sha256 + ".json", proposed_reference.sha256 + ".json"])
    assert not roots["live_root"].exists() and not roots["candidate_root"].exists()


@pytest.mark.parametrize("case", ["api-key", "nested-token", "authorization", "url-userinfo", "identity"])
def test_credentials_and_process_identity_cannot_be_frozen(case, caplog):
    from renulus.runtime.harness_launch import FrozenLaunchInputs, HarnessLaunchError

    boot = {"apiKey": CANARY} if case == "api-key" else {"native": {"refresh_token": CANARY}}
    if case == "authorization":
        boot = {"native": {"headers": {"accept": "Bearer " + CANARY}}}
    elif case == "url-userinfo":
        boot = {"native": {"endpoint": "https://synthetic:" + CANARY + "@invalid.example/"}}
    elif case == "identity":
        boot = {"root": "synthetic-owned-root"}
    with pytest.raises(HarnessLaunchError) as denied:
        FrozenLaunchInputs(**launch_arguments(boot_settings=boot))
    assert CANARY not in str(denied.value) and CANARY not in caplog.text
    assert denied.value.code in {"launch_credentials_forbidden", "launch_inputs_invalid"}


@pytest.mark.parametrize("case", ["tuple", "non-object", "non-string-key", "object", "nan",
    "unsafe-integer", "surrogate", "cyclic", "deep", "oversized", "copied-policy", "launch-input"])
def test_invalid_or_unbounded_launch_data_fails_with_safe_errors(case):
    from renulus.runtime.harness_launch import FrozenLaunchInputs, HarnessLaunchError

    boot = {"value": (1, 2)}
    changes = {}
    if case == "non-object":
        boot = []
    elif case == "non-string-key":
        boot = {1: "value"}
    elif case == "object":
        boot = {"value": object()}
    elif case == "nan":
        boot = {"value": float("nan")}
    elif case == "unsafe-integer":
        boot = {"value": 9007199254740992}
    elif case == "surrogate":
        boot = {"value": chr(0xd800)}
    elif case == "cyclic":
        boot = {}
        boot["value"] = boot
    elif case == "deep":
        boot = {}
        for _ in range(20):
            boot = {"value": boot}
    elif case == "oversized":
        boot = {"value": "x" * 262144}
    elif case == "copied-policy":
        boot = {}
        changes["roles"] = (RolePolicy(purpose="explain").model_copy(update={"output_tokens": True}),)
    elif case == "launch-input":
        boot = {}
        changes["inputs"] = (InputHash(kind="artifact", name="launch", sha256="a" * 64),)
    with pytest.raises(HarnessLaunchError) as denied:
        FrozenLaunchInputs(**launch_arguments(boot_settings=boot, **changes))
    assert denied.value.code in {"launch_inputs_invalid", "launch_too_large"}
    assert str(denied.value) == "The launch artifact is unavailable or invalid."


@pytest.mark.parametrize("case", ["tampered", "unknown-field", "unknown-version", "boolean-version",
    "unknown-policy", "duplicate-key", "malformed", "utf8", "noncanonical", "oversized"])
def test_load_rejects_tampered_or_unrecognized_artifact_bytes(tmp_path, case):
    from renulus.runtime.harness_launch import FrozenLaunchInputs, HarnessLaunchError, LaunchArtifactStore

    root = tmp_path / "artifacts"
    store = LaunchArtifactStore(root, live_root=tmp_path / "live", candidate_root=tmp_path / "candidates")
    reference = store.save(FrozenLaunchInputs(**launch_arguments()))
    path = root / (reference.sha256 + ".json")
    original = path.read_bytes()
    document = json.loads(original)
    if case == "tampered":
        document["boot_settings"]["native"]["instructions"] = ["changed persisted launch"]
    elif case == "unknown-field":
        document["unreviewed"] = True
    elif case == "unknown-version":
        document["version"] = 2
    elif case == "boolean-version":
        document["version"] = True
    elif case == "unknown-policy":
        document["policy"]["unreviewed"] = True
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    if case == "duplicate-key":
        payload = b'{"version":2,' + original[1:]
    elif case == "malformed":
        payload = b'{"version":'
    elif case == "utf8":
        payload = b'\xff'
    elif case == "noncanonical":
        payload = original + b'\n'
    elif case == "oversized":
        payload = b' ' * 262145
    digest = reference.sha256 if case == "tampered" else hashlib.sha256(payload).hexdigest()
    path = root / (digest + ".json")
    path.write_bytes(payload)
    with pytest.raises(HarnessLaunchError) as denied:
        store.load(digest)
    assert denied.value.code in {"launch_artifact_invalid", "launch_too_large"}
    assert path.read_bytes() == payload


@pytest.mark.parametrize("case", ["relative-artifact", "relative-live", "relative-candidate",
    "same-live", "inside-live", "around-live", "same-candidate", "inside-candidate",
    "around-candidate", "traversal", "string-root", "alternate-stream"])
def test_artifact_root_must_be_explicit_and_disjoint_from_runtime_stores(tmp_path, case):
    from renulus.runtime.harness_launch import HarnessLaunchError, LaunchArtifactStore

    roots = dict(artifact_root=tmp_path / "artifacts", live_root=tmp_path / "live",
                 candidate_root=tmp_path / "candidates")
    if case.startswith("relative-"):
        roots[case.removeprefix("relative-") + "_root"] = Path("relative")
    elif case.endswith("live") or case.endswith("candidate"):
        protected = roots["live_root" if case.endswith("live") else "candidate_root"]
        roots["artifact_root"] = (protected if case.startswith("same") else
            protected / "artifacts" if case.startswith("inside") else protected.parent)
    elif case == "traversal":
        roots["artifact_root"] = tmp_path / "outside" / ".." / "artifacts"
    elif case == "string-root":
        roots["artifact_root"] = str(roots["artifact_root"])
    elif case == "alternate-stream":
        roots["artifact_root"] = tmp_path / "artifacts:stream"
    with pytest.raises(HarnessLaunchError) as denied:
        LaunchArtifactStore(**roots)
    assert denied.value.code == "launch_path_invalid"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("case", ["copied-unknown", "incomplete-model"])
def test_typed_policy_must_be_validated_before_snapshot_serialization(case):
    from renulus.runtime.harness_launch import FrozenLaunchInputs

    arguments = launch_arguments()
    if case == "copied-unknown":
        arguments["roles"] = (arguments["roles"][0].model_copy(update={"unreviewed": True}),)
    else:
        arguments["connection"] = ConnectionReference.model_construct()
    with pytest.raises(Exception) as denied:
        FrozenLaunchInputs(**arguments)
    assert type(denied.value).__name__ == "HarnessLaunchError"
    assert denied.value.code == "launch_inputs_invalid"


@pytest.mark.parametrize("digest", ["../outside", "A" * 64, "a" * 63, "a" * 65, None, 1])
def test_load_rejects_noncanonical_digest_without_creating_files(tmp_path, digest):
    from renulus.runtime.harness_launch import HarnessLaunchError, LaunchArtifactStore

    store = LaunchArtifactStore(tmp_path / "artifacts", live_root=tmp_path / "live",
                               candidate_root=tmp_path / "candidates")
    with pytest.raises(HarnessLaunchError) as denied:
        store.load(digest)
    assert denied.value.code == "launch_artifact_invalid"
    assert list(tmp_path.iterdir()) == []


def make_junction(link, target):
    # Explicit owned Windows paths; no native profile or external directory.
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                   check=True, capture_output=True)


@pytest.mark.parametrize("root_name", ["artifact_root", "live_root", "candidate_root"])
def test_junction_roots_are_rejected_at_construction(tmp_path, root_name):
    from renulus.runtime.harness_launch import HarnessLaunchError, LaunchArtifactStore

    target = tmp_path / "owned-target"
    target.mkdir()
    roots = dict(artifact_root=tmp_path / "artifacts", live_root=tmp_path / "live",
                 candidate_root=tmp_path / "candidates")
    make_junction(roots[root_name], target)
    with pytest.raises(HarnessLaunchError) as denied:
        LaunchArtifactStore(**roots)
    assert denied.value.code == "launch_path_invalid"
    assert list(target.iterdir()) == []


@pytest.mark.parametrize("operation", ["save", "load"])
def test_root_replacement_with_junction_is_rejected_before_io(tmp_path, operation):
    from renulus.runtime.harness_launch import FrozenLaunchInputs, HarnessLaunchError, LaunchArtifactStore

    root = tmp_path / "artifacts"
    store = LaunchArtifactStore(root, live_root=tmp_path / "live", candidate_root=tmp_path / "candidates")
    inputs = FrozenLaunchInputs(**launch_arguments())
    store.save(inputs)
    target = tmp_path / "retained-owned-artifacts"
    root.rename(target)
    make_junction(root, target)
    before = {path.name: path.read_bytes() for path in target.iterdir()}
    with pytest.raises(HarnessLaunchError) as denied:
        store.save(inputs) if operation == "save" else store.load(inputs.sha256)
    assert denied.value.code == "launch_path_invalid"
    assert {path.name: path.read_bytes() for path in target.iterdir()} == before


@pytest.mark.parametrize("operation", ["save", "load"])
def test_aliased_artifact_file_is_rejected_and_never_replaced(tmp_path, operation):
    from renulus.runtime.harness_launch import FrozenLaunchInputs, HarnessLaunchError, LaunchArtifactStore

    root = tmp_path / "artifacts"
    store = LaunchArtifactStore(root, live_root=tmp_path / "live", candidate_root=tmp_path / "candidates")
    inputs = FrozenLaunchInputs(**launch_arguments())
    store.save(inputs)
    path = root / (inputs.sha256 + ".json")
    external_alias = tmp_path / "owned-alias.json"
    os.link(path, external_alias)
    before = path.read_bytes()
    with pytest.raises(HarnessLaunchError) as denied:
        store.save(inputs) if operation == "save" else store.load(inputs.sha256)
    assert denied.value.code == "launch_artifact_invalid"
    assert path.read_bytes() == external_alias.read_bytes() == before
    assert list(root.iterdir()) == [path]


@pytest.mark.parametrize("operation", ["registry-hash", "registry-type", "finish-inputs", "save-inputs"])
def test_public_boundaries_deny_invalid_arguments_without_exposing_values(tmp_path, operation, caplog):
    from renulus.runtime.harness_launch import FrozenLaunchInputs, LaunchArtifactStore, finish_spec

    inputs = FrozenLaunchInputs(**launch_arguments())
    store = LaunchArtifactStore(tmp_path / "artifacts", live_root=tmp_path / "live",
                               candidate_root=tmp_path / "candidates")
    with pytest.raises(Exception) as denied:
        if operation == "registry-hash":
            finish_spec(inputs, CANARY)
        elif operation == "registry-type":
            finish_spec(inputs, 1)
        elif operation == "finish-inputs":
            finish_spec(None, "c" * 64)
        else:
            store.save(None)
    # The first assertion prints only the type if a raw validator exception leaks.
    assert type(denied.value).__name__ == "HarnessLaunchError"
    assert str(denied.value) == "The launch artifact is unavailable or invalid."
    assert denied.value.code in {"launch_spec_invalid", "launch_inputs_invalid"}
    assert CANARY not in caplog.text
    assert list(tmp_path.iterdir()) == []


def test_concurrent_saves_publish_one_complete_artifact_without_temporary_files(tmp_path):
    from renulus.runtime.harness_launch import FrozenLaunchInputs, LaunchArtifactStore

    inputs = FrozenLaunchInputs(**launch_arguments())
    roots = dict(artifact_root=tmp_path / "artifacts", live_root=tmp_path / "live",
                 candidate_root=tmp_path / "candidates")
    ready = Barrier(8)

    def save_and_reopen(_index):
        store = LaunchArtifactStore(**roots)
        ready.wait(timeout=10)
        reference = store.save(inputs)
        return reference, store.load(reference.sha256).boot_settings

    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(save_and_reopen, range(8)))
    assert results == [(inputs.launch_hash, launch_arguments()["boot_settings"])] * 8
    assert sorted(path.name for path in roots["artifact_root"].iterdir()) == [inputs.sha256 + ".json"]
    assert not roots["live_root"].exists() and not roots["candidate_root"].exists()


def test_corrupt_existing_artifact_is_preserved_and_missing_artifact_fails_closed(tmp_path):
    from renulus.runtime.harness_launch import FrozenLaunchInputs, HarnessLaunchError, LaunchArtifactStore

    inputs = FrozenLaunchInputs(**launch_arguments())
    root = tmp_path / "artifacts"
    store = LaunchArtifactStore(root, live_root=tmp_path / "live", candidate_root=tmp_path / "candidates")
    with pytest.raises(HarnessLaunchError) as missing:
        store.load(inputs.sha256)
    assert missing.value.code == "launch_artifact_invalid"
    store.save(inputs)
    path = root / (inputs.sha256 + ".json")
    path.write_bytes(b"changed synthetic artifact")
    with pytest.raises(HarnessLaunchError) as corrupt:
        store.save(inputs)
    assert corrupt.value.code == "launch_artifact_invalid"
    assert path.read_bytes() == b"changed synthetic artifact"
    assert list(root.iterdir()) == [path]


def test_canonical_unicode_snapshot_ignores_object_order_and_preserves_array_order(tmp_path):
    from renulus.runtime.harness_launch import FrozenLaunchInputs, LaunchArtifactStore

    boot = {"z": ["renal – α", 2], "a": {"enabled": True, "optional": None, "ratio": 1.5}}
    first = FrozenLaunchInputs(**launch_arguments(boot_settings=boot))
    equivalent = FrozenLaunchInputs(**launch_arguments(boot_settings={"a": {"ratio": 1.5,
        "optional": None, "enabled": True}, "z": ["renal – α", 2]}))
    assert equivalent.sha256 == first.sha256
    reordered = FrozenLaunchInputs(**launch_arguments(boot_settings={**boot, "z": [2, "renal – α"]}))
    assert reordered.sha256 != first.sha256
    root = tmp_path / "artifacts"
    store = LaunchArtifactStore(root, live_root=tmp_path / "live", candidate_root=tmp_path / "candidates")
    reference = store.save(first)
    payload = (root / (reference.sha256 + ".json")).read_bytes()
    assert "renal – α".encode("utf-8") in payload
    assert hashlib.sha256(payload).hexdigest() == reference.sha256
    assert store.load(reference.sha256).boot_settings == boot


@pytest.mark.parametrize("case", ["duplicate-roles", "duplicate-inputs", "duplicate-capabilities", "foreign-role-model"])
def test_launch_policy_keeps_shared_configuration_invariants(case):
    from renulus.runtime.harness_launch import FrozenLaunchInputs, HarnessLaunchError

    arguments = launch_arguments()
    if case == "duplicate-roles":
        arguments["roles"] *= 2
    elif case == "duplicate-inputs":
        arguments["inputs"] *= 2
    elif case == "duplicate-capabilities":
        arguments["capabilities"] = ("text", "text")
    else:
        arguments["roles"] = (RolePolicy(purpose="explain", model_id="gpt-6.1-sol"),)
    with pytest.raises(HarnessLaunchError) as denied:
        FrozenLaunchInputs(**arguments)
    assert denied.value.code == "launch_inputs_invalid"
