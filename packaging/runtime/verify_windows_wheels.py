"""Check a resolved proposal against official PyPI wheels, without downloading models."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import urllib.request

from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import parse_wheel_filename


def verify(requirements: Path) -> dict:
    pins = re.findall(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)", requirements.read_text(), re.MULTILINE)
    tags = set(cpython_tags((3, 14), ["cp314"], ["win_amd64"]))
    tags.update(compatible_tags((3, 14), "cp314", ["win_amd64"]))

    def package(pin):
        name, version = pin
        url = "https://pypi.org/pypi/" + name + "/" + version + "/json"
        with urllib.request.urlopen(url, timeout=30) as response:
            metadata = json.load(response)
        matches = []
        for artifact in metadata["urls"]:
            if artifact["packagetype"] != "bdist_wheel" or artifact.get("yanked"):
                continue
            _, _, _, wheel_tags = parse_wheel_filename(artifact["filename"])
            if not wheel_tags.isdisjoint(tags):
                matches.append(artifact)
        if not matches:
            return {"package": name, "version": version, "available": False, "source": url}
        artifact = sorted(matches, key=lambda item: item["filename"])[0]
        return {"package": name, "version": version, "available": True,
                "filename": artifact["filename"], "sha256": artifact["digests"]["sha256"],
                "bytes": artifact["size"], "requires_python": metadata["info"]["requires_python"],
                "source": url}

    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(package, pins))
    return {"verified_on": "2026-10-04", "python": "CPython 3.14", "platform": "Windows x64",
            "package_count": len(rows), "all_wheels_available": all(row["available"] for row in rows),
            "packages": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("requirements", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    result = verify(arguments.requirements)
    arguments.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "packages"}))
    if not result["all_wheels_available"]:
        print(json.dumps([row for row in result["packages"] if not row["available"]]))
        raise SystemExit(1)
