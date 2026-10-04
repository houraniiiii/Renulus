# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import shutil

from renulus.content.validation import coverage_for

PACK = Path(__file__).parents[2] / "content/packs/renulus-foundations/1.0.0"


def read(path, name):
    return json.loads((path / name).read_text(encoding="utf-8"))


def write(path, name, value):
    (path / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def copy_pack(tmp_path, name="pack"):
    path = tmp_path / name
    shutil.copytree(PACK, path)
    return path


def refresh(path, *, coverage=True):
    """Adversarial/synthetic test pack only, never a published repository pack."""
    manifest = read(path, "manifest.json")
    if coverage:
        prior = read(path, "coverage.json")
        result = coverage_for(read(path, "topics.json"), read(path, "cases.json"),
                              read(path, "questions.json"), prior["target_topics"],
                              prior["minimum_questions"])
        write(path, "coverage.json", result)
    for entry in manifest["files"].values():
        entry["sha256"] = hashlib.sha256((path / entry["path"]).read_bytes()).hexdigest()
    write(path, "manifest.json", manifest)


def correction_pack(tmp_path):
    path = copy_pack(tmp_path, "corrected")
    manifest = read(path, "manifest.json")
    manifest["version"] = "1.0.1"
    questions = read(path, "questions.json")
    q = questions[0]
    q["version"] = q["key_version"] = 2
    # Synthetic test correction of wording; no false medical key published.
    q["rationale"] += " Synthetic test revision: wording clarified; intended key unchanged."
    q["correction"] = {"previous_version": 1, "reason": "Synthetic wording correction"}
    manifest["withdrawals"] = [{"question_id": q["id"], "version": 1,
                                  "reason": "Synthetic wording correction", "replacement_version": 2}]
    write(path, "questions.json", questions)
    write(path, "manifest.json", manifest)
    refresh(path)
    return path, q
