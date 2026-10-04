"""Explicit development-only CPU artifact acquisition; never called by the app.

Run with --profile <isolated .local/runtime/profile> --groups embedding docling ocr.
Downloads are allowlisted and byte-bounded. HF files use immutable commit URLs;
RapidOCR files use upstream version URLs plus shipped immutable SHA-256 values.
Existing helper manifests are preserved; failures never publish a ready group.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlparse

import httpx

MAX_FILE = 350 * 1024 * 1024
MAX_TOTAL = 900 * 1024 * 1024
HF_MODELS = {
    "embedding": ("Qdrant/bge-small-en-v1.5-onnx-Q", "aa8f8b060edb00e03bfdd08813a2949946c8ba55",
        "fastembed/bge-small-en-v1.5", ["README.md", "config.json", "model_optimized.onnx",
            "ort_config.json", "special_tokens_map.json", "tokenizer.json", "tokenizer_config.json", "vocab.txt"]),
    "layout": ("docling-project/docling-layout-heron", "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8",
        "docling/docling-project--docling-layout-heron", ["README.md", "config.json", "model.safetensors", "preprocessor_config.json"]),
}


def fetch(helpers: Path, relative: str, url: str, expected=None):
    if urlparse(url).scheme != "https" or urlparse(url).hostname not in ("huggingface.co", "www.modelscope.cn"):
        raise ValueError("Artifact source is not allowlisted")
    target = (helpers / relative).resolve()
    if not target.is_relative_to(helpers):
        raise ValueError("Artifact path is outside the helper bundle")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and expected:
        with target.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() == expected:
                return {"path": relative, "size": target.stat().st_size, "sha256": expected, "source_url": url}
    temporary = target.with_name(target.name + ".partial")
    for attempt in range(3):
        try:
            digest, size = hashlib.sha256(), 0
            with httpx.stream("GET", url, follow_redirects=True, timeout=90) as response:
                response.raise_for_status()
                with temporary.open("wb") as stream:
                    for block in response.iter_bytes(1024 * 1024):
                        size += len(block)
                        if size > MAX_FILE:
                            raise ValueError("Artifact exceeds the development byte limit")
                        digest.update(block)
                        stream.write(block)
            if expected and digest.hexdigest() != expected:
                raise ValueError("Upstream artifact does not match its pinned SHA-256")
            temporary.replace(target)
            return {"path": relative, "size": size, "sha256": digest.hexdigest(), "source_url": url}
        except (httpx.HTTPError, OSError):
            if temporary.exists():
                temporary.unlink()
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
        except BaseException:
            if temporary.exists():
                temporary.unlink()
            raise


def hf_specs(key):
    repo, revision, folder, files = HF_MODELS[key]
    return repo, revision, [(f"{folder}/{name}", f"https://huggingface.co/{repo}/resolve/{revision}/{name}", None) for name in files]


def table_specs():
    # Resolve the version explicitly selected by installed Docling's table model.
    repo = "docling-project/docling-models"
    response = httpx.get(f"https://huggingface.co/api/models/{repo}/revision/v2.3.0", timeout=30)
    response.raise_for_status()
    revision = response.json()["sha"]
    if len(revision) != 40:
        raise ValueError("Table artifact revision is not immutable")
    files = ["README.md", "config.json", "model_artifacts/tableformer/accurate/tableformer_accurate.safetensors", "model_artifacts/tableformer/accurate/tm_config.json"]
    return repo, revision, [(f"docling/docling-project--docling-models/{name}", f"https://huggingface.co/{repo}/resolve/{revision}/{name}", None) for name in files]


def ocr_specs():
    import yaml
    import rapidocr
    from rapidocr.utils.typings import EngineType
    from docling.models.stages.ocr.rapid_ocr_model import _rapidocr_artifacts, _resolve_rapidocr
    resolved = _resolve_rapidocr("en", "onnxruntime")
    artifacts = _rapidocr_artifacts(Path("ocr"), EngineType.ONNXRUNTIME,
        resolved.ppocr_version, resolved.rapidocr_code, model_size="small")
    registry = yaml.safe_load((Path(rapidocr.__file__).parent / "default_models.yaml").read_text(encoding="utf-8"))
    hashes = {}
    def walk(value):
        if isinstance(value, dict):
            if "model_dir" in value and "SHA256" in value:
                hashes[value["model_dir"]] = value["SHA256"]
            for child in value.values():
                walk(child)
    walk(registry)
    specs = []
    for task, artifact in artifacts.items():
        for path, url in artifact.files.items():
            expected = hashes.get(url)
            if not expected:
                raise ValueError("RapidOCR artifact lacks a shipped hash; acquisition refused")
            relative = f"ocr/{task}.onnx" if path == artifact.model_path else "ocr/" + path.name
            specs.append((relative, url, expected))
    return "RapidAI/RapidOCR", "rapidocr-3.9.2-shipped-sha256", specs


def acquire(profile: Path, groups: list[str]):
    profile = profile.resolve()
    parts = [p.lower() for p in profile.parts]
    if ".local" not in parts or "runtime" not in parts:
        raise ValueError("Use an explicit development .local/runtime profile, never an installed user profile")
    helpers = (profile / "helpers").resolve()
    helpers.mkdir(parents=True, exist_ok=True)
    manifest_path = helpers / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {"version": 1, "groups": {}}
    for name, value in manifest["groups"].items():
        # Early development output used arrays for provenance; normalise it to
        # the now-published F0 v1 contract before an atomic manifest write.
        if isinstance(value.get("source_url"), list):
            value["source_url"] = value["source_url"][0]
        if isinstance(value.get("revision"), dict):
            value["revisions"] = value["revision"]
            revisions = value["revisions"]
            value["revision"] = next(iter(revisions.values())) if len(revisions) == 1 else hashlib.sha256(json.dumps(revisions, sort_keys=True).encode()).hexdigest()
        if name == "embedding":
            value["model_id"] = "BAAI/bge-small-en-v1.5"
    for group in groups:
        bundles = [hf_specs("embedding")] if group == "embedding" else ([hf_specs("layout"), table_specs()] if group == "docling" else [ocr_specs()])
        specs = [spec for _, _, items in bundles for spec in items]
        with ThreadPoolExecutor(max_workers=3) as workers:
            files = list(workers.map(lambda spec: fetch(helpers, *spec), specs))
        if sum(x["size"] for x in files) > MAX_TOTAL:
            raise ValueError("Helper group exceeds the development byte limit")
        revisions = {repo: revision for repo, revision, _ in bundles}
        manifest["groups"][group] = {"source_url": ("https://huggingface.co/" if group != "ocr" else "https://www.modelscope.cn/models/") + bundles[0][0],
            "revision": (bundles[0][1] if len(bundles) == 1 else hashlib.sha256(json.dumps(revisions, sort_keys=True).encode()).hexdigest()),
            "revisions": revisions, "files": files}
        if group == "embedding":
            manifest["groups"][group]["model_id"] = "BAAI/bge-small-en-v1.5"
        if sum(x["size"] for value in manifest["groups"].values() for x in value["files"]) > MAX_TOTAL:
            raise ValueError("Combined helper bundle exceeds the development byte limit")
        temporary = manifest_path.with_suffix(".json.partial")
        temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        temporary.replace(manifest_path)
        print(json.dumps({"group": group, "files": len(files), "bytes": sum(x["size"] for x in files), "manifest": str(manifest_path)}), flush=True)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--groups", nargs="+", choices=["embedding", "docling", "ocr"], default=["embedding", "docling", "ocr"])
    args = parser.parse_args()
    acquire(args.profile, args.groups)
