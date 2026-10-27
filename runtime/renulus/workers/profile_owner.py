# SPDX-License-Identifier: MIT
"""Windows lifetime supervisor for the selected Node backend; opens no database.

The existing profile mutex, exact FILETIME identities and kill-on-close job are
held until this process exits. Node receives its one-use launch proof through a
private pipe only after registration in that job. No PID age/TTL reclamation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from renulus.runtime.harness_profile_owner import ProfileOwnerScope, acquire_profile_owner

SELECTOR = ".renulus-backend-selector.json"
RECEIPT = ".renulus-selected-owner.json"


def read_selection(root: Path):
    path = root / SELECTOR
    if not path.exists():
        return None
    if path.is_symlink() or path.stat().st_size > 16384:
        raise ValueError("backend_selector_invalid")
    payload = path.read_bytes()
    value = json.loads(payload)
    keys = {"contract", "profileId", "generation", "authorityEpoch", "writer", "state",
            "generationPath", "manifestSha256", "schemaHash", "cohortHash"}
    if (set(value) != keys or value["contract"] != "renulus-backend-selector/1"
            or value["writer"] not in ("python", "ts") or value["state"] not in ("held", "active")
            or type(value["authorityEpoch"]) is not int or value["authorityEpoch"] < 1):
        raise ValueError("backend_selector_invalid")
    target = (root / value["generationPath"]).resolve()
    if (not target.is_relative_to(root) or target == root
            or target.relative_to(root).as_posix() != value["generationPath"]):
        raise ValueError("backend_generation_unowned")
    for path in (target, *target.parents):
        if path == root:
            break
        if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError("backend_generation_unowned")
    manifest = target / ".renulus-complete-generation.json"
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != value["manifestSha256"]:
        raise ValueError("backend_generation_changed")
    return value, hashlib.sha256(payload).hexdigest(), target


# Node cannot import main (and hence cannot open a writer) before this pipe is
# issued. The proof is consumed by readSelectedOwnerLaunch in host/handoff.ts.
NODE_GATE = """
import { once } from 'node:events';
let bytes = '';
for await (const chunk of process.stdin) {
  bytes += chunk.toString('utf8');
  if (bytes.length > 32768) throw new Error('backend_launch_proof_limit');
  if (bytes.includes('\\n')) break;
}
const proof = JSON.parse(bytes.trim());
globalThis[Symbol.for('renulus.selected-owner.launch')] = proof;
const entry = process.argv[1];
process.argv = [process.argv[0], entry, ...process.argv.slice(2)];
await import((await import('node:url')).pathToFileURL(entry).href);
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("profile", "node", "entrypoint", "profile-id", "domain-store-id", "runtime-store-id"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--initialize-new", action="store_true")
    parser.add_argument("--adopt-legacy", action="store_true")
    parser.add_argument("--maintenance", action="store_true")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root, node, entry = (Path(value) for value in (args.profile, args.node, args.entrypoint))
    if any(not value.is_absolute() or value.resolve() != value for value in (root, node, entry)):
        raise ValueError("backend_absolute_owned_paths_required")
    lease = acquire_profile_owner(ProfileOwnerScope(root, args.profile_id, args.domain_store_id,
        args.runtime_store_id), initialize_new=args.initialize_new, adopt_legacy=args.adopt_legacy)
    selected = read_selection(root)
    if selected is not None and (selected[0]["profileId"] != args.profile_id
            or (not args.maintenance and (selected[0]["state"] != "active" or selected[0]["writer"] != "ts"))):
        raise ValueError("backend_selected_admission_held")
    child_args = args.args[1:] if args.args[:1] == ["--"] else args.args
    environment = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "COMSPEC", "PATHEXT",
        "TEMP", "TMP", "RENULUS_SESSION_TOKEN") if key in os.environ}
    environment.update(PATH=str(node.parent) + os.pathsep + str(Path(sys.executable).parent),
        PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    child = subprocess.Popen([str(node), "--input-type=module", "-e", NODE_GATE, str(entry), *child_args],
        cwd=entry.parent, env=environment, stdin=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        identity = lease.register_native(child.pid, generation="backend-" + lease.generation)
        nonce = secrets.token_hex(32)
        native_receipt = (root / ".renulus-profile-owner.json").read_bytes()
        proof = {"contract": "renulus-selected-writer/1", "profileRoot": str(root),
            "generationRoot": str(selected[2]) if selected else str(root),
            "selectorSha256": selected[1] if selected else None,
            "authorityEpoch": selected[0]["authorityEpoch"] if selected else 0,
            "ownerGeneration": lease.generation,
            "predecessorGeneration": lease.predecessor.previous_generation,
            "ownerReceiptSha256": hashlib.sha256(native_receipt).hexdigest(),
            "nodePid": identity.pid, "nodeCreationFiletime": str(identity.creation_filetime),
            "supervisorPid": lease.python_identity.pid,
            "supervisorCreationFiletime": str(lease.python_identity.creation_filetime),
            "nonceSha256": hashlib.sha256(nonce.encode()).hexdigest()}
        # The same durable MoveFileEx(REPLACE_EXISTING|WRITE_THROUGH) primitive.
        # _publish has a fixed name, so publish this small proof with an explicit
        # sibling temporary and the identical Windows primitive instead.
        temporary = root / (".selected-owner-" + lease.generation + ".tmp")
        with temporary.open("xb") as stream:
            stream.write(json.dumps(proof, sort_keys=True, separators=(",", ":")).encode())
            stream.flush()
            os.fsync(stream.fileno())
        if not lease._kernel.api.MoveFileExW(str(temporary), str(root / RECEIPT), 0x01 | 0x08):
            raise ValueError("backend_owner_proof_publish_failed")
        child.stdin.write((json.dumps({"authority": proof, "nonce": nonce}) + "\n").encode())
        child.stdin.flush()
        child.stdin.close()
        code = child.wait()
        raise SystemExit(code)
    finally:
        if child.poll() is None:
            # Never release the profile job on an uncertain graceful-close result.
            # Process exit closes the existing kill-on-close job and all children.
            child.terminate()
            child.wait(timeout=15)


if __name__ == "__main__":
    main()
