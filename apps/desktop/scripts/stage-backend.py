"""Developer-only portable Windows payload; never copy runtime profile state."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

DESKTOP = Path(__file__).resolve().parents[1]
PYTHON_VERSION = "3.14.4"
PYTHON_SHA256 = "cda80a9b1e75c0f1b4f9872ca1b417f0d19bce32facc811aea9180e70fad5fb9"
sys.dont_write_bytecode = True

def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()

def snapshot(repo: Path, ref: str, destination: Path) -> None:
    """Adapt Hermes scripts/bundles/payload.py snapshot to an admitted allowlist."""
    admitted = ["runtime/renulus", "content/packs", "content/LICENSE", "LICENSE",
                "licenses", "upstream/hermes", "packaging/runtime", "uv.lock",
                "pyproject.toml", "docs/SOURCES.md"]
    admitted = [item for item in admitted if subprocess.check_output(
        ["git", "ls-tree", "--name-only", ref, "--", item], cwd=repo).strip()]
    exclusions = [f":(exclude)upstream/hermes/{name}" for name in
                  ("tests", "tests-js", "website", "evals", ".github", "nix", "docker",
                   "apps", "ui-tui", "web", "scripts", "docs")]
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix="source-archive-") as temp:
        archive = Path(temp) / "source.tar"
        subprocess.run(["git", "archive", "--format=tar", "--output", str(archive), ref,
                        "--", *admitted, *exclusions], cwd=repo, check=True)
        with tarfile.open(archive) as source:
            source.extractall(destination, filter="data")

def helper_contract(contract: Path, acquired: Path) -> dict:
    """An acquired manifest cannot redefine the reviewed artifact hashes."""
    reviewed = json.loads(contract.read_text(encoding="utf-8-sig"))
    supplied = json.loads((acquired / "manifest.json").read_text(encoding="utf-8-sig"))
    if reviewed.get("version") != 1 or set(reviewed.get("groups", {})) != {"embedding", "docling", "ocr"}:
        raise ValueError("The reviewed helper contract must contain exactly the selected groups")
    if supplied != reviewed:
        raise ValueError("The acquired helper manifest differs from the reviewed source contract")
    return reviewed

def refresh_snapshot(repo: Path, before: str, after: str, payload: Path) -> None:
    """Refresh only generated public source when the selected wheel lock is unchanged."""
    payload = payload.resolve()
    if not payload.is_relative_to(DESKTOP / "test-results"):
        raise ValueError("A source refresh must stay inside this lane's generated test-results")
    changes = subprocess.check_output(["git", "diff", "--name-only", before, after,
                                      "--", "uv.lock", "pyproject.toml"], cwd=repo, text=True)
    if changes.strip():
        raise ValueError("Dependency changes require a fresh dependency staging run")
    admitted = ("runtime/renulus", "content/packs", "licenses", "upstream/hermes",
                "packaging/runtime", "docs/SOURCES.md", "content/LICENSE", "LICENSE")
    removed = subprocess.check_output(["git", "diff", "--name-only", "--diff-filter=D",
                                      before, after, "--", *admitted], cwd=repo, text=True)
    for name in removed.splitlines():
        target = (payload / name).resolve()
        if not target.is_relative_to(payload):
            raise ValueError("A source deletion escaped the generated payload")
        target.unlink(missing_ok=True)
    snapshot(repo, after, payload)

def apply_runtime_patch(repo: Path, ref: str, payload: Path) -> dict:
    """Adopt an approved runtime-lane diff in the generated payload only."""
    revision = subprocess.check_output(["git", "rev-parse", ref], cwd=repo, text=True).strip()
    paths = subprocess.check_output(["git", "diff", "--name-only", revision + "^",
                                     revision, "--", "runtime/renulus/runtime"],
                                    cwd=repo, text=True).splitlines()
    if not paths or any(not name.startswith("runtime/renulus/runtime/") for name in paths):
        raise ValueError("Only an explicit runtime-lane production patch is admitted")
    patch = subprocess.check_output(["git", "diff", "--binary", revision + "^",
                                     revision, "--", *paths], cwd=repo)
    with tempfile.TemporaryDirectory(dir=payload.parent, prefix="runtime-patch-") as temp:
        scratch = Path(temp)
        for name in paths:
            destination = scratch / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if (payload / name).exists():
                shutil.copyfile(payload / name, destination)
        subprocess.run(["git", "init", "--quiet"], cwd=scratch, check=True)
        patch_file = scratch / "approved.patch"
        patch_file.write_bytes(patch)
        check = subprocess.run(["git", "apply", "--check", str(patch_file)], cwd=scratch,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check.returncode:
            subprocess.run(["git", "apply", "--reverse", "--check", str(patch_file)],
                           cwd=scratch, check=True)
            state = "already-included"
        else:
            subprocess.run(["git", "apply", str(patch_file)], cwd=scratch, check=True)
            for name in paths:
                file = scratch / name
                if not file.is_file():
                    raise ValueError("Runtime patch deletion requires an integration source snapshot")
                (payload / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, payload / name)
            state = "applied-to-generated-payload"
    notice = payload / "packaging/runtime/desktop-source-patches" / (revision + ".patch")
    notice.parent.mkdir(parents=True, exist_ok=True)
    notice.write_bytes(patch)
    return {"revision": revision, "paths": paths, "sha256": digest(notice), "state": state}

def inventory(root: Path) -> list[dict]:
    """Hash payload bytes without repeatedly resolving every file's ancestors."""
    root = root.resolve()
    directories, records = [root], []
    while directories:
        directory = directories.pop()
        # Every child comes from its checked parent. Reject reparse points before
        # scanning; repeated realpath walks add thousands of Windows syscalls.
        if directory.is_symlink() or directory.is_junction():
            raise ValueError("Payload contains a directory outside its root")
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_symlink():
                    raise ValueError("Payload contains a symbolic link")
                file = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    directories.append(file)
                elif entry.is_file(follow_symlinks=False):
                    if file == root / "inventory.json":
                        continue
                    records.append({"path": file.relative_to(root).as_posix(),
                                    "size": entry.stat(follow_symlinks=False).st_size,
                                    "sha256": digest(file)})
                else:
                    raise ValueError("Payload contains an unsupported file type")
    return sorted(records, key=lambda record: record["path"])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "environment", "helpers", "python-archive", "target"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--source-revision", default="HEAD")
    parser.add_argument("--helper-contract", type=Path,
                        help="Reviewed source JSON; defaults to source/packaging/runtime/helper-assets.json")
    parser.add_argument("--runtime-patch-repo", type=Path)
    parser.add_argument("--runtime-patch-revision")
    parser.add_argument("--refresh-source-only", action="store_true",
                        help="Refresh an existing generated payload; refuse any dependency lock change")
    args = parser.parse_args()
    if bool(args.runtime_patch_repo) != bool(args.runtime_patch_revision):
        raise ValueError("A runtime patch requires its explicit source repository and revision")
    source, environment, helpers, archive, target = (value.resolve() for value in
        (args.source, args.environment, args.helpers, args.python_archive, args.target))
    if not target.is_relative_to(DESKTOP / "test-results") or (target.exists() and not args.refresh_source_only):
        raise ValueError("Use a fresh target under this desktop lane test-results directory")
    if any(target == item or target.is_relative_to(item) or item.is_relative_to(target)
           for item in (source, environment, helpers)):
        raise ValueError("Payload sources and destination must be independent")
    if digest(archive) != PYTHON_SHA256:
        raise ValueError("The official pinned Python archive failed checksum validation")
    if f"version_info = {PYTHON_VERSION}" not in (environment / "pyvenv.cfg").read_text():
        raise ValueError("Dependency environment must match the tested CPython pin")
    sites = environment / "Lib" / "site-packages"
    if not sites.is_dir():
        raise ValueError("Expected an explicit project-owned Windows dependency environment")
    contract = (args.helper_contract or source / "packaging/runtime/helper-assets.json").resolve()
    helper_contract(contract, helpers)
    revision = subprocess.check_output(["git", "rev-parse", args.source_revision], cwd=source, text=True).strip()
    if args.refresh_source_only:
        manifest = json.loads((target / "bundle.json").read_text(encoding="utf-8"))
        if manifest.get("format") != "embedded-cpython-windows-v1" or not (target / "inventory.json").is_file():
            raise ValueError("Source refresh requires a completed generated embedded payload")
        previous = manifest["source_revision"]
        refresh_snapshot(source, previous, revision, target)
        if digest(target / "packaging/runtime/helper-assets.json") != manifest["helper_contract_sha256"]:
            raise ValueError("A changed helper contract requires a fresh acquired payload")
        helper_contract(target / "packaging/runtime/helper-assets.json", target / "helper-assets")
        manifest["source_patches"] = [apply_runtime_patch(args.runtime_patch_repo.resolve(),
            args.runtime_patch_revision, target)] if args.runtime_patch_repo else []
        shutil.copyfile(DESKTOP / "scripts/packaged-backend.py", target / "bootstrap.py")
        (target / "helper_copy.py").write_bytes(subprocess.check_output(
            ["git", "show", f"{revision}:scripts/copy_helper_assets.py"], cwd=source))
        manifest.update(source_revision=revision, helper_copy_sha256=digest(target / "helper_copy.py"))
        manifest.setdefault("source_refreshes", []).append({"previous_revision": previous,
            "revision": revision, "dependency_lock": "unchanged"})
        (target / "bundle.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        files = inventory(target)
        (target / "inventory.json").write_text(json.dumps(files, indent=2), encoding="utf-8")
        print(json.dumps({"target": str(target), "source_revision": revision, "refreshed": True,
                          "files": len(files), "bytes": sum(file["size"] for file in files)}))
        return
    target.mkdir(parents=True)
    python = target / "python"
    python.mkdir()
    with zipfile.ZipFile(archive) as contents:
        if any(Path(name).is_absolute() or ".." in Path(name).parts for name in contents.namelist()):
            raise ValueError("The Python archive contains an unsafe path")
        contents.extractall(python)
    # Python's supported embedded path contract ignores registry/user/global paths.
    # No import site: copied .pth files cannot execute outside-profile startup code.
    (python / "python314._pth").write_text(
        "python314.zip\n.\n../dependencies\n../runtime\n../upstream/hermes\n..\n", encoding="utf-8")
    snapshot(source, revision, target)
    source_patches = [apply_runtime_patch(args.runtime_patch_repo.resolve(),
                                        args.runtime_patch_revision, target)] if args.runtime_patch_repo else []
    print(json.dumps({"phase": "source-snapshot", "source_revision": revision}), flush=True)
    bundled_contract = target / "packaging/runtime/helper-assets.json"
    bundled_contract.parent.mkdir(parents=True, exist_ok=True)
    if bundled_contract.exists() and digest(bundled_contract) != digest(contract):
        raise ValueError("The source snapshot and explicit reviewed helper contract differ")
    shutil.copyfile(contract, bundled_contract)
    skipped = {"__pycache__", ".pytest_cache", "renulus"}
    def ignore(directory, names):
        return [name for name in names if name in skipped or name.endswith(".pth")
                or name in {"direct_url.json", "pyvenv.cfg"}]
    shutil.copytree(sites, target / "dependencies", ignore=ignore, symlinks=False)
    print(json.dumps({"phase": "windows-dependencies-copied"}), flush=True)
    (target / "helper_copy.py").write_bytes(subprocess.check_output(
        ["git", "show", f"{revision}:scripts/copy_helper_assets.py"], cwd=source))
    shutil.copyfile(DESKTOP / "scripts" / "packaged-backend.py", target / "bootstrap.py")
    spec = importlib.util.spec_from_file_location("helper_copy", target / "helper_copy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    helper_proof = module.copy_assets(helpers, target / "helper-assets")
    print(json.dumps({"phase": "public-helpers-verified"}), flush=True)
    distributions = []
    for metadata in sorted((target / "dependencies").glob("*.dist-info/METADATA")):
        fields = {}
        for line in metadata.read_text(encoding="utf-8").splitlines():
            if line.startswith(("Name: ", "Version: ")):
                key, value = line.split(": ", 1)
                fields[key] = value
            if "Name" in fields and "Version" in fields:
                break
        distributions.append(fields)
    manifest = {"version": 1, "format": "embedded-cpython-windows-v1",
                "python": {"version": PYTHON_VERSION, "archive_sha256": PYTHON_SHA256,
                           "executable": "python/python.exe",
                           "executable_sha256": digest(python / "python.exe")},
                "source_revision": revision, "bootstrap": "bootstrap.py",
                "source_patches": source_patches,
                "helper_contract_sha256": digest(bundled_contract),
                "helper_copy_sha256": digest(target / "helper_copy.py"),
                "helper_proof": helper_proof, "dependencies": distributions,
                "limits": ["Unsigned development bundle", "No live account or model proof"]}
    (target / "bundle.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    files = inventory(target)
    (target / "inventory.json").write_text(json.dumps(files, indent=2), encoding="utf-8")
    print(json.dumps({"target": str(target), "source_revision": revision,
                      "files": len(files), "bytes": sum(file["size"] for file in files),
                      "helpers": helper_proof}, indent=2))

if __name__ == "__main__":
    main()
