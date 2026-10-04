"""Selected native engines under file-write and external-connection denial."""
import builtins
import io
import os
from pathlib import Path
import socket
import warnings

import pytest

from test_offline_engines import live_repository, _pdf_bytes


def inventory(root):
    return {str(path.relative_to(root)): (path.stat().st_size, path.stat().st_mtime_ns)
            for path in root.rglob("*") if path.is_file()}


def test_real_documentstream_text_native_scanned_pdf_and_image_never_write(live_repository, monkeypatch, caplog):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (1200, 350), "white")
    ImageDraw.Draw(image).text((40, 80), "Transplant rejection biopsy review", fill="black",
        font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 38))
    png, scanned = io.BytesIO(), io.BytesIO()
    image.save(png, format="PNG")
    image.save(scanned, format="PDF", resolution=150)
    inputs = [(b"TEMPORARY_SENTINEL Dialysis fistula teaching", "private-title.txt", False),
              (_pdf_bytes("TEMPORARY_SENTINEL Dialysis access review"), "private-title.pdf", None),
              (scanned.getvalue(), "private-title.pdf", None),
              (png.getvalue(), "private-title.png", True)]
    extractor = live_repository.extractor
    before = inventory(live_repository.paths.root)
    original_open, original_io_open, original_os_open = builtins.open, io.open, os.open
    attempts = []
    def deny_open(original):
        def checked(file, mode="r", *args, **kwargs):
            if isinstance(mode, str) and any(value in mode for value in ("w", "a", "x", "+")):
                attempts.append(str(file))
                raise AssertionError("Temporary extraction attempted a file write")
            return original(file, mode, *args, **kwargs)
        return checked
    def checked_os_open(path, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            attempts.append(str(path))
            raise AssertionError("Temporary extraction attempted a low-level file write")
        return original_os_open(path, flags, *args, **kwargs)
    def denied(*args, **kwargs):
        attempts.append(str(args[0]) if args else "filesystem mutation")
        raise AssertionError("Temporary extraction attempted a filesystem mutation")
    results = []
    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", deny_open(original_open))
        guard.setattr(io, "open", deny_open(original_io_open))
        guard.setattr(os, "open", checked_os_open)
        for name in ("mkdir", "makedirs", "remove", "unlink", "rename", "replace", "rmdir"):
            guard.setattr(os, name, denied)
        # The extraction seam does not use LanceDB/asyncio; no sockets are needed.
        guard.setattr(socket.socket, "connect", denied)
        guard.setattr(socket.socket, "connect_ex", denied)
        with warnings.catch_warnings(record=True) as recorded:
            for data, filename, used in inputs:
                result = extractor.extract_bytes(data, filename, "PRIVATE_TITLE_SENTINEL")
                assert result.passages and result.ocr == {"used": used, "confidence": None}
                results.append(result)
            assert not any("TEMPORARY_SENTINEL" in str(item.message) or "PRIVATE_TITLE_SENTINEL" in str(item.message) for item in recorded)
    assert not attempts, attempts
    assert inventory(live_repository.paths.root) == before
    assert all("private-title" not in str(result.document.get("origin", {})) for result in results)
    assert not any("PRIVATE_TITLE_SENTINEL" in record.message or "TEMPORARY_SENTINEL" in record.message or "private-title" in record.message for record in caplog.records)
    assert all(p["locators"] and p["locators"][0]["page"] == 1 for result in results[1:] for p in result.passages)


def test_byte_scope_capability_requires_prepared_verified_helpers(live_repository):
    assert callable(live_repository.extract_bytes)
    assert live_repository.capabilities()["temporary_extraction"] is True
    live_repository.services.registry["helpers"].startup.close()
    assert live_repository.capabilities()["temporary_extraction"] is False
    from renulus.contracts import ApiError
    with pytest.raises(ApiError) as caught:
        live_repository.extract_bytes(b"PRIVATE_SENTINEL", "private.txt", "Private")
    assert caught.value.code == "temporary_extraction_unavailable"
