"""Inspect a native-saved format-2 ZIP of an owned synthetic profile."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile


def inspect(file: Path, *, expected_id: str, expected_text: str) -> dict:
    with zipfile.ZipFile(file) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("The saved archive contains duplicate members")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != "renulus-full-backup" or manifest.get("format_version") != 2:
            raise ValueError("The native producer did not save a format-2 full backup")
        canonical = manifest["canonical"]
        declared = {"manifest.json"}
        records, expanded, matched = 0, 0, False
        tables = {name: 0 for name in canonical["tables"]}
        for entry in canonical["segments"]:
            name = entry["path"]
            if name in declared or not re.fullmatch(r"canonical/[a-z][a-z0-9_]*/[0-9]{6}[.]jsonl", name):
                raise ValueError("The saved segment path is duplicated or outside canonical data")
            declared.add(name)
            digest, size, count = hashlib.sha256(), 0, 0
            with archive.open(name) as member:
                for line in member:
                    size += len(line)
                    digest.update(line)
                    row = json.loads(line)
                    count += 1
                    if entry["table"] == "memory_facts" and row.get("id") == expected_id:
                        if matched or row.get("text") != expected_text:
                            raise ValueError("The saved synthetic memory row changed or was duplicated")
                        matched = True
            if size != entry["bytes"] or count != entry["records"] or digest.hexdigest() != entry["sha256"]:
                raise ValueError("The saved segment differs from its declared bytes, rows or hash")
            records += count
            expanded += size
            tables[entry["table"]] += count
        for entry in manifest["originals"]:
            name = entry["path"]
            if name in declared or not re.fullmatch(r"library/knowledge/doc_[a-zA-Z0-9_-]{1,100}/rev_[a-zA-Z0-9_-]{1,100}/original[.](pdf|png|jpg|jpeg|tif|tiff|txt|md)", name):
                raise ValueError("The saved original path is duplicated or outside originals")
            declared.add(name)
            digest, size = hashlib.sha256(), 0
            with archive.open(name) as member:
                while block := member.read(64 * 1024):
                    digest.update(block)
                    size += len(block)
            if size != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
                raise ValueError("The saved original differs from its declared bytes or hash")
        if set(names) != declared or records != canonical["records"] or expanded != canonical["bytes"] or tables != canonical["tables"]:
            raise ValueError("The saved archive inventory disagrees with its manifest")
        if not matched:
            raise ValueError("The actual producer omitted the synthetic manual memory row")
        return {"format": manifest["format"], "format_version": manifest["format_version"],
                "schema_version": manifest["schema_version"], "exported_at": manifest["exported_at"],
                "members": len(names), "canonical_records": records, "canonical_bytes": expanded,
                "tables": tables, "originals": len(manifest["originals"]),
                "synthetic_memory_id": expected_id, "synthetic_memory_present": True,
                "omissions": manifest["omissions"],
                "limits": ["Small synthetic native save and manifest integrity, not restore or multi-GiB capacity proof"]}


if __name__ == "__main__":
    request = json.load(sys.stdin)
    file = Path(request["file"]).resolve()
    root = Path(__file__).resolve().parents[1] / "test-results"
    if not file.is_relative_to(root) or file.suffix != ".zip":
        raise ValueError("Native backup inspection is confined to this lane's synthetic ZIP outputs")
    print(json.dumps(inspect(file, expected_id=request["expected_id"], expected_text=request["expected_text"])))
