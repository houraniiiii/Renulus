"""Hash-validated CPU helper paths. Runtime never provisions/downloads assets."""
from __future__ import annotations

import hashlib
import json
import copy
from pathlib import Path

from renulus.contracts import ApiError
from .startup import HelperStartup

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSIONS = 384
EMBEDDING_TOKEN_LIMIT = 512


class HelperAssets:
    def __init__(self, paths, *, expected_manifest: dict | None = None):
        self.paths = paths
        # Production readiness is anchored to the reviewed source/bundle contract,
        # not to hashes which an editable profile manifest could rewrite itself.
        # Explicit injection is for synthetic validator tests/developer packaging.
        self._expected_manifest = copy.deepcopy(expected_manifest)
        self.startup = HelperStartup(paths, self)

    def _expected_group(self, group: str) -> dict:
        if self._expected_manifest is None:
            contract = self.paths.source_root / "packaging" / "runtime" / "helper-assets.json"
            if not contract.is_file():
                raise ApiError("helper_contract_missing", "The reviewed CPU helper manifest is missing from this installation.", 503)
            self._expected_manifest = json.loads(contract.read_text(encoding="utf-8"))
        if self._expected_manifest["version"] != 1:
            raise ValueError("trusted manifest version")
        return self._expected_manifest["groups"][group]

    def _validate(self, group: str) -> tuple[dict, str]:
        root = self.paths.helpers.resolve()
        manifest = root / "manifest.json"
        if not manifest.is_file():
            raise ApiError("helper_assets_missing", "The bundled CPU helper assets are not installed.", 503)
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
            if document["version"] != 1:
                raise ValueError("manifest version")
            metadata = document["groups"][group]
            if metadata != self._expected_group(group):
                raise ValueError("unapproved asset provenance")
            if not metadata["source_url"].startswith("https://") or not metadata["revision"]:
                raise ValueError("source provenance")
            files = metadata["files"]
            if not files:
                raise ValueError("empty group")
            seen = set()
            for record in files:
                relative = Path(record["path"])
                target = (root / relative).resolve()
                if relative.is_absolute() or not target.is_relative_to(root) or record["path"] in seen:
                    raise ValueError("artifact location")
                seen.add(record["path"])
                if not target.is_file():
                    raise ApiError("helper_assets_missing", "A bundled CPU helper artifact is missing.", 503)
                if target.stat().st_size != record["size"]:
                    raise ValueError("artifact size")
                digest = hashlib.sha256()
                with target.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                if digest.hexdigest() != record["sha256"]:
                    raise ValueError("artifact hash")
            fingerprint = hashlib.sha256(json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            return metadata, fingerprint
        except ApiError:
            raise
        except Exception:
            raise ApiError("helper_assets_invalid", "The bundled CPU helper artifacts failed validation. Repair this installation.", 503) from None

    def embedding_config(self) -> dict:
        metadata, fingerprint = self._validate("embedding")
        root = self.paths.helpers / "fastembed" / "bge-small-en-v1.5"
        declared = {record["path"] for record in metadata["files"]}
        tokenizer = root / "tokenizer.json"
        prefix = "fastembed/bge-small-en-v1.5/"
        required = {prefix + name for name in ("model_optimized.onnx", "tokenizer.json",
            "config.json", "tokenizer_config.json", "special_tokens_map.json")}
        if metadata.get("model_id") != EMBEDDING_MODEL or not required.issubset(declared):
            raise ApiError("helper_assets_invalid", "The selected embedding model/tokenizer is not bundled.", 503)
        return {"model_id": EMBEDDING_MODEL, "dimensions": EMBEDDING_DIMENSIONS,
                "max_tokens": EMBEDDING_TOKEN_LIMIT, "model_path": root,
                "tokenizer_path": tokenizer, "cache_dir": self.paths.cache / "fastembed",
                "local_files_only": True, "cpu_threads": 2, "fingerprint": fingerprint}

    def docling_config(self) -> dict:
        metadata, document_hash = self._validate("docling")
        ocr_metadata, ocr_hash = self._validate("ocr")
        document_files = {record["path"] for record in metadata["files"]}
        ocr_files = {record["path"] for record in ocr_metadata["files"]}
        required = {"docling/docling-project--docling-layout-heron/" + name for name in
                    ("config.json", "model.safetensors", "preprocessor_config.json")}
        required.update({"docling/docling-project--docling-models/model_artifacts/tableformer/accurate/" + name for name in
                         ("tableformer_accurate.safetensors", "tm_config.json")})
        if not required.issubset(document_files) or not {"ocr/det.onnx", "ocr/rec.onnx", "ocr/cls.onnx"}.issubset(ocr_files):
            raise ApiError("helper_assets_invalid", "The selected document/OCR artifacts are not fully bundled.", 503)
        return {"artifacts_path": self.paths.helpers / "docling",
                "ocr_path": self.paths.helpers / "ocr", "device": "cpu",
                "cpu_threads": 2,
                "rapidocr_params": {"Global.model_root_dir": str(self.paths.helpers / "ocr"),
                    "EngineConfig.onnxruntime.intra_op_num_threads": 2,
                    "EngineConfig.onnxruntime.inter_op_num_threads": 2},
                "fingerprint": hashlib.sha256((document_hash + ocr_hash).encode()).hexdigest()}

    def status(self) -> dict:
        result = {}
        for name, operation in (("embedding", self.embedding_config), ("docling", self.docling_config)):
            try:
                config = operation()
                result[name] = {"ready": True, "fingerprint": config["fingerprint"]}
            except ApiError as error:
                result[name] = {"ready": False, "code": error.code}
        return result
