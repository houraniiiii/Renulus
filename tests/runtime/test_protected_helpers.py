import hashlib
import json

import pytest

from renulus.contracts import ApiError
from renulus.runtime.helpers import HelperAssets
from renulus.runtime.protected import ConnectionStore, WindowsDPAPI


def test_actual_windows_dpapi_round_trip_is_profile_bound(app_paths, tmp_path):
    store = ConnectionStore(app_paths.root, app_paths.state)
    data = {"version": 1, "host_id": "synthetic-host", "connections": {
        "opencode-go": {"access_token": "synthetic-sensitive-key"}}, "selected_provider": "opencode-go"}
    store.save(data)
    assert store.load() == data
    assert b"synthetic-sensitive-key" not in store.path.read_bytes()
    other = ConnectionStore(tmp_path / "other", tmp_path / "other" / "state")
    with pytest.raises(ApiError):
        WindowsDPAPI().unprotect(store.path.read_bytes(), other.entropy)


def test_helpers_fail_closed_until_complete_hash_manifest_is_valid(app_paths):
    helpers = HelperAssets(app_paths)
    assert helpers.status()["embedding"] == {"ready": False, "code": "helper_assets_missing"}
    model = app_paths.helpers / "fastembed" / "bge-small-en-v1.5"
    model.mkdir(parents=True)
    files = []
    for name, payload in (("model_optimized.onnx", b"synthetic-model"), ("tokenizer.json", b"{}"),
                          ("config.json", b"{}"), ("tokenizer_config.json", b"{}"),
                          ("special_tokens_map.json", b"{}")):
        path = model / name
        path.write_bytes(payload)
        files.append({"path": path.relative_to(app_paths.helpers).as_posix(),
                      "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
    manifest = {"version": 1, "groups": {"embedding": {"model_id": "BAAI/bge-small-en-v1.5",
        "source_url": "https://huggingface.co/qdrant/bge-small-en-v1.5-onnx-q", "revision": "synthetic-test", "files": files}}}
    (app_paths.helpers / "manifest.json").write_text(json.dumps(manifest))
    helpers = HelperAssets(app_paths, expected_manifest=manifest)
    config = helpers.embedding_config()
    assert config["dimensions"] == 384 and config["max_tokens"] == 512
    assert config["local_files_only"] is True
    (model / "model_optimized.onnx").write_bytes(b"tampered-model!")
    with pytest.raises(ApiError) as error:
        helpers.embedding_config()
    assert error.value.code == "helper_assets_invalid"


def test_profile_cannot_rewrite_both_assets_and_manifest_to_pass_readiness(app_paths):
    payload = b"synthetic-replacement-model"
    model = app_paths.helpers / "fastembed" / "bge-small-en-v1.5"
    model.mkdir(parents=True)
    (model / "model_optimized.onnx").write_bytes(payload)
    manifest = {"version": 1, "groups": {"embedding": {"model_id": "BAAI/bge-small-en-v1.5",
        "source_url": "https://huggingface.co/Qdrant/bge-small-en-v1.5-onnx-Q", "revision": "unreviewed",
        "files": [{"path": "fastembed/bge-small-en-v1.5/model_optimized.onnx", "size": len(payload),
                   "sha256": hashlib.sha256(payload).hexdigest()}]}}}
    (app_paths.helpers / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ApiError) as error:
        HelperAssets(app_paths).embedding_config()
    assert error.value.code == "helper_assets_invalid"


def test_helper_manifest_cannot_escape_profile(app_paths):
    (app_paths.helpers / "manifest.json").write_text(json.dumps({"version": 1, "groups": {
        "embedding": {"source_url": "https://example.invalid", "revision": "synthetic",
                      "files": [{"path": "../../outside", "size": 1, "sha256": "0" * 64}]}}}))
    with pytest.raises(ApiError) as failure:
        HelperAssets(app_paths).embedding_config()
    assert failure.value.code == "helper_assets_invalid"
