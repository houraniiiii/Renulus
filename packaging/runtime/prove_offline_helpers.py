"""Development-only real CPU proof using provisioned, hash-validated public assets."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
from unittest.mock import patch

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["MEM0_TELEMETRY"] = "false"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))

from renulus.runtime.helpers import HelperAssets
from renulus.storage import AppPaths


def native_pdf(path: Path):
    lines = ["Renulus synthetic cross-domain education", "CKD: review albuminuria and eGFR trends.",
             "Dialysis: consider potassium and volume balance.", "Transplantation: learn rejection mechanisms.",
             "Glomerular disease: inspect haematuria and proteinuria.",
             "Electrolytes: review sodium and water balance."]
    text = "BT /F1 13 Tf 50 750 Td " + " ".join(
        ("0 -28 Td " if index else "") + "(" + line + ") Tj" for index, line in enumerate(lines)) + " ET"
    bodies = [b"<< /Type /Catalog /Pages 2 0 R >>",
              b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
              b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
              b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
              b"<< /Length " + str(len(text)).encode() + b" >>\nstream\n" + text.encode() + b"\nendstream"]
    data = b"%PDF-1.4\n"
    offsets = [0]
    for index, body in enumerate(bodies, 1):
        offsets.append(len(data))
        data += str(index).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    start = len(data)
    data += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    data += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(start).encode() + b"\n%%EOF\n"
    path.write_bytes(data)


def scanned_pdf(path: Path):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (1600, 1200), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 38)
    lines = ["Renulus synthetic dialysis learning", "Dialysis review: potassium and fluid balance.",
             "CKD education: albuminuria and kidney function.", "Transplantation education: rejection mechanisms."]
    for index, line in enumerate(lines):
        draw.text((80, 100 + index * 110), line, fill="black", font=font)
    image.save(path, "PDF", resolution=150.0)


def prove(profile: Path) -> dict:
    paths = AppPaths.create(profile, Path(__file__).resolve().parents[2])
    os.environ["HF_HOME"] = str(paths.cache / "huggingface")
    os.environ["MEM0_DIR"] = str(paths.state / "mem0")
    os.environ["TMP"] = os.environ["TEMP"] = str(paths.cache)
    helpers = HelperAssets(paths)
    embedding = helpers.embedding_config()
    document = helpers.docling_config()
    print("Validated all helper hashes", flush=True)
    import psutil
    process = psutil.Process()
    peak = {"rss": process.memory_info().rss}
    finished = threading.Event()
    def sample_memory():
        while not finished.wait(0.05):
            peak["rss"] = max(peak["rss"], process.memory_info().rss)
    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    started = time.perf_counter()
    network_attempts = []
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    def local_only(original, connection, address):
        if isinstance(address, tuple):
            try:
                if ipaddress.ip_address(address[0]).is_loopback:
                    return original(connection, address)
            except ValueError:
                pass
        network_attempts.append("blocked")
        raise RuntimeError("Offline helper proof refuses network connections")

    result = {"verified_on": "2026-10-04", "python": sys.version.split()[0],
              "platform": "Windows x64", "embedding_fingerprint": embedding["fingerprint"],
              "docling_fingerprint": document["fingerprint"], "cpu_threads": 2}
    try:
        with patch.object(socket.socket, "connect", lambda connection, address: local_only(original_connect, connection, address)), \
             patch.object(socket.socket, "connect_ex", lambda connection, address: local_only(original_connect_ex, connection, address)):
            from fastembed import TextEmbedding
            model = TextEmbedding(model_name=embedding["model_id"],
                specific_model_path=str(embedding["model_path"]),
                cache_dir=str(embedding["cache_dir"]), local_files_only=True,
                threads=2, providers=["CPUExecutionProvider"], cuda=False)
            vectors = list(model.embed(["CKD albuminuria risk and nephrology learning",
                                       "Dialysis potassium and fluid balance"]))
            assert len(vectors) == 2 and all(vector.shape == (384,) for vector in vectors)
            result["embedding"] = {"passed": True, "vectors": len(vectors), "dimensions": 384,
                                   "model_id": embedding["model_id"]}
            print("Real offline CPU embedding passed", flush=True)

            from docling.datamodel.base_models import InputFormat, ConversionStatus
            from docling.datamodel.pipeline_options import (PdfPipelineOptions, RapidOcrOptions,
                AcceleratorOptions, AcceleratorDevice)
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling_core.transforms.chunker import HybridChunker
            from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
            options = PdfPipelineOptions(artifacts_path=document["artifacts_path"],
                enable_remote_services=False, do_ocr=True, do_table_structure=True,
                do_picture_description=False, do_picture_classification=False,
                do_code_enrichment=False, do_formula_enrichment=False,
                accelerator_options=AcceleratorOptions(num_threads=2, device=AcceleratorDevice.CPU),
                ocr_options=RapidOcrOptions(lang=["en"], backend="onnxruntime",
                    rapidocr_params=document["rapidocr_params"],
                    det_model_path=str(document["ocr_path"] / "det.onnx"),
                    rec_model_path=str(document["ocr_path"] / "rec.onnx"),
                    cls_model_path=str(document["ocr_path"] / "cls.onnx")))
            converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
            native = paths.cache / "synthetic-native.pdf"
            scanned = paths.cache / "synthetic-scanned.pdf"
            native_pdf(native)
            scanned_pdf(scanned)
            documents = []
            for label, file in (("native_pdf", native), ("scanned_pdf", scanned)):
                before = time.perf_counter()
                conversion = converter.convert(file)
                assert conversion.status == ConversionStatus.SUCCESS
                text = conversion.document.export_to_markdown()
                assert "dialysis" in text.lower() and "albuminuria" in text.lower()
                documents.append(conversion.document)
                result[label] = {"passed": True, "seconds": round(time.perf_counter() - before, 3),
                                 "pages": len(conversion.document.pages), "characters": len(text)}
                print(label + " real CPU extraction passed", flush=True)
            tokenizer = HuggingFaceTokenizer.from_pretrained(embedding["model_path"],
                max_tokens=embedding["max_tokens"], local_files_only=True)
            chunker = HybridChunker(tokenizer=tokenizer)
            chunks = list(chunker.chunk(dl_doc=documents[0]))
            assert chunks and all(chunker.tokenizer.count_tokens(chunk.text) <= 512 for chunk in chunks)
            assert all(chunk.meta.doc_items for chunk in chunks)
            chunk_vectors = list(model.embed([chunk.text for chunk in chunks]))
            import lancedb
            database = lancedb.connect(str(paths.indexes / "offline-library-proof"))
            table = database.create_table("synthetic", data=[
                {"id": str(index), "text": chunk.text, "vector": vector.tolist()}
                for index, (chunk, vector) in enumerate(zip(chunks, chunk_vectors))], mode="overwrite")
            found = table.search(chunk_vectors[0]).limit(1).to_list()
            assert found and "CKD" in found[0]["text"]
            result["chunking_index"] = {"passed": True, "chunks": len(chunks),
                "page_locators": sorted({prov.page_no for chunk in chunks for item in chunk.meta.doc_items for prov in item.prov}),
                "index_rows": table.count_rows()}
            assert not network_attempts
        result["network_connection_attempts"] = len(network_attempts)
        result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        result["peak_process_rss_bytes"] = peak["rss"]
        result["all_passed"] = True
        return result
    finally:
        finished.set()
        sampler.join(timeout=1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = prove(args.profile)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output), flush=True)
