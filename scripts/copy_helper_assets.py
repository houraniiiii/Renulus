"""Copy declared public helper artifacts without another model download.

Development/release tooling only; doctors receive these in the application.
The manifest is written last, after both source and copied hashes are checked.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def copy_assets(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target or target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError("Use independent source and target helper directories")
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8-sig"))
    if manifest.get("version") != 1 or set(manifest.get("groups", {})) != {"embedding", "docling", "ocr"}:
        raise ValueError("Expected the selected three-group helper manifest")
    files, totals = [], {}
    for name, group in manifest["groups"].items():
        if not group.get("revision") or not group.get("source_url", "").startswith("https://") or not group.get("files"):
            raise ValueError("Helper provenance is incomplete")
        totals[name] = {"files": len(group["files"]), "bytes": 0, "revision": group["revision"]}
        for record in group["files"]:
            relative = Path(record["path"])
            original, destination = (source / relative).resolve(), (target / relative).resolve()
            if relative.is_absolute() or not original.is_relative_to(source) or not destination.is_relative_to(target):
                raise ValueError("The manifest contains a path outside its helper directory")
            if not original.is_file() or original.stat().st_size != record["size"] or digest(original) != record["sha256"]:
                raise ValueError("An acquired helper artifact failed integrity validation")
            files.append((original, destination, record))
            totals[name]["bytes"] += record["size"]
    if len({str(destination) for _, destination, _ in files}) != len(files):
        raise ValueError("A helper artifact is declared more than once")
    target.mkdir(parents=True, exist_ok=True)
    for original, destination, record in files:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file() and destination.stat().st_size == record["size"] and digest(destination) == record["sha256"]:
            continue
        staging = destination.with_name(destination.name + ".copying")
        shutil.copyfile(original, staging)
        if staging.stat().st_size != record["size"] or digest(staging) != record["sha256"]:
            raise ValueError("A copied helper artifact failed integrity validation")
        staging.replace(destination)
    staging_manifest = target / "manifest.json.copying"
    staging_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    staging_manifest.replace(target / "manifest.json")
    return {"status": "copied-and-verified", "groups": totals, "target": str(target)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    print(json.dumps(copy_assets(args.source, args.target), indent=2))
