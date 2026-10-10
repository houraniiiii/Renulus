# SPDX-License-Identifier: MIT
"""Materialize built OpenCode and its actual installed Bun graph, without installing.

The source is read-only. Junctions in the resulting developer cohort point only
to copied packages inside that cohort. Relocation/distribution remains H20.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import quote


PACKAGES = (
    "schema", "codemode", "ai", "util", "protocol", "client", "plugin",
    "plugin-browser", "core", "simulation", "server", "sdk",
)
SHA = "4b6fea2875e4f2e3e8a8fee181803e54f7056845"
# Core's emitted NodeSocket chunk retains this external import even though the
# pinned source declares it under devDependencies. Copy its frozen resolution.
RUNTIME_PROMOTIONS = {"@opencode/core": ("@effect/platform-node",)}
SOURCE_PINS = {
    "package.json": "09ab22d46509f617157a1573a59d9a5868aa6d8f5556d758ee5415d8c5679abd",
    "bun.lock": "3232687da07c15408130bc7b2eefd37364eb1e3ac9e61d2b779a3a6880b38d1c",
    "LICENSE": "625f0f619133f89bbbb2abe37369613dfa1885eba1e50d02170deb62bb42cb6b",
}
ARTIFACTS = {
    "source": {
        "url": f"https://codeload.github.com/anomalyco/opencode/tar.gz/{SHA}",
        "sha256": "b50f959e4a072e10b81f73b144c3017e83e5c8fafcdefc381d627063c8c67761",
        "size": 79614886,
    },
    "bun": {
        "version": "1.4.2",
        "url": "https://github.com/oven-sh/bun/releases/download/bun-v1.4.2/bun-windows-x64.zip",
        "sha256": "ce4c17497b2f29712a99d3d53f028de28cd42e3bacb8589599e7f000e49b6405",
        "license_url": "https://raw.githubusercontent.com/oven-sh/bun/bun-v1.4.2/LICENSE.md",
        "role": "build-only",
    },
    "node": {
        "version": "26.4.0",
        "url": "https://nodejs.org/dist/v26.4.0/node-v26.4.0-win-x64.zip",
        "sha256": "5f87d038c6ec442aa46b9126f8ca170acbd2f3b9b9152ca798cf54596a31e214",
        "exe_sha256": "3193d7f751b8a07bd4acc70e81946ae9c6efdee83e07ad1c8d0e4089df7c5cef",
        "license_url": "https://raw.githubusercontent.com/nodejs/node/v26.4.0/LICENSE",
        "role": "runtime",
    },
}
BUILD_BOOTSTRAP = {
    "status": "documented-parent-bootstrap-not-automated-or-replayed-from-fresh-source",
    "junctions_after_filtered_install": {
        "node_modules/.bin": "packages/ai/node_modules/.bin",
        "node_modules/typescript": "packages/ai/node_modules/typescript",
    },
    "typescript_version": "5.8.2",
    "mime_types": {
        "name": "@types/mime-types", "version": "3.0.1", "role": "source-build-only",
        "url": "https://registry.npmjs.org/@types/mime-types/-/mime-types-3.0.1.tgz",
        "integrity": "sha512-xRMsfuQbnRq1Ef+C+RKaENOxXX87Ygl38W1vDfPHRku02TgQr+Qd8iivLtAMcR0KF5/29xlnFihkTlbqFrGOVQ==",
        "integrity_source": "pinned bun.lock packages[@types/mime-types]",
        "tar_sha256": None,
        "tar_sha256_status": "parent has earlier acquisition receipt; unavailable to this lane; no redownload",
        "license": "MIT",
        "destination": "node_modules/@types/mime-types",
        "installed_files_sha256": {
            "index.d.ts": "c0b69899a086f2049f739fb1b5ed76ec8bea7a826347ed42c2661ceca2d3ebd1",
            "LICENSE": "c2cfccb812fe482101a8f04597dfc5a9991a6b2748266c47ac91b6a5aae15383",
            "package.json": "70a0ca4329b067bab4f775ac740fb5d4e02240f1d7e1c62350788bbe87b29696",
            "README.md": "1b45414ca16655b0482f08fa8d807a4c7ebba7948aff299d813306e3b713e24e",
        },
    },
}


class CohortError(ValueError):
    """Preparation cannot preserve the requested source/dependency boundary."""


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_json(path: Path, data) -> None:
    # Condition order is executable behavior: `default` must stay last.
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def validate_source(source: Path) -> None:
    for name, expected in SOURCE_PINS.items():
        path = source / name
        if not path.is_file() or digest(path) != expected:
            raise CohortError(f"Source pin mismatch: {name}")


def validate_manifest_destination(manifest: Path, source: Path, output: Path,
                                  node: Path, source_archive: Path | None) -> None:
    """The receipt must not overwrite inputs or the graph it describes."""
    destination = manifest.resolve()
    protected_trees = (source.resolve(), output.resolve(), node.resolve().parent)
    protected_files = [Path(__file__).resolve()]
    if source_archive:
        protected_files.append(source_archive.resolve())
    if (any(destination.is_relative_to(tree) for tree in protected_trees) or
            destination in protected_files or
            (destination.exists() and (not destination.is_file() or destination.stat().st_nlink > 1))):
        raise CohortError("Manifest destination overlaps protected inputs/cohort or aliases an existing file")
    resolved_output = output.resolve()
    if resolved_output.is_relative_to(source) or source.is_relative_to(resolved_output):
        raise CohortError("Source and output must be separate directories")


def selected_roots(source: Path):
    runtime = {"@opencode/" + name: source / "packages" / name for name in PACKAGES}
    runtime["effect"] = resolve_dependency(source / "packages/sdk", "effect", source)
    tooling = {
        "typescript": resolve_dependency(source, "typescript", source),
        "@types/node": resolve_dependency(source / "packages/core", "@types/node", source),
    }
    expected = {"effect": "4.0.1", "typescript": "5.8.2", "@types/node": "24.12.2"}
    for name, version in expected.items():
        path = runtime.get(name, tooling.get(name))
        if path is None or json.loads((path / "package.json").read_text())["version"] != version:
            raise CohortError(f"Missing pinned installed root: {name}@{version}")
    for name in PACKAGES:
        path = source / "packages" / name
        if json.loads((path / "package.json").read_text())["version"] != "2.0.26":
            raise CohortError(f"Source package version mismatch: {name}")
    return runtime, tooling


def package_name(name: str) -> None:
    if not re.fullmatch(r"(?:@[a-zA-Z0-9_.-]+/)?[a-zA-Z0-9_.-]+", name) or name in (".", ".."):
        raise CohortError(f"Invalid package name: {name!r}")


def within(path: Path, boundary: Path) -> Path:
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(boundary):
        raise CohortError(f"Resolved path leaves the selected source/cohort: {path}")
    return resolved


def resolve_dependency(origin: Path, name: str, source: Path) -> Path | None:
    package_name(name)
    for ancestor in (origin, *origin.parents):
        if not ancestor.is_relative_to(source):
            break
        candidate = ancestor / "node_modules" / name
        if (candidate / "package.json").is_file():
            return within(candidate, source)
    return None


def collect_graph(source: Path, roots: dict[str, Path]):
    graph = {}
    queue = deque(within(path, source) for path in roots.values())
    while queue:
        path = queue.popleft()
        if path in graph:
            continue
        manifest = json.loads((path / "package.json").read_text(encoding="utf-8"))
        package_name(manifest["name"])
        dependencies = dict(manifest.get("dependencies", {}))
        promoted = {name: manifest["devDependencies"][name]
                    for name in RUNTIME_PROMOTIONS.get(manifest["name"], ())
                    if name in manifest.get("devDependencies", {})}
        dependencies.update(promoted)
        optional = manifest.get("optionalDependencies", {})
        dependencies.update(optional)
        peers = manifest.get("peerDependencies", {})
        for name, version in peers.items():
            dependencies.setdefault(name, version)
        node = {"manifest": manifest, "dependencies": {}, "missing": [], "promoted": promoted}
        graph[path] = node
        for name in sorted(dependencies):
            target = resolve_dependency(path, name, source)
            kinds = [kind for kind in ("dependencies", "optionalDependencies", "peerDependencies")
                     if name in manifest.get(kind, {})]
            if name in promoted:
                kinds.append("emitted-node-runtime")
            if target is None:
                allowed = name in optional or (
                    name not in manifest.get("dependencies", {}) and
                    manifest.get("peerDependenciesMeta", {}).get(name, {}).get("optional", False)
                )
                if not allowed:
                    raise CohortError(f"Missing installed dependency {name} for {manifest['name']} at {path}")
                node["missing"].append({"name": name, "kinds": kinds, "reason": "optional-not-installed"})
                continue
            node["dependencies"][name] = {"path": target, "kinds": kinds, "requested": dependencies[name]}
            queue.append(target)
    return graph


def output_path(value: str, name: str, types=False) -> str:
    prefix = "./dist/types/" if name == "@opencode/core" and types else "./dist/"
    return re.sub(r"\.ts$", ".d.ts" if types else ".js", value.replace("./src/", prefix))


def staged_manifest(node, graph):
    manifest = dict(node["manifest"])
    name = manifest["name"]
    manifest["exports"] = {
        key: {"types": output_path(value, name, True), "import": output_path(value, name)}
        if isinstance(value, str) else value
        for key, value in manifest.get("exports", {}).items()
    }
    if "imports" in manifest:
        manifest["imports"] = {
            key: {condition: output_path(value, name, condition == "types")
                  for condition, value in conditions.items()}
            for key, conditions in manifest["imports"].items()
        }
    if node["promoted"]:
        manifest["dependencies"] = {**manifest.get("dependencies", {}), **node["promoted"]}
    for kind in ("dependencies", "optionalDependencies", "peerDependencies"):
        if kind in manifest:
            manifest[kind] = {
                dep: graph[node["dependencies"][dep]["path"]]["manifest"]["version"]
                if dep in node["dependencies"] and version.startswith(("workspace:", "catalog:")) else version
                for dep, version in manifest[kind].items()
            }
    manifest.pop("devDependencies", None)
    manifest.pop("scripts", None)
    return manifest


def copy_payload(origin: Path, destination: Path, boundary: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for entry in sorted(origin.iterdir(), key=lambda item: item.name):
        if entry.name in ("node_modules", ".git"):
            continue
        resolved = within(entry, boundary)
        target = destination / entry.name
        if resolved.is_dir():
            copy_payload(resolved, target, boundary)
        elif resolved.is_file():
            shutil.copyfile(resolved, target)
            if digest(resolved) != digest(target):
                raise CohortError(f"Source changed while copying {entry}")
        else:
            raise CohortError(f"Unsupported payload entry: {entry}")


def create_links(links: list[dict[str, str]], output: Path) -> None:
    for link in links:
        path, target = Path(link["path"]), Path(link["target"])
        if not path.is_relative_to(output) or not within(target, output).is_relative_to(output):
            raise CohortError("A cohort link would leave its owned root")
        path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        command = (
            "$ErrorActionPreference='Stop'; "
            "$items=([Console]::In.ReadToEnd() | ConvertFrom-Json); "
            "foreach($item in $items){ "
            "New-Item -ItemType Junction -Path $item.path -Target $item.target | Out-Null }"
        )
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            input=json.dumps(links), text=True, capture_output=True, timeout=180,
        )
        if completed.returncode:
            raise CohortError("Creating owned junctions failed: " + completed.stderr.strip())
    else:
        for link in links:
            path = Path(link["path"])
            path.symlink_to(os.path.relpath(link["target"], path.parent), target_is_directory=True)
    for link in links:
        if within(Path(link["path"]), output) != Path(link["target"]):
            raise CohortError("Cohort link verification failed")


def read_inventory(output: Path, *, allow_unsealed: bool = False):
    output = output.resolve(strict=True)
    receipt = output / "READY.json"
    if (output / "INCOMPLETE").exists() or not receipt.is_file():
        if not allow_unsealed or not (output / "MATERIALIZED.json").is_file():
            raise CohortError("Cohort is incomplete")
        receipt = output / "MATERIALIZED.json"
    ready = json.loads(receipt.read_text(encoding="utf-8"))
    if digest(output / "inventory.json") != ready["inventory_sha256"]:
        raise CohortError("Inventory hash mismatch")
    return json.loads((output / "inventory.json").read_text(encoding="utf-8"))


def verify_cohort(output: Path):
    """Check the receipt, every copied byte, and every recorded local link."""
    output = output.resolve(strict=True)
    inventory = read_inventory(output)
    if inventory.get("provenance_status") != "recorded-from-frozen-source-and-installed-bytes":
        raise CohortError("Cohort provenance is incomplete")
    for record in inventory["files"]:
        path = within(output / record["path"], output)
        if path.stat().st_size != record["size"] or digest(path) != record["sha256"]:
            raise CohortError(f"Payload hash mismatch: {record['path']}")
    for link in inventory["links"]:
        path = output / link["path"]
        if not (path.is_symlink() or path.is_junction()) or within(path, output) != output / link["target"]:
            raise CohortError(f"Dependency link mismatch: {link['path']}")
    return inventory


def record_provenance(source: Path, output: Path, node: Path | None = None):
    """Seal copied bytes with the original lock, patch inputs and license evidence.

    The base receipt already records copy-time hashes. This adds provenance;
    `verify` separately rechecks all payload bytes without reading the source.
    """
    source, output = source.resolve(strict=True), output.resolve(strict=True)
    inventory = read_inventory(output, allow_unsealed=True)
    root_manifest = json.loads((source / "package.json").read_text(encoding="utf-8"))
    # This pinned Bun JSONC lock uses trailing commas; protect quoted strings.
    lock = json.loads(re.sub(r'("(?:\\.|[^"\\])*")|,\s*(?=[}\]])',
                            lambda match: match.group(1) or "",
                            (source / "bun.lock").read_text(encoding="utf-8")))
    locked = {}
    for key, value in lock["packages"].items():
        locked.setdefault(value[0], []).append((key, value))
    file_by_path = {row["path"]: row for row in inventory["files"]}
    for package in inventory["packages"]:
        name, version = package["name"], package["version"]
        if package["source"].startswith("packages/"):
            reference = f"{name}@workspace:{package['source']}"
            artifact = {"kind": "pinned-source-workspace", "reference": reference,
                        "commit": SHA, "archive": ARTIFACTS["source"]}
            if package["payload"] != "built-dist":
                package["payload"] = "auxiliary-workspace-source"
        else:
            reference = f"{name}@{version}"
            candidates = locked.get(reference, [])
            if not candidates:
                raise CohortError(f"No exact frozen-lock artifact for copied package: {reference}")
            integrities = {row[-1] for _, row in candidates if isinstance(row[-1], str) and row[-1].startswith("sha")}
            if len(integrities) != 1:
                raise CohortError(f"Ambiguous frozen artifact integrity: {reference}")
            artifact = {
                "kind": "npm-registry-artifact", "reference": reference,
                "integrity": next(iter(integrities)), "lock_keys": sorted(key for key, _ in candidates),
                "url": "https://registry.npmjs.org/" + quote(name, safe="@/") + "/-/" +
                       quote(name.rsplit("/", 1)[-1] + "-" + version + ".tgz"),
                "url_basis": "standard public registry artifact path; not fetched by materializer",
            }
        if reference not in locked:
            raise CohortError(f"Workspace missing from frozen lock: {reference}")
        package["lock_artifact"] = artifact
        package["license_evidence"] = [
            {key: file_by_path[path][key] for key in ("path", "sha256", "size")}
            for path in package["license_files"]
        ]
        package["license_notice_status"] = "copied-notices" if package["license_evidence"] else "no-notice-file-in-installed-package"
    provenance_files = []

    def preserve(origin: Path, relative: str):
        target = output / "provenance" / relative
        if not target.absolute().is_relative_to(output / "provenance"):
            raise CohortError("Provenance path leaves cohort")
        target.parent.mkdir(parents=True, exist_ok=True)
        expected = digest(origin)
        if target.exists() and digest(target) != expected:
            raise CohortError(f"Existing provenance differs: {relative}")
        shutil.copyfile(origin, target)
        if digest(target) != expected:
            raise CohortError(f"Provenance changed during copy: {relative}")
        record = {"path": target.relative_to(output).as_posix(), "sha256": expected,
                  "size": target.stat().st_size, "role": "provenance"}
        provenance_files.append(record)
        return record

    for name in ("package.json", "bun.lock", "LICENSE"):
        preserve(source / name, name)
    patches = []
    for reference, relative in sorted(root_manifest.get("patchedDependencies", {}).items()):
        record = preserve(within(source / relative, source), relative)
        patches.append({
            "reference": reference, "source_path": relative, "sha256": record["sha256"],
            "copied_package_ids": [package["id"] for package in inventory["packages"]
                                   if package["lock_artifact"]["reference"] == reference],
            "application_evidence": "installed payload bytes preserved; declaration is not independent patch-application proof",
        })
    if node:
        preserve(node.parent / "LICENSE", "node-LICENSE")
    inventory["patches"] = patches
    inventory["source_commit"] = SHA
    inventory["artifacts"] = ARTIFACTS
    inventory["provenance_status"] = "recorded-from-frozen-source-and-installed-bytes"
    root_package = output / "package.json"
    extra = {row["path"]: row for row in provenance_files}
    extra["package.json"] = {"path": "package.json", "sha256": digest(root_package),
                             "size": root_package.stat().st_size, "role": "cohort-root-manifest"}
    inventory["files"] = sorted(
        [row for row in inventory["files"] if row["path"] not in extra] + list(extra.values()),
        key=lambda row: row["path"],
    )
    write_json(output / "inventory.json", inventory)
    write_json(output / "READY.json", {"inventory_sha256": digest(output / "inventory.json"),
                                       "packages": len(inventory["packages"]), "files": len(inventory["files"])})
    (output / "INCOMPLETE").unlink(missing_ok=True)
    (output / "MATERIALIZED.json").unlink(missing_ok=True)
    return inventory


def prepare_cohort(source: Path, output: Path, runtime_roots: dict[str, Path], tooling_roots: dict[str, Path]):
    """Copy a closed installed graph and return its observable hash/license inventory."""
    source = source.resolve(strict=True)
    output = Path(os.path.abspath(output))
    if os.path.lexists(output):
        raise CohortError("Output already exists; it was not modified. Choose a fresh owned directory.")
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise CohortError("Source and output must be separate directories")
    for ancestor in output.parents:
        if ancestor.is_symlink() or ancestor.is_junction():
            raise CohortError("Output ancestors must not redirect through links")
    roots = {**runtime_roots, **tooling_roots}
    graph = collect_graph(source, roots)
    if "effect" in runtime_roots:
        effects = [path for path, node in graph.items() if node["manifest"]["name"] == "effect"]
        if (effects != [within(runtime_roots["effect"], source)] or
                graph[effects[0]]["manifest"]["version"] != "4.0.1"):
            raise CohortError("The cohort must resolve one shared Effect 4.0.1 instance")
    for path, node in graph.items():
        node["id"] = hashlib.sha256(path.relative_to(source).as_posix().encode()).hexdigest()[:16]
        node["roles"] = set()
        node["built"] = path == source / "packages" / node["manifest"]["name"].removeprefix("@opencode/") and node["manifest"]["name"] in {"@opencode/" + n for n in PACKAGES}
        if node["built"] and not (path / "dist").is_dir():
            raise CohortError(f"Built dist is missing: {path}")
    for role, selected in (("runtime", runtime_roots), ("build-only", tooling_roots)):
        todo = list(selected.values())
        while todo:
            node = graph[within(todo.pop(), source)]
            if role in node["roles"]:
                continue
            node["roles"].add(role)
            todo.extend(dep["path"] for dep in node["dependencies"].values())
    output.mkdir(parents=True)
    (output / "INCOMPLETE").write_text("Preparation has not committed its inventory.\n", encoding="utf-8")
    packages, files, links = [], [], []
    for path, node in sorted(graph.items(), key=lambda pair: pair[1]["id"]):
        target = output / "p" / node["id"]
        if node["built"]:
            copy_payload(path / "dist", target / "dist", path)
            write_json(target / "package.json", staged_manifest(node, graph))
            license_path = path / "LICENSE"
            if not license_path.is_file():
                license_path = source / "LICENSE"
            if license_path.is_file():
                shutil.copyfile(license_path, target / "LICENSE")
        else:
            copy_payload(path, target, path)
        package_files = []
        for item in sorted(target.rglob("*")):
            if item.is_file():
                record = {"path": item.relative_to(output).as_posix(), "sha256": digest(item),
                          "size": item.stat().st_size, "package": node["id"]}
                files.append(record)
                package_files.append(record)
        tree_hash = hashlib.sha256(json.dumps(
            [{"path": row["path"].split("/", 2)[2], "sha256": row["sha256"], "size": row["size"]}
             for row in package_files], sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        dependencies = []
        for name, dep in node["dependencies"].items():
            dep_id = graph[dep["path"]]["id"]
            links.append({"path": str(target / "node_modules" / name), "target": str(output / "p" / dep_id)})
            dependencies.append({"name": name, "target": dep_id, "kinds": dep["kinds"], "requested": dep["requested"]})
        manifest = node["manifest"]
        packages.append({
            "id": node["id"], "name": manifest["name"], "version": manifest["version"],
            "source": path.relative_to(source).as_posix(), "path": target.relative_to(output).as_posix(),
            "source_manifest_sha256": digest(path / "package.json"), "tree_sha256": tree_hash,
            "file_count": len(package_files), "declared_license": manifest.get("license", manifest.get("licenses")),
            "license_files": [row["path"] for row in package_files if re.search(r"(?:^|/)(?:licen[sc]e|notice|copying|copyright|third.party)", row["path"], re.I)],
            "engines": manifest.get("engines", {}), "roles": sorted(node["roles"]),
            "payload": "built-dist" if node["built"] else "installed-bytes",
            "dependencies": dependencies, "missing_optional": node["missing"],
        })
    for name, path in roots.items():
        package_name(name)
        links.append({"path": str(output / "node_modules" / name),
                      "target": str(output / "p" / graph[within(path, source)]["id"])})
    create_links(links, output)
    write_json(output / "package.json", {
        "name": "renulus-opencode-cohort", "private": True, "type": "module",
        "dependencies": {name: graph[within(path, source)]["manifest"]["version"]
                         for name, path in runtime_roots.items()},
        "devDependencies": {name: graph[within(path, source)]["manifest"]["version"]
                            for name, path in tooling_roots.items()},
    })
    inventory = {
        "schema": 1, "status": "materialized-developer-cohort", "relocation_acceptance": "H20-pending",
        "link_kind": "internal-absolute-junction" if os.name == "nt" else "internal-relative-symlink",
        "runtime_roots": sorted(runtime_roots), "build_only_roots": sorted(tooling_roots),
        "packages": packages, "files": files,
        "links": [{"path": Path(link["path"]).relative_to(output).as_posix(),
                   "target": Path(link["target"]).relative_to(output).as_posix()} for link in links],
    }
    write_json(output / "inventory.json", inventory)
    write_json(output / "MATERIALIZED.json", {"inventory_sha256": digest(output / "inventory.json"),
                                              "packages": len(packages), "files": len(files)})
    return inventory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("materialize", "record", "verify", "recipe"))
    parser.add_argument("--source", type=Path, default=Path("C:/Renulus/scratch/ocf/src"))
    parser.add_argument("--output", type=Path, default=Path("C:/Renulus/scratch/ocf/cohort"))
    parser.add_argument("--node", type=Path, default=Path("C:/Renulus/scratch/ocf/runtime/node.exe"))
    parser.add_argument("--source-archive", type=Path)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parents[1] / "upstream/opencode/cohort.json")
    args = parser.parse_args(argv)
    if args.command == "recipe":
        print(json.dumps({
            "source_commit": SHA, "artifacts": ARTIFACTS, "source_file_pins": SOURCE_PINS,
            "source": str(args.source), "output": str(args.output),
            "bootstrap": BUILD_BOOTSTRAP,
            "install_argv": ["bun", "install", "--frozen-lockfile", "--ignore-scripts"] +
                [value for name in (*PACKAGES, "theme", "httpapi-codegen", "http-recorder", "script")
                 for value in ("--filter", "@opencode/" + name)],
            "build_argv_in_order": [["bun", "run", "--cwd", "packages/" + name, "build"] for name in PACKAGES],
            "notes": ["Acquisition and builds are explicit parent actions, never run by materialize.",
                      "Apply the documented root .bin/TypeScript junctions and exact mime-types build bootstrap first.",
                      "Fresh-source bootstrap is not automated or replayed; see upstream/opencode/UPSTREAM.md.",
                      "No new npm graph, source patches, trust changes or full/global install.",
                      "Use Node 26.4.0 alone on the host PATH; Bun and compiler are build-only.",
                      "Preserve source lock and patched installed bytes; H20 relocation/packaging remains pending."],
        }, indent=2))
        return 0
    try:
        if args.command == "verify":
            result = verify_cohort(args.output)
            print(json.dumps({"verified": str(args.output), "packages": len(result["packages"]),
                              "inventory_sha256": digest(args.output / "inventory.json")}))
            return 0
        source = args.source.resolve(strict=True)
        validate_manifest_destination(args.manifest, source, args.output, args.node, args.source_archive)
        validate_source(source)
        if not args.node.is_file() or digest(args.node) != ARTIFACTS["node"]["exe_sha256"]:
            raise CohortError("Pinned Node 26.4.0 executable hash mismatch")
        if args.source_archive and digest(args.source_archive) != ARTIFACTS["source"]["sha256"]:
            raise CohortError("Pinned source archive hash mismatch")
        if args.command == "materialize":
            runtime, tooling = selected_roots(source)
            prepare_cohort(source, args.output, runtime, tooling)
        result = record_provenance(source, args.output, args.node)
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.manifest, {
            "schema": 1, "source_commit": SHA, "artifacts": ARTIFACTS,
            "source_file_pins": SOURCE_PINS,
            "build_bootstrap": BUILD_BOOTSTRAP,
            "source_archive_verified": args.source_archive is not None,
            "node_executable_sha256": digest(args.node),
            "inventory_sha256": digest(args.output / "inventory.json"),
            "inventory": str(args.output / "inventory.json"),
            "status": result["status"], "relocation_acceptance": "H20-pending",
            "runtime_roots": result["runtime_roots"], "build_only_roots": result["build_only_roots"],
            "packages": result["packages"],
            "patches": result["patches"],
            "file_count": len(result["files"]),
            "link_count": len(result["links"]),
            "provenance_status": result["provenance_status"],
            "root_input_files": [row for row in result["files"] if row.get("role") == "provenance"],
        })
        print(json.dumps({"output": str(args.output), "packages": len(result["packages"]),
                          "inventory_sha256": digest(args.output / "inventory.json")}))
        return 0
    except (CohortError, OSError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
