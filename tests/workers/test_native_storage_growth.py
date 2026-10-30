# SPDX-License-Identifier: MIT
"""Small real Library journey; checkpoint peaks are observed lower bounds."""
import json
import os
from pathlib import Path
import shutil

from renulus.knowledge.engines import LanceIndex
from renulus.server import create_app
from renulus.workers.native_storage import NativeStorage

from .support import grant


def test_library_append_rebuild_compaction_measurements(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    helpers = Path(os.environ["RENULUS_WORKER_TEST_HELPERS"])
    services = create_app(tmp_path / "synthetic-profile").state.services
    manifest = json.loads((helpers / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["groups"]["embedding"]["files"]:
        destination = services.paths.helpers / entry["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(helpers / entry["path"], destination)
    (services.paths.helpers / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    library = services.registry["knowledge"]
    storage = NativeStorage([services.paths.root], services.paths.root)
    observations = []

    def observe():
        measured = storage.measure()
        observations.append(measured)
        return measured

    for name in ("stage", "build_fts", "optimize", "prepare_retirement"):
        original = getattr(LanceIndex, name)

        def measured_call(self, *args, _original=original, **kwargs):
            observe()
            result = _original(self, *args, **kwargs)
            observe()
            return result

        monkeypatch.setattr(LanceIndex, name, measured_call)

    print("\nsynthetic, uncalibrated — bytes; operation-boundary observed peak")
    print("| Operation | Phase | Logical | Allocated | Unique | Peak allocated |")
    print("| --- | --- | ---: | ---: | ---: | ---: |")
    try:
        for operation in ("Library append", "Rebuild", "Compaction"):
            observations.clear()
            before = observe()
            if operation == "Library append":
                for topic in ("AKI volume assessment", "CKD albuminuria", "transplant rejection"):
                    body = ("SYNTHETIC educational note: " + topic + ".").encode()
                    document = grant(body)
                    assert document["bytes"] == len(body)
                    imported = library.import_text(body.decode(), title=topic, process=False)
                    library.run_job(imported["job"]["id"])
                    assert services.db.fetch_one("SELECT status FROM knowledge_revisions WHERE id=?",
                                                 (imported["revision_id"],))["status"] == "ready"
            elif operation == "Rebuild":
                assert library.rebuild_index()["status"] == "ready"
            else:
                library.index.optimize()
            after = observe()
            peak = max(row["allocated_bytes"] for row in observations)
            for phase, row in (("Before", before), ("After", after)):
                print(f'| {operation} | {phase} | {row["logical_bytes"]} | '
                      f'{row["allocated_bytes"]} | {row["unique_bytes"]} | {peak} |')
            assert peak >= max(before["allocated_bytes"], after["allocated_bytes"])
        assert len(services.db.fetch_all("SELECT id FROM knowledge_documents")) == 3
    finally:
        library.index.close()
