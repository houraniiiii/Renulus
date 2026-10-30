"""Opt-in selected-helper proofs through the real inherited-stdio subprocess."""
import json
import math
import os
from io import BytesIO
from pathlib import Path

import pytest

from renulus.worker_contracts import HelperPaths
from .support import Process, ROOT, command, config, output, target


@pytest.fixture
def helpers():
    path = os.environ.get("RENULUS_WORKER_TEST_HELPERS")
    if not path:
        pytest.skip("Set RENULUS_WORKER_TEST_HELPERS to explicitly provisioned selected assets")
    root = Path(path)
    assert root.is_absolute() and (root / "manifest.json").is_file()
    return root


def _pdf(text):
    content = ("BT /F1 18 Tf 50 760 Td (" + text + ") Tj ET").encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"]
    data, offsets = bytearray(b"%PDF-1.4\n"), [0]
    for index, value in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode() + value + b"\nendobj\n")
    start = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010} 00000 n \n".encode())
    data.extend(f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode())
    return bytes(data)


def _scan_no_payload(folder, sentinel):
    for path in folder.rglob("*"):
        if path.is_file():
            with path.open("rb") as stream:
                carry = b""
                while block := stream.read(1024 * 1024):
                    assert sentinel not in carry + block, path
                    carry = block[-len(sentinel):]


def test_real_fastembed_docling_hybridchunker_and_no_canonical_state(tmp_path, helpers):
    cache = tmp_path / "cache"
    launch = config(helpers=HelperPaths(helpers_root=str(helpers), cache_root=str(cache), source_root=str(ROOT)))
    sentinel = b"BF00syntheticNoSpillSentinel82716"
    text = sentinel + b"\n\nAKI assessment reviews volume status.\n\nTransplant rejection may require biopsy.\n\nCKD management reviews albuminuria."
    with Process(tmp_path / "process", launch=launch) as worker:
        worker.start()
        g = worker.upload(text)
        result = worker.request(command("document.extract", dict(artifact_handle=g["artifact_handle"],
            artifact_revision=1, offset=0, length=len(text), format="txt", title="Synthetic broad nephrology",
            output=output())), timeout=120)
        assert result["outcome"] == "committed_reference", result
        document = json.loads(worker.read_all(result["result"]))
        assert document["tag"] == "document" and document["passages"]
        assert any(p["locators"] for p in document["passages"])
        texts = [p["context_text"] for p in document["passages"]]
        result2 = worker.request(command("embedding.embed", dict(texts=texts, query=False, output=output())), timeout=120)
        assert result2["outcome"] == "committed_reference", result2
        embeddings = json.loads(worker.read_all(result2["result"]))
        assert embeddings["model_id"] == "BAAI/bge-small-en-v1.5"
        assert len(embeddings["vectors"]) == len(texts)
        assert all(len(v) == 384 and all(math.isfinite(x) for x in v) for v in embeddings["vectors"])
        reference = result["result"]
        chunked = worker.request(command("document.chunk", dict(artifact_handle=reference["artifact_handle"],
            artifact_revision=1,offset=0,length=reference["bytes"],output=output())), timeout=120)
        assert chunked["outcome"] == "committed_reference", chunked
        assert json.loads(worker.read_all(chunked["result"]))["passages"][0]["locators"]
        pdf = _pdf("Synthetic glomerulonephritis proteinuria review")
        g = worker.upload(pdf)
        result = worker.request(command("document.extract", dict(artifact_handle=g["artifact_handle"],
            artifact_revision=1, offset=0, length=len(pdf),format="pdf",title="Synthetic GN PDF",
            output=output( max_bytes=4*1024*1024))), timeout=180)
        assert result["outcome"] == "committed_reference", result
        extracted = json.loads(worker.read_all(result["result"]))
        assert any(loc["page"] == 1 for p in extracted["passages"] for loc in p["locators"])
        from PIL import Image, ImageDraw, ImageFont
        image = Image.new("RGB", (1200, 250), "white")
        ImageDraw.Draw(image).text((30, 70), "Dialysis fistula access review", fill="black",
            font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 40))
        stream = BytesIO()
        image.save(stream, format="PNG")
        body = stream.getvalue()
        g = worker.upload(body)
        result = worker.request(command("document.extract", dict(artifact_handle=g["artifact_handle"],
            artifact_revision=1,offset=0,length=len(body),format="png",title="Synthetic dialysis image",
            output=output(max_bytes=4*1024*1024))), timeout=180)
        assert result["outcome"] == "committed_reference", result
        extracted = json.loads(worker.read_all(result["result"]))
        assert any("fistula" in p["text"].lower() for p in extracted["passages"])
    assert worker.process.returncode == 0
    assert not list(tmp_path.rglob("*.sqlite*"))
    _scan_no_payload(tmp_path, sentinel)


def test_real_temporary_worker_cancel_retains_lease_until_native_return(tmp_path, helpers):
    cache = tmp_path / "cache"
    launch = config(retention="temporary", helpers=HelperPaths(helpers_root=str(helpers),
                         cache_root=str(cache),source_root=str(ROOT)))
    with Process(tmp_path / "process", launch=launch) as worker:
        worker.start()
        value = command("embedding.embed", dict(texts=["BF00temporarySentinelNoDisk61572"],query=False, output=output()),
                        retention="temporary")
        pending = worker.request(value, terminal=False)
        assert pending["outcome"] == "accepted_pending"
        cancel_value = command("worker.settle", {"action":"cancel","target":target(pending)},retention="temporary")
        ack = worker.request(cancel_value, terminal=False)
        assert ack["settlement"]["state"] in ("pending", "settled")
        # Observe the original terminal without resending execution.
        while True:
            matches = [r for r in worker.saved if r["identity"]["request_id"] == value["request_id"]]
            reply = matches[0] if matches else worker.receive(timeout=120)
            if reply["identity"]["request_id"] == value["request_id"] and reply["settlement"]["state"] == "settled":
                break
        assert reply["outcome"] == "cancelled_settled", reply
        assert reply["settlement"]["worker_lease"] == pending["settlement"]["worker_lease"]
    _scan_no_payload(tmp_path, b"BF00temporarySentinelNoDisk61572")
