# SPDX-License-Identifier: MIT
"""Measured product disk recovery, with an opt-in 13k-document synthetic run.

RENULUS_RECOVERY_SCALE=1 selects 13,000 documents / 130,000 passages.
Ordinary checks use 156 / 12,000 and exceed the old JSON byte budget; the opt-in
run also exceeds the old record budget. Every child owns fresh synthetic state.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def measurement_helpers():
    spec = importlib.util.spec_from_file_location("capacity_measurement_helpers", ROOT / "scripts/measure_recovery_capacity.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker(work, mode):
    helper = measurement_helpers()
    helper.directory(work)
    config = json.loads((work / "synthetic-product.json").read_text(encoding="utf-8"))
    assert config.pop("synthetic_product_only") is True
    from renulus.server import create_app
    from renulus.storage.recovery_segmented import file_digest
    from renulus.storage.recovery_files import remove_owned_tree
    if mode == "seed":
        with helper.app_services(ROOT, work) as services:
            helper.synthetic_fixture(services, config)
        return {"status": "seeded"}
    path = work / ("s" if mode == "export" else "t_" + mode)
    if mode != "export":
        assert not path.exists()
    services = create_app(path, source_root=ROOT).state.services
    recovery = services.registry["data_recovery"]
    try:
        with helper.Measurement(work) as measured:
            if mode == "export":
                directory, manifest = recovery.backup(format_version=2)
                result = {"format_version": manifest["format_version"],
                    "canonical_bytes": manifest["canonical"]["bytes"], "record_count": manifest["canonical"]["records"],
                    "tables": manifest["canonical"]["tables"], "segments": len(manifest["canonical"]["segments"])}
            else:
                token, directory = recovery.begin_preview()
                shutil.copyfile(work / "product.zip", directory / "input.zip")
                checked = recovery.complete_preview(token, directory)
                recovery.end_upload(directory, keep=True)
                if mode == "preview":
                    result = {"format_version": checked["format_version"], "record_count": checked["record_count"],
                        "canonical_bytes": checked["canonical_bytes"]}
                    recovery.discard_preview(token)
                else:
                    result = recovery.restore_preview(token, checked["exported_at"], True)
        result["measurement"] = measured.report
        if mode == "export":
            shutil.copyfile(directory / "backup.zip", work / "product.zip")
            result["archive"] = file_digest(work / "product.zip")
            remove_owned_tree(services.paths, directory)
        if mode == "restore":
            assert services.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_documents")["n"] == config["documents"]
            assert services.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_passages")["n"] == config["passages"]
            assert services.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_source_status_events")["n"] == 1
            last = services.db.fetch_one("SELECT * FROM knowledge_passages ORDER BY id DESC LIMIT 1")
            assert last["id"] == f"pass_{config['passages'] - 1:010d}" and "SYNTHETIC" in last["text"]
            assert json.loads(last["locators_json"])[0]["item_id"].startswith("#/texts/")
        return result
    finally:
        import asyncio
        services.registry["knowledge_worker"].stop(timeout=5)
        services.registry["knowledge"].index.close()
        asyncio.run(services.registry["memory"].close())
        asyncio.run(services.registry["provider"].close())


def test_product_disk_round_trip_measurement_refuses_whole_corpus_ram_growth(tmp_path):
    work = tmp_path / "product-capacity"
    assert not work.exists()
    work.mkdir()
    large = os.environ.get("RENULUS_RECOVERY_SCALE") == "1"
    config = {"synthetic_product_only": True, "documents": 13000 if large else 156,
        "passages": 130000 if large else 12000, "text_bytes": 1536}
    (work / "synthetic-product.json").write_text(json.dumps(config), encoding="utf-8")
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "runtime")}
    results = {}
    for mode in ("seed", "export", "preview", "restore"):
        child = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), str(work), mode],
            env=environment, capture_output=True, text=True, timeout=1800)
        assert child.returncode == 0, child.stderr + child.stdout
        results[mode] = json.loads(child.stdout)
    report = {"synthetic": config, "source_root": str(ROOT), "work_dir": str(work), **results}
    report_path = work / "product-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    assert results["export"]["canonical_bytes"] > 32 * 1024 * 1024
    assert results["export"]["record_count"] == results["preview"]["record_count"]
    assert results["export"]["segments"] > 1
    assert results["restore"]["format_version"] == 2
    assert results["restore"]["restored_records"] >= config["documents"] * 3 + config["passages"]
    # 16 MiB is a row limit; normal fixture rows are small. This catches a
    # corpus-sized dict/list/JSON or in-memory candidate regression. Native
    # SQLite allocations are measured separately rather than inferred from it.
    for mode in ("export", "preview", "restore"):
        assert results[mode]["measurement"]["python_peak_bytes"] < 16 * 1024 * 1024, (mode, report_path)
    print("Synthetic product resource report:", report_path)


if __name__ == "__main__":
    print(json.dumps(worker(Path(sys.argv[1]), sys.argv[2])))
