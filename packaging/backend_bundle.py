# SPDX-License-Identifier: MIT
"""Stage a closed, relocatable backend from explicitly prepared local artifacts.

No downloads, install hooks, developer PATH lookup or profile inputs. The native
Node loader resolves the frozen external package graph without junctions, so the
same immutable files work after relocation and inside a Windows application.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

NODE_SHA256 = "3193d7f751b8a07bd4acc70e81946ae9c6efdee83e07ad1c8d0e4089df7c5cef"
COHORT = "4b6fea2875e4f2e3e8a8fee181803e54f7056845"

GRAPH_LOADER = r"""// SPDX-License-Identifier: MIT
import { registerHooks, createRequire, isBuiltin } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL('./cohort/', import.meta.url));
const graph = JSON.parse(readFileSync(new URL('./cohort/graph.json', import.meta.url), 'utf8'));
const packages = new Map(graph.packages.map(p=>[p.path,p]));
const edges = new Map(graph.links.map(l=>[l.path,l.target]));
const metadata = new Map();
registerHooks({ resolve(specifier, context, next) {
  if (isBuiltin(specifier) || specifier.startsWith('.') || specifier.startsWith('/') ||
      specifier.startsWith('file:') || specifier.startsWith('#') || /^[a-z]:/i.test(specifier)) return next(specifier, context);
  if (specifier.includes(':')) throw new Error('bundle_module_scheme_refused');
  const parts=specifier.split('/'), name=specifier.startsWith('@')?parts.slice(0,2).join('/'):parts[0];
  const sub=specifier.slice(name.length);
  let parent='';
  if(context.parentURL?.startsWith('file:')) {
    const rel=path.relative(root,fileURLToPath(context.parentURL)).split(path.sep).join('/');
    const match=/^(p\/[a-f0-9]+)\//.exec(rel);if(match)parent=match[1];
  }
  const self=packages.get(parent);
  const target=self?.name===name?parent:edges.get((parent?parent+'/':'')+'node_modules/'+name);
  if(!target)throw new Error('bundle_module_not_in_closed_graph:'+name);
  const directory=path.join(root,target), manifest=path.join(directory,'package.json');
  let pkg=metadata.get(target);if(!pkg){pkg=JSON.parse(readFileSync(manifest,'utf8'));metadata.set(target,pkg);}
  if(pkg.exports) return next(pkg.name+sub,{...context,parentURL:pathToFileURL(manifest).href});
  const req=createRequire(manifest);
  const entry=req.resolve(sub?'./'+sub.slice(1):'./'+(pkg.main||'index.js'));
  return next(pathToFileURL(entry).href,context);
}});
"""

LAUNCH = """// SPDX-License-Identifier: MIT
import './graph-loader.mjs';
await import('./packages/backend/dist/main.mjs');
"""


def digest(path: Path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def copy_checked(source: Path, target: Path, expected: str | None = None):
    if source.is_symlink() or not source.is_file() or (expected is not None and digest(source) != expected):
        raise ValueError("bundle_source_hash_or_type_mismatch:" + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def copy_source(source: Path, target: Path):
    for file in source.rglob("*"):
        if any(part in {"__pycache__", "node_modules", ".git"} for part in file.relative_to(source).parts):
            continue
        if file.is_file() and not file.name.endswith((".pyc", ".pyo")):
            copy_checked(file, target / file.relative_to(source))


def stage(source: Path, prepared_python: Path, node: Path, cohort: Path, target: Path):
    if (not target.is_absolute() or target.exists() or any(target.is_relative_to(p) or p.is_relative_to(target)
            for p in (source, prepared_python, node.parent, cohort))):
        raise ValueError("bundle_fresh_independent_destination_required")
    target.mkdir(parents=True)
    if digest(node) != NODE_SHA256:
        raise ValueError("bundle_node_pin_mismatch")
    graph = json.loads((cohort / "inventory.json").read_text())
    if graph["source_commit"] != COHORT:
        raise ValueError("bundle_cohort_mismatch")
    existing = json.loads((prepared_python / "bundle.json").read_text())
    if existing["format"] != "embedded-cpython-windows-v1" or existing["python"]["version"] != "3.14.4":
        raise ValueError("bundle_python_pin_mismatch")
    # Copy only declared public dependency/helper/runtime artifacts; no profile
    # discovery. The prepared payload inventory itself pins every copied byte.
    entries = json.loads((prepared_python / "inventory.json").read_text())
    prefixes = ("python/", "dependencies/", "helper-assets/", "licenses/", "upstream/hermes/")
    for item in entries:
        name = item["path"]
        if name.startswith(prefixes):
            if Path(name).is_absolute() or ".." in Path(name).parts or ":" in name:
                raise ValueError("bundle_inventory_path_invalid")
            copy_checked(prepared_python / name, target / name, item["sha256"])
    copy_checked(node, target / "node/node.exe", NODE_SHA256)
    copy_checked(node.parent / "LICENSE", target / "licenses/node-26.4.0-LICENSE")
    for file in graph["files"]:
        name = file["path"]
        if not name.startswith("p/") or ".." in Path(name).parts or ":" in name:
            raise ValueError("bundle_cohort_path_invalid")
        copy_checked(cohort / name, target / "cohort" / name, file["sha256"])
    (target / "cohort/graph.json").write_text(json.dumps({"packages": graph["packages"], "links": graph["links"]}, separators=(",", ":")))
    copy_source(cohort / "provenance", target / "cohort/provenance")
    copy_checked(cohort / "inventory.json", target / "cohort/source-inventory.json")
    for directory in ("runtime/renulus", "content/packs", "packaging/runtime", "licenses"):
        copy_source(source / directory, target / directory)
    for name in ("LICENSE", "content/LICENSE", "packages/contracts/worker.schema.json"):
        copy_checked(source / name, target / name)
    for name in ("main.mjs", "storage-worker.mjs"):
        copy_checked(source / "packages/backend/dist" / name, target / "packages/backend/dist" / name)
    for name in ("backend_migration.py", "backend_bundle.py"):
        copy_checked(source / "packaging" / name, target / "packaging" / name)
    (target / "graph-loader.mjs").write_text(GRAPH_LOADER, encoding="utf-8")
    (target / "launch.mjs").write_text(LAUNCH, encoding="utf-8")
    # Patches apply to owned regular files using the exact reviewed source hashes.
    # Present a temporary package facade only during staging; it is not shipped.
    facade = target / ".patch-node-modules"
    for name in ("core", "plugin-browser"):
        link = next(item for item in graph["links"] if item["path"] == "node_modules/@opencode/" + name)
        copy_source(target / "cohort" / link["target"], facade / "@opencode" / name)
    patch = source / "packages/backend/src/domain/capabilities/native-patch.mjs"
    result = subprocess.run([str(node), str(patch), str(facade)], check=True, capture_output=True, text=True,
                            env={"SystemRoot": __import__('os').environ.get('SystemRoot', ''), "PATH": str(node.parent)})
    patch_receipt = json.loads(result.stdout)
    for name in ("core", "plugin-browser"):
        link = next(item for item in graph["links"] if item["path"] == "node_modules/@opencode/" + name)
        for changed in patch_receipt["files"]:
            posix = changed.replace("\\", "/")
            prefix = "@opencode/" + name + "/"
            if posix.startswith(prefix):
                copy_checked(facade / posix, target / "cohort" / link["target"] / posix[len(prefix):])
    shutil.rmtree(facade)
    # Every helper must match the CURRENT reviewed contract, not only the old
    # public payload's inventory. Current helpers are never acquired at runtime.
    helpers = json.loads((target / "packaging/runtime/helper-assets.json").read_text(encoding="utf-8-sig"))
    if helpers != json.loads((target / "helper-assets/manifest.json").read_text(encoding="utf-8-sig")):
        raise ValueError("bundle_helper_contract_mismatch")
    files = [{"path": p.relative_to(target).as_posix(), "sha256": digest(p), "bytes": p.stat().st_size}
             for p in sorted(target.rglob("*")) if p.is_file()]
    (target / "backend-inventory.json").write_text(json.dumps(files, separators=(",", ":")))
    manifest = {"contract": "renulus-backend-bundle/1", "node": "node/node.exe", "nodeSha256": NODE_SHA256,
        "python": "python/python.exe", "entrypoint": "launch.mjs", "cohort": COHORT,
        "cohortHash": digest(target / "cohort/source-inventory.json"), "patch": patch_receipt,
        "inventorySha256": digest(target / "backend-inventory.json"),
        "helperContractSha256": digest(target / "packaging/runtime/helper-assets.json"),
        "source": "working-tree-exact-inventory", "activation": "explicit-profile-selector-required"}
    (target / "backend-bundle.json").write_text(json.dumps(manifest, indent=2))
    return {"target": str(target), "files": len(files), "bytes": sum(f["bytes"] for f in files), **manifest}


def verify(target: Path):
    manifest = json.loads((target / "backend-bundle.json").read_text())
    if manifest["contract"] != "renulus-backend-bundle/1" or digest(target / "backend-inventory.json") != manifest["inventorySha256"]:
        raise ValueError("bundle_inventory_changed")
    files = json.loads((target / "backend-inventory.json").read_text())
    for item in files:
        file = target / item["path"]
        if not file.resolve().is_relative_to(target) or file.is_symlink() or digest(file) != item["sha256"] or file.stat().st_size != item["bytes"]:
            raise ValueError("bundle_member_changed:" + item["path"])
    return {"verified": True, "files": len(files), "cohortHash": manifest["cohortHash"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    for name in ("source", "prepared-python", "node", "cohort"):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args()
    if args.verify:
        result = verify(args.target.resolve())
    else:
        if any(getattr(args, n) is None for n in ("source", "prepared_python", "node", "cohort")):
            parser.error("All explicit prepared artifact paths are required")
        result = stage(args.source.resolve(), args.prepared_python.resolve(), args.node.resolve(), args.cohort.resolve(), args.target)
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
