"""Warm helper dependency imports before input, inside the explicit app profile."""
from __future__ import annotations

import asyncio
import importlib
import os
import sys
import tempfile


EMBEDDING_IMPORTS = (
    "huggingface_hub.file_download",
    "docling_core.transforms.chunker.hybrid_chunker",
    "docling_core.transforms.chunker.tokenizer.base",
    "tokenizers",
    "fastembed",
)
DOCUMENT_IMPORTS = (
    "PIL.Image",
    "docling.datamodel.base_models",
    "docling.datamodel.pipeline_options",
    "docling.datamodel.accelerator_options",
    "docling.document_converter",
    "docling.pipeline.standard_pdf_pipeline",
    "rapidocr",
)


class HelperStartup:
    def __init__(self, paths, assets, *, import_module=importlib.import_module):
        self.paths = paths
        self.assets = assets
        self._import = import_module
        self._environment: dict[str, tuple[str | None, str]] = {}
        self._previous_temp = None
        self._previous_bytecode = False
        self._configured = False
        self._groups: dict[str, dict] = {}

    def configure(self) -> None:
        if self._configured:
            return
        root = self.paths.cache.resolve()
        owned = {name: root / name for name in ("import-temp", "huggingface", "torch", "fastembed")}
        for path in owned.values():
            path.mkdir(parents=True, exist_ok=True)
        settings = {
            "TMPDIR": str(owned["import-temp"]), "TEMP": str(owned["import-temp"]),
            "TMP": str(owned["import-temp"]), "HF_HOME": str(owned["huggingface"]),
            "HF_HUB_CACHE": str(owned["huggingface"] / "hub"),
            "TRANSFORMERS_CACHE": str(owned["huggingface"] / "transformers"),
            "HF_MODULES_CACHE": str(owned["huggingface"] / "modules"),
            "TORCH_HOME": str(owned["torch"]), "FASTEMBED_CACHE_PATH": str(owned["fastembed"]),
            "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
            "TOKENIZERS_PARALLELISM": "false", "RAYON_NUM_THREADS": "2",
            "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2",
            "OPENBLAS_NUM_THREADS": "2", "NUMEXPR_NUM_THREADS": "2",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        self._environment = {name: (os.environ.get(name), value) for name, value in settings.items()}
        os.environ.update(settings)
        # tempfile caches its choice independently of TEMP. Configure both before
        # importing filelock: its cold symlink probe creates throwaway files.
        self._previous_temp = tempfile.tempdir
        tempfile.tempdir = str(owned["import-temp"])
        self._previous_bytecode = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        self._configured = True

    def _warm(self) -> None:
        readiness = self.assets.status()
        for group, modules in (("embedding", EMBEDDING_IMPORTS), ("docling", DOCUMENT_IMPORTS)):
            if not readiness[group]["ready"]:
                self._groups[group] = {"ready": False, "code": readiness[group]["code"]}
                continue
            try:
                for module in modules:
                    self._import(module)
            except Exception:
                # Import failures can disclose paths; no dependency exception or
                # input is persisted. No model/converter is created by warmup.
                self._groups[group] = {"ready": False, "code": "helper_import_failed"}
            else:
                self._groups[group] = {"ready": True, "fingerprint": readiness[group]["fingerprint"]}

    async def start(self) -> None:
        self.configure()
        await asyncio.to_thread(self._warm)

    def status(self) -> dict:
        return {"configured": self._configured, "imports": dict(self._groups),
                "cpu_threads": 2, "downloads": False, "model_instances_created": False,
                "temporary_extraction_verified": False}

    def close(self) -> None:
        if not self._configured:
            return
        # Production has one owned backend/profile per process. Restoration also
        # keeps repeated app lifespans in integration tests from leaking state.
        for name, (previous, value) in self._environment.items():
            if os.environ.get(name) == value:
                if previous is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = previous
        if tempfile.tempdir == str(self.paths.cache.resolve() / "import-temp"):
            tempfile.tempdir = self._previous_temp
        if sys.dont_write_bytecode:
            sys.dont_write_bytecode = self._previous_bytecode
        self._configured = False
