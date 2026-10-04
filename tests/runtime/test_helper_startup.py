import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest

from renulus.runtime.startup import DOCUMENT_IMPORTS, EMBEDDING_IMPORTS, HelperStartup
from renulus.runtime.helpers import HelperAssets


class Assets:
    def __init__(self, ready):
        self.ready = ready

    def status(self):
        return {group: {"ready": self.ready, "fingerprint": "synthetic", "code": "helper_assets_missing"}
                for group in ("embedding", "docling")}


@pytest.mark.asyncio
async def test_startup_owns_temp_cache_and_warms_before_use_then_restores(app_paths, monkeypatch):
    monkeypatch.setenv("TEMP", "synthetic-user-temp")
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    previous_temp, previous_bytecode = tempfile.tempdir, sys.dont_write_bytecode
    imports = []
    def dependency(name):
        assert Path(tempfile.gettempdir()) == app_paths.cache / "import-temp"
        assert os.environ["TEMP"] == str(app_paths.cache / "import-temp")
        assert os.environ["HF_HUB_OFFLINE"] == "1" and os.environ["OMP_NUM_THREADS"] == "2"
        assert sys.dont_write_bytecode
        imports.append(name)
    startup = HelperStartup(app_paths, Assets(True), import_module=dependency)
    try:
        await startup.start()
        assert imports == list(EMBEDDING_IMPORTS + DOCUMENT_IMPORTS)
        assert all(row["ready"] for row in startup.status()["imports"].values())
        assert startup.status()["temporary_extraction_verified"] is False
        assert startup.status()["model_instances_created"] is False
    finally:
        startup.close()
    assert os.environ["TEMP"] == "synthetic-user-temp" and os.environ["HF_HUB_OFFLINE"] == "0"
    assert tempfile.tempdir == previous_temp and sys.dont_write_bytecode == previous_bytecode


@pytest.mark.asyncio
async def test_missing_assets_skip_imports_and_failed_imports_report_honestly(app_paths):
    def unavailable(name):
        raise RuntimeError("synthetic-sensitive-dependency-detail")
    missing = HelperStartup(app_paths, Assets(False), import_module=lambda name: pytest.fail(name))
    try:
        await missing.start()
        assert missing.status()["imports"]["embedding"]["code"] == "helper_assets_missing"
    finally:
        missing.close()
    failed = HelperStartup(app_paths, Assets(True), import_module=unavailable)
    try:
        await failed.start()
        assert failed.status()["imports"]["docling"] == {"ready": False, "code": "helper_import_failed"}
        assert "sensitive" not in json.dumps(failed.status())
    finally:
        failed.close()


def test_real_cold_filelock_probe_is_profile_owned_then_warm_import_has_no_writes(app_paths):
    # Actual installed dependency in a clean interpreter, with no model/torch
    # loading. Audit all startup writes; prohibit even mkdir after warmup.
    script = r'''
import importlib, json, os, sys
from pathlib import Path
from types import SimpleNamespace
from renulus.runtime.startup import HelperStartup
root = Path(sys.argv[1]).resolve()
startup = HelperStartup(SimpleNamespace(cache=root / "cache"), None)
startup.configure()
warmed = False
writes = []
def audit(event, args):
    if event == "open":
        flags = args[2]
        if not isinstance(flags, int) or not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            return
        targets = [args[0]]
    elif event in ("os.mkdir", "os.remove", "os.rmdir"):
        targets = [args[0]]
    elif event in ("os.link", "os.symlink", "os.rename"):
        targets = args[:2]
    else:
        return
    if warmed:
        raise AssertionError("write after dependency warmup: " + event)
    for target in targets:
        if isinstance(target, (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(target)).resolve()
            assert path.is_relative_to(root), "dependency wrote outside explicit profile"
            writes.append({"event": event, "path": path.relative_to(root).as_posix()})
sys.addaudithook(audit)
importlib.import_module("huggingface_hub.file_download")
assert any("probe-source" in record["path"] for record in writes)
warmed = True
importlib.import_module("huggingface_hub.file_download")
importlib.import_module("filelock._strict")
print(json.dumps({"startup_writes": writes, "warm_writes": 0}))
startup.close()
'''
    environment = dict(os.environ, PYTHONPATH=str(app_paths.source_root / "runtime"), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-c", script, str(app_paths.root)],
        capture_output=True, text=True, env=environment, timeout=30)
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["warm_writes"] == 0
    assert all(row["path"].startswith("cache/import-temp/") for row in evidence["startup_writes"])


def test_actual_rapidocr_parser_accepts_local_root_and_two_thread_config(app_paths, monkeypatch):
    # Inspect the exact package config parser without constructing OCR sessions.
    import rapidocr
    from rapidocr.utils.parse_parameters import ParseParams
    metadata = {"files": [{"path": path} for path in (
        "docling/docling-project--docling-layout-heron/config.json",
        "docling/docling-project--docling-layout-heron/model.safetensors",
        "docling/docling-project--docling-layout-heron/preprocessor_config.json",
        "docling/docling-project--docling-models/model_artifacts/tableformer/accurate/tableformer_accurate.safetensors",
        "docling/docling-project--docling-models/model_artifacts/tableformer/accurate/tm_config.json",
        "ocr/det.onnx", "ocr/rec.onnx", "ocr/cls.onnx")]}
    helpers = HelperAssets(app_paths)
    monkeypatch.setattr(helpers, "_validate", lambda group: (metadata, "synthetic"))
    parameters = helpers.docling_config()["rapidocr_params"]
    cfg = ParseParams.load(Path(rapidocr.__file__).parent / "config.yaml")
    cfg = ParseParams.update_batch(cfg, parameters)
    assert cfg.Global.model_root_dir == str(app_paths.helpers / "ocr")
    assert cfg.EngineConfig.onnxruntime.intra_op_num_threads == 2
    assert cfg.EngineConfig.onnxruntime.inter_op_num_threads == 2
