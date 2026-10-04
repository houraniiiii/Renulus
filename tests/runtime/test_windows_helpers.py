"""Native selected-library checks; synthetic vectors are not model inference proof."""
import importlib.metadata

import pytest


def test_selected_cpu_stack_imports_and_native_embedded_store_roundtrips(app_paths, monkeypatch):
    monkeypatch.setenv("MEM0_TELEMETRY", "false")
    monkeypatch.setenv("MEM0_DIR", str(app_paths.state / "mem0"))
    from docling.document_converter import DocumentConverter
    from docling_core.transforms.chunker import HybridChunker
    from fastembed import TextEmbedding
    import lancedb
    import mem0
    import onnxruntime
    import pyarrow as pa
    from qdrant_client import QdrantClient, models
    from tokenizers import Tokenizer
    import torch

    assert torch.version.cuda is None
    assert "CPUExecutionProvider" in onnxruntime.get_available_providers()
    expected = {"docling": "2.133.0", "docling-core": "2.99.0", "fastembed": "0.8.1",
                "lancedb": "0.39.0", "mem0ai": "2.2.1", "onnxruntime": "1.30.0",
                "tokenizers": "0.23.2"}
    for package, version in expected.items():
        assert importlib.metadata.version(package) == version
    model = next(model for model in TextEmbedding.list_supported_models()
                 if model["model"] == "BAAI/bge-small-en-v1.5")
    assert model["dim"] == 384 and model["model_file"] == "model_optimized.onnx"
    vectors = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    database = lancedb.connect(str(app_paths.indexes / "lance-proof"))
    schema = pa.schema([pa.field("id", pa.string()), pa.field("text", pa.string()),
                        pa.field("vector", pa.list_(pa.float32(), 3))])
    table = database.create_table("synthetic", schema=schema, data=[
        {"id": "ckd", "text": "Synthetic CKD education", "vector": vectors[0]},
        {"id": "dialysis", "text": "Synthetic dialysis education", "vector": vectors[1]}])
    assert table.search(vectors[0]).limit(1).to_list()[0]["id"] == "ckd"
    table.create_fts_index("text", use_tantivy=False)
    assert table.search("dialysis", query_type="fts").limit(1).to_list()[0]["id"] == "dialysis"
    table.delete("id = 'ckd'")
    assert table.count_rows() == 1
    qdrant = QdrantClient(path=str(app_paths.indexes / "qdrant-proof"))
    try:
        qdrant.create_collection("synthetic", vectors_config=models.VectorParams(size=3, distance=models.Distance.COSINE))
        qdrant.upsert("synthetic", points=[models.PointStruct(id=1, vector=vectors[0], payload={"topic": "CKD"})])
        assert qdrant.query_points("synthetic", query=vectors[0]).points[0].payload["topic"] == "CKD"
        qdrant.delete("synthetic", points_selector=models.PointIdsList(points=[1]))
        assert qdrant.count("synthetic").count == 0
    finally:
        qdrant.close()
    # Import compatibility is evidence; Mem0 generation/capture remains M5 work.
    assert mem0.Memory and DocumentConverter and HybridChunker and Tokenizer
