"""Synthetic, explicitly selected originals; no corpus or installed-user state."""
import base64
from contextlib import closing
import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest

from renulus.knowledge.models import SourceMetadata, own_text_rights
from renulus.server import create_app
from renulus.storage.backup import snapshot_in
from renulus.storage.recovery_files import remove_owned_tree


def text_pdf(text):
    """A complete one-page PDF, including a valid xref table."""
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 40 740 Td ({text}) Tj ET".encode("ascii")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    data, offsets = bytearray(b"%PDF-1.4\n"), [0]
    for index, body in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(str(index).encode() + b" 0 obj\n" + body + b"\nendobj\n")
    xref = len(data)
    data.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(data)


@pytest.fixture
def source(tmp_path):
    app = create_app(tmp_path / "source")
    services = app.state.services
    inputs = tmp_path / "selected-synthetic-inputs"
    inputs.mkdir()
    payloads = {
        "ckd.txt": b"SYNTHETIC CKD learning note: original renal source with units and provenance.\n",
        "dialysis.md": b"# Synthetic dialysis study\nThis is backup verification material, not clinical advice.\n",
        "transplant.pdf": text_pdf("SYNTHETIC transplant study attachment - backup round trip"),
        "glomerular.png": base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aK1sAAAAASUVORK5CYII="),
    }
    selected = []
    for name, data in payloads.items():
        path = inputs / name
        path.write_bytes(data)
        imported = services.registry["knowledge"].import_file(path, rights=own_text_rights(),
            metadata=SourceMetadata(source_id="R02", edition="Synthetic recovery 1", topic_ids=[path.stem]),
            process=False)
        selected.append({**imported, "input": path, "bytes": data})
    services.db.execute("INSERT INTO preferences VALUES(?,?,?)", ("runtime.selected_provider", "SYNTHETIC_PROVIDER_SENTINEL", "2026-10-04T21:00:00+00:00"))
    services.db.execute("INSERT INTO preferences VALUES(?,?,?)", ("learn.teaching_style", "guided", "2026-10-04T21:00:00+00:00"))
    services.db.execute("INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)", (
        "evidence_synthetic", "manual-study", None, None, '{"lesson":"Synthetic renal learning evidence"}', "2026-10-04T21:00:00+00:00"))
    (services.paths.state / "protected-synthetic.bin").write_bytes(b"SYNTHETIC_PROTECTED_SENTINEL")
    (services.paths.helpers / "synthetic-weights.bin").write_bytes(b"SYNTHETIC_WEIGHT_SENTINEL")
    (services.paths.indexes / "synthetic-index.bin").write_bytes(b"SYNTHETIC_INDEX_SENTINEL")
    (services.paths.library / "unreferenced.txt").write_bytes(b"SYNTHETIC_UNREFERENCED_SENTINEL")
    return services, selected


@pytest.fixture
def target(tmp_path):
    return create_app(tmp_path / "target").state.services


def zip_bytes(services):
    recovery = services.registry["data_recovery"]
    directory, _ = recovery.backup()
    try:
        return (directory / "backup.zip").read_bytes()
    finally:
        remove_owned_tree(services.paths, directory)


def preview(services, data):
    recovery = services.registry["data_recovery"]
    identifier, directory = recovery.begin_preview()
    keep = False
    try:
        (directory / "input.zip").write_bytes(data)
        result = recovery.complete_preview(identifier, directory)
        keep = True
        return result
    finally:
        recovery.end_upload(directory, keep=keep)


def restore(services, data):
    checked = preview(services, data)
    return services.registry["data_recovery"].restore_preview(
        checked["preview_token"], checked["exported_at"], True)


def state(services):
    with closing(services.db.connect()) as conn:
        snapshot = snapshot_in(conn)
    return snapshot["records"], {
        path.relative_to(services.paths.library).as_posix(): path.read_bytes()
        for path in services.paths.library.rglob("*") if path.is_file()}


def forge(data, change):
    """Repack a forged archive with valid ZIP CRCs and updated record digest."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = {info.filename: archive.read(info) for info in archive.infolist()}
    manifest = json.loads(members["manifest.json"])
    bundle = json.loads(members["records.json"])
    change(manifest, bundle, members)
    members["records.json"] = json.dumps(bundle, separators=(",", ":")).encode()
    manifest["records"]["bytes"] = len(members["records.json"])
    manifest["records"]["sha256"] = hashlib.sha256(members["records.json"]).hexdigest()
    members["manifest.json"] = json.dumps(manifest, separators=(",", ":")).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, contents in members.items():
            archive.writestr(name, contents)
    return output.getvalue()
