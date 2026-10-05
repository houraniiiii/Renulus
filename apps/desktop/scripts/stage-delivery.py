"""Prepare one immutable parent revision for an unsigned Windows delivery.

Copies a completed public embedded payload to fresh E staging when its dependency
lock is unchanged, then refreshes committed source there. Existing release/
checkpoint directories and application profiles are never inputs. Run --plan-only
before the parent sends its final freeze revision.
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
from delivery_paths import DESKTOP, EXTERNAL_DELIVERY_ROOT, generated_path, owned_path

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
    resumed = getattr(args, 'resume_staged', False)
    source = args.source.resolve()
    revision = committed_revision(source, args.revision)
    base_payload = generated_path(args.payload)
    output = delivery_output(args.output)
    external = output.is_relative_to(EXTERNAL_DELIVERY_ROOT.resolve())
    snapshot = owned_path(args.snapshot, EXTERNAL_DELIVERY_ROOT if external else DESKTOP / "test-results", fresh=True)
    payload = owned_path(EXTERNAL_DELIVERY_ROOT / "payloads" / ("backend-" + revision[:8]),
                         EXTERNAL_DELIVERY_ROOT, fresh=not resumed) if external else base_payload
    modules = owned_path(EXTERNAL_DELIVERY_ROOT / "environment" / ("node-" + revision[:8]) / "node_modules",
                         EXTERNAL_DELIVERY_ROOT, fresh=not resumed) if external else DESKTOP / "node_modules"
    temporary = owned_path(EXTERNAL_DELIVERY_ROOT / "temporary" / ("build-" + revision),
                           EXTERNAL_DELIVERY_ROOT, fresh=not resumed)
    if resumed and not external:
        raise ValueError('Staged continuation requires the reserved external public tree')
    if snapshot.is_relative_to(payload) or payload.is_relative_to(snapshot):
        raise ValueError("Renderer snapshot and embedded payload must be independent")
    manifest = json.loads((base_payload / "bundle.json").read_text(encoding="utf-8"))
    if manifest.get("format") != "embedded-cpython-windows-v1" or not (base_payload / "inventory.json").is_file():
        raise ValueError("A completed embedded CPython payload is required")
    dependency_check(source, manifest["source_revision"], revision)
    for name in ("electron/backend.ts", "scripts/packaged-backend.py"):
        if git(source, "show", revision + ":apps/desktop/" + name) != (DESKTOP / name).read_bytes():
            raise ValueError("The final source must include the packaging lane adoption: " + name)
    trusted = base_payload / "packaging/runtime/helper-assets.json"
    reviewed = git(source, "show", revision + ":packaging/runtime/helper-assets.json")
    if hashlib.sha256(reviewed).hexdigest() != manifest["helper_contract_sha256"]:
        raise ValueError("The final reviewed helper contract changed; acquire a fresh admitted payload")
    if trusted.read_bytes() != reviewed:
        raise ValueError("The embedded source helper anchor differs from the final committed contract")
    selected = backend.helper_contract(trusted, args.helpers.resolve())
    backend.helper_contract(trusted, base_payload / "helper-assets")
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
    if external:
        commands[1].extend(["--node-modules", str(modules)])
    build = [node, str(modules / "electron-builder/cli.js"), "--config",
             str(DESKTOP / "electron-builder.config.cjs"), "--win", "--x64", "--publish", "never"]
    if args.package == "directory":
        build.append("--dir")
    commands.append(build)
    return {"version": 1, "source_revision": revision, "kind": "matching-unsigned-windows-delivery",
            "resumed_staged_renderer": resumed,
            "base_payload": str(base_payload), "payload": str(payload), "snapshot": str(snapshot), "output": str(output),
            "build_node_modules": str(modules), "build_cwd": str(snapshot / "apps/desktop") if external else str(DESKTOP),
            "temporary_directory": str(temporary),
            "executable": str(output / "win-unpacked/Renulus Development.exe"),
            "package": args.package, "electron": pin, "python": backend.PYTHON_VERSION,
            "installer_app_id": "org.renulus.desktop.delivery." + revision,
            "helper_files": len(helper_files), "helper_bytes": sum(file["size"] for file in helper_files),
            "commands": commands,
            "environment": {"RENULUS_BACKEND_BUNDLE": str(payload),
                            "RENULUS_RENDERER_BUNDLE": str(renderer),
                            "RENULUS_NATIVE_BUNDLE": str(native),
                            "RENULUS_DELIVERY_OUTPUT": str(output),
                            "RENULUS_DELIVERY_REVISION": revision,
                            "TEMP": str(temporary), "TMP": str(temporary),
                            "ELECTRON_CACHE": str(temporary / "cache/electron"),
                            "ELECTRON_BUILDER_CACHE": str(temporary / "cache/electron-builder"),
                            "npm_config_cache": str(temporary / "cache/npm"),
                            "UV_CACHE_DIR": str(temporary / "cache/uv"),
                            "PIP_CACHE_DIR": str(temporary / "cache/pip"),
                            "PYTHONDONTWRITEBYTECODE": "1"}}


def validate_completed_stage(payload: Path, revision: str, electron: str, modules: Path) -> dict:
    current = json.loads((payload / 'bundle.json').read_text())
    if current.get('source_revision') != revision or current.get('source_patches'):
        raise ValueError('Continuation requires this exact completed unpatched source payload')
    if current.get('format') != 'embedded-cpython-windows-v1' or current['python']['version'] != backend.PYTHON_VERSION:
        raise ValueError('Continuation requires the admitted embedded Python payload')
    if json.loads((modules / 'electron/package.json').read_text())['version'] != electron or (modules / 'electron/dist/version').read_text().strip() != electron:
        raise ValueError('Continuation requires the pinned copied Electron artifact')
    stored = json.loads((payload / 'inventory.json').read_text())
    if backend.inventory(payload) != stored:
        raise ValueError('The completed staged payload differs from its byte inventory')
    return {'files': len(stored), 'bytes': sum(file['size'] for file in stored),
            'inventory_sha256': backend.digest(payload / 'inventory.json')}


def execute(delivery: dict) -> None:
    base_payload, payload = Path(delivery["base_payload"]), Path(delivery["payload"])
    # Verify the already acquired public wheel/helper bytes before source refresh.
    resumed = delivery.get('resumed_staged_renderer', False)
    if resumed:
        verified = validate_completed_stage(payload, delivery['source_revision'], delivery['electron'], Path(delivery['build_node_modules']))
        delivery['continued_public_stage'] = verified
        print(json.dumps({'phase': 'completed-staged-inventory-verified', **verified}), flush=True)
    else:
        stored = json.loads((base_payload / "inventory.json").read_text())
        if backend.inventory(base_payload) != stored:
            raise ValueError("The acquired payload changed outside its recorded byte inventory")
        print(json.dumps({"phase": "public-input-inventory-verified", "files": len(stored)}), flush=True)
    temporary = owned_path(Path(delivery["temporary_directory"]), EXTERNAL_DELIVERY_ROOT, fresh=not resumed)
    temporary.mkdir(parents=True, exist_ok=resumed)
    if base_payload != payload and not resumed:
        owned_path(payload, EXTERNAL_DELIVERY_ROOT, fresh=True)
        shutil.copytree(base_payload, payload)
        print(json.dumps({"phase": "public-payload-copied", "target": str(payload)}), flush=True)
        modules = owned_path(Path(delivery["build_node_modules"]), EXTERNAL_DELIVERY_ROOT, fresh=True)
        shutil.copytree(DESKTOP / "node_modules", modules,
                        ignore=shutil.ignore_patterns(".vite", ".vite-temp", ".cache", "__pycache__"))
        print(json.dumps({"phase": "build-environment-copied", "target": str(modules)}), flush=True)
        delivery["public_inputs"] = {"base_inventory_sha256": backend.digest(base_payload / "inventory.json"),
                                    "node_package_lock_sha256": backend.digest(DESKTOP / "package-lock.json")}
    environment = dict(os.environ, **delivery["environment"])
    for name in ('RENULUS_BACKEND_URL', 'RENULUS_SESSION_TOKEN', 'RENULUS_PROFILE', 'RENULUS_SOURCE_DESKTOP', 'RENULUS_PDF_FIXTURE_ONLY'):
        environment.pop(name, None)
    for command in delivery["commands"][1:2] if resumed else delivery["commands"][:2]:
        subprocess.run(command, cwd=temporary, env=environment, check=True)
    renderer = json.loads((Path(environment["RENULUS_RENDERER_BUNDLE"]) / "renderer-provenance.json").read_text())
    native = json.loads((Path(environment["RENULUS_NATIVE_BUNDLE"]) / "native-provenance.json").read_text())
    current = json.loads((payload / "bundle.json").read_text())
    if {item["source_revision"] for item in (current, renderer, native)} != {delivery["source_revision"]}:
        raise ValueError("Backend, renderer and native source revisions do not match")
    adoption = native["backend_adoption"]
    if adoption["source_sha256"] != adoption["adopted_sha256"]:
        raise ValueError("The final native source required an unstaged adoption patch")
    subprocess.run(delivery["commands"][2], cwd=Path(delivery["build_cwd"]), env=environment, check=True)
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
    parser.add_argument('--resume-staged', action='store_true',
                        help='Revalidate a completed public payload and build a fresh renderer snapshot; preserve failed source staging')
    args = parser.parse_args()
    delivery = plan(args)
    if not args.plan_only:
        execute(delivery)
    print(json.dumps({"plan_only": args.plan_only, **delivery}, indent=2))


if __name__ == "__main__":
    main()
