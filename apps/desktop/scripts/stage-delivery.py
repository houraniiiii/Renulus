"""Prepare one immutable parent revision for an unsigned Windows delivery.

Refreshes a completed public embedded payload only when its dependency lock is
unchanged. Existing release/checkpoint directories and application profiles are
never inputs. Run --plan-only before the parent sends its final freeze revision.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

DESKTOP = Path(__file__).resolve().parents[1]
EXTERNAL_DELIVERY_ROOT = Path("E:/Renulus-native-delivery/desktop-20261005")
spec = importlib.util.spec_from_file_location("stage_backend", Path(__file__).with_name("stage-backend.py"))
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


def git(repo: Path, *arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=repo)


def committed_revision(source: Path, revision: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Delivery requires the parent's exact 40-character commit, not HEAD or a branch")
    actual = git(source, "rev-parse", "--verify", revision + "^{commit}").decode().strip()
    if actual != revision:
        raise ValueError("The delivery commit did not resolve to its supplied identity")
    return actual


def owned_path(value: Path, root: Path, *, fresh: bool = False) -> Path:
    resolved, root = value.resolve(), root.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError("Delivery output must stay in its assigned desktop generated directory")
    if fresh and resolved.exists():
        raise ValueError("Delivery output must be fresh; preserve the existing checkpoint")
    for ancestor in (value.absolute(), *value.absolute().parents):
        if ancestor.exists() and (ancestor.is_symlink() or ancestor.is_junction()):
            raise ValueError("Delivery may not traverse a reparse path")
        if ancestor == root:
            break
    return resolved


def delivery_output(value: Path, *, fresh: bool = True) -> Path:
    # This exact external root was reserved by the parent on 2026-10-05.
    for root in (DESKTOP / "release", EXTERNAL_DELIVERY_ROOT):
        if value.absolute().is_relative_to(root.absolute()):
            return owned_path(value, root, fresh=fresh)
    raise ValueError("Delivery output must stay in the desktop release tree or exact authorised E root")


def dependency_check(source: Path, previous: str, revision: str) -> None:
    changed = git(source, "diff", "--name-only", previous, revision, "--",
                  "uv.lock", "pyproject.toml").decode().strip()
    if changed:
        raise ValueError("The Windows dependency lock changed; stage and prove fresh selected wheels first")
    for name in ("package.json", "package-lock.json"):
        committed = git(source, "show", revision + ":apps/desktop/" + name)
        if committed != (DESKTOP / name).read_bytes():
            raise ValueError("The committed desktop manifest/lock differs from the installed packaging lane")


def plan(args) -> dict:
    source = args.source.resolve()
    revision = committed_revision(source, args.revision)
    payload = owned_path(args.payload, DESKTOP / "test-results")
    snapshot = owned_path(args.snapshot, DESKTOP / "test-results", fresh=True)
    output = delivery_output(args.output)
    temporary = owned_path(EXTERNAL_DELIVERY_ROOT / "temporary" / ("build-" + revision),
                           EXTERNAL_DELIVERY_ROOT, fresh=True)
    if snapshot.is_relative_to(payload) or payload.is_relative_to(snapshot):
        raise ValueError("Renderer snapshot and embedded payload must be independent")
    manifest = json.loads((payload / "bundle.json").read_text(encoding="utf-8"))
    if manifest.get("format") != "embedded-cpython-windows-v1" or not (payload / "inventory.json").is_file():
        raise ValueError("A completed embedded CPython payload is required")
    dependency_check(source, manifest["source_revision"], revision)
    for name in ("electron/backend.ts", "scripts/packaged-backend.py"):
        if git(source, "show", revision + ":apps/desktop/" + name) != (DESKTOP / name).read_bytes():
            raise ValueError("The final source must include the packaging lane adoption: " + name)
    trusted = payload / "packaging/runtime/helper-assets.json"
    reviewed = git(source, "show", revision + ":packaging/runtime/helper-assets.json")
    if hashlib.sha256(reviewed).hexdigest() != manifest["helper_contract_sha256"]:
        raise ValueError("The final reviewed helper contract changed; acquire a fresh admitted payload")
    if trusted.read_bytes() != reviewed:
        raise ValueError("The embedded source helper anchor differs from the final committed contract")
    selected = backend.helper_contract(trusted, args.helpers.resolve())
    backend.helper_contract(trusted, payload / "helper-assets")
    helper_files = [file for group in selected["groups"].values() for file in group["files"]]
    if len(helper_files) != 19 or sum(file["size"] for file in helper_files) != 483_597_181:
        raise ValueError("This delivery reserves the reviewed 19-file public helper inventory")
    if backend.digest(args.python_archive) != backend.PYTHON_SHA256:
        raise ValueError("The official embedded Python archive did not match its pinned checksum")
    if manifest["python"]["version"] != backend.PYTHON_VERSION:
        raise ValueError("The completed payload uses a different Python release")
    installed = json.loads((DESKTOP / "node_modules/electron/package.json").read_text())["version"]
    pin = json.loads((DESKTOP / "package.json").read_text())["devDependencies"]["electron"]
    if installed != pin or (DESKTOP / "node_modules/electron/dist/version").read_text().strip() != pin:
        raise ValueError("Installed Electron must match both package pin and actual artifact version")
    node = shutil.which("node")
    if not node:
        raise ValueError("Node is required for developer packaging, not for the delivered application")
    renderer = snapshot / "apps/desktop/dist"
    native = snapshot / "apps/desktop/dist-electron"
    commands = [
        [sys.executable, str(DESKTOP / "scripts/stage-backend.py"),
         "--source", str(source), "--source-revision", revision,
         "--environment", str(args.environment.resolve()), "--helpers", str(args.helpers.resolve()),
         "--python-archive", str(args.python_archive.resolve()), "--helper-contract", str(trusted),
         "--target", str(payload), "--refresh-source-only"],
        [sys.executable, str(DESKTOP / "scripts/stage-renderer.py"),
         "--source", str(source), "--revision", revision, "--target", str(snapshot), "--include-native"],
    ]
    build = [node, str(DESKTOP / "node_modules/electron-builder/cli.js"), "--config",
             str(DESKTOP / "electron-builder.config.cjs"), "--win", "--x64", "--publish", "never"]
    if args.package == "directory":
        build.append("--dir")
    commands.append(build)
    return {"version": 1, "source_revision": revision, "kind": "matching-unsigned-windows-delivery",
            "payload": str(payload), "snapshot": str(snapshot), "output": str(output),
            "temporary_directory": str(temporary),
            "executable": str(output / "win-unpacked/Renulus Development.exe"),
            "package": args.package, "electron": pin, "python": backend.PYTHON_VERSION,
            "helper_files": len(helper_files), "helper_bytes": sum(file["size"] for file in helper_files),
            "commands": commands,
            "environment": {"RENULUS_BACKEND_BUNDLE": str(payload),
                            "RENULUS_RENDERER_BUNDLE": str(renderer),
                            "RENULUS_NATIVE_BUNDLE": str(native),
                            "RENULUS_DELIVERY_OUTPUT": str(output),
                            "TEMP": str(temporary), "TMP": str(temporary)}}


def execute(delivery: dict) -> None:
    payload = Path(delivery["payload"])
    # Verify the already acquired public wheel/helper bytes before source refresh.
    stored = json.loads((payload / "inventory.json").read_text())
    if backend.inventory(payload) != stored:
        raise ValueError("The acquired payload changed outside its recorded byte inventory")
    temporary = owned_path(Path(delivery["temporary_directory"]), EXTERNAL_DELIVERY_ROOT, fresh=True)
    temporary.mkdir(parents=True, exist_ok=False)
    environment = dict(os.environ, **delivery["environment"])
    for command in delivery["commands"][:2]:
        subprocess.run(command, cwd=DESKTOP, env=environment, check=True)
    renderer = json.loads((Path(environment["RENULUS_RENDERER_BUNDLE"]) / "renderer-provenance.json").read_text())
    native = json.loads((Path(environment["RENULUS_NATIVE_BUNDLE"]) / "native-provenance.json").read_text())
    current = json.loads((payload / "bundle.json").read_text())
    if {item["source_revision"] for item in (current, renderer, native)} != {delivery["source_revision"]}:
        raise ValueError("Backend, renderer and native source revisions do not match")
    adoption = native["backend_adoption"]
    if adoption["source_sha256"] != adoption["adopted_sha256"]:
        raise ValueError("The final native source required an unstaged adoption patch")
    subprocess.run(delivery["commands"][2], cwd=DESKTOP, env=environment, check=True)
    output = Path(delivery["output"])
    if not Path(delivery["executable"]).is_file():
        raise ValueError("The native packaging command produced no runnable executable")
    installed = json.loads((output / "win-unpacked/resources/backend/bundle.json").read_text())
    if installed["source_revision"] != delivery["source_revision"]:
        raise ValueError("The packaged embedded runtime differs from the selected revision")
    delivery["executable_sha256"] = backend.digest(Path(delivery["executable"]))
    delivery["app_asar_sha256"] = backend.digest(output / "win-unpacked/resources/app.asar")
    delivery["native_launch"] = "pending actual relocated native journey"
    delivery["installers"] = [{"path": str(file), "bytes": file.stat().st_size,
                              "sha256": backend.digest(file)} for file in output.glob("*-setup.exe")]
    (output / "delivery-provenance.json").write_text(json.dumps(delivery, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "payload", "snapshot", "output", "environment", "helpers", "python-archive"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--package", choices=("directory", "installer"), default="directory")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    delivery = plan(args)
    if not args.plan_only:
        execute(delivery)
    print(json.dumps({"plan_only": args.plan_only, **delivery}, indent=2))


if __name__ == "__main__":
    main()
