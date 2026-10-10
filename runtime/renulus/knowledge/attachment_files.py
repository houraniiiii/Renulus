# SPDX-License-Identifier: MIT
"""Exact attachment-owned path and bounded admission; no document resources."""
from io import BytesIO
import os
from pathlib import Path
import re
import shutil
import warnings

from ..contracts import ApiError
from .engines import MAX_BYTES, MAX_PAGES
from .office import OFFICE_MEDIA, validate_office
from .repository import MEDIA

ATTACHMENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
# Keep the existing Knowledge admission inventory; normalise aliases on disk.
CANONICAL_SUFFIX = {value: suffix for suffix, value in MEDIA.items()}
CANONICAL_SUFFIX.update({"image/jpeg": ".jpg", "image/tiff": ".tiff", "text/html": ".html"})


def admit(filename, data, *, max_bytes=MAX_BYTES):
    suffix = Path(filename).suffix.lower()
    if suffix not in MEDIA:
        raise ApiError("attachment_format_unsupported", "Choose a supported document or image", 415)
    if not data:
        raise ApiError("attachment_empty", "The selected file is empty", 422)
    if len(data) > max_bytes:
        raise ApiError("attachment_limit", "The selected file exceeds this conversation's attachment limit", 413)
    if suffix == ".pdf" and not data.lstrip().startswith(b"%PDF-"):
        raise ApiError("malformed_pdf", "The selected file has no PDF signature", 422)
    if suffix in OFFICE_MEDIA:
        validate_office(data, suffix, max_bytes=max_bytes, max_pages=MAX_PAGES)
    if MEDIA[suffix].startswith("image/"):
        from PIL import Image
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as image:
                    expected = {"image/png": "PNG", "image/jpeg": "JPEG", "image/tiff": "TIFF"}[MEDIA[suffix]]
                    if image.format != expected:
                        raise ValueError("Image signature disagrees with extension")
                    if image.width * image.height > 12_000_000:
                        raise ApiError("reader_image_limit", "This image exceeds the reader pixel limit", 413)
                    image.verify()
        except ApiError:
            raise
        except Exception:
            raise ApiError("attachment_image_invalid", "The selected image cannot be read safely", 422) from None
    return MEDIA[suffix]


def folder(paths, attachment_id):
    if not isinstance(attachment_id, str) or not ATTACHMENT_ID.fullmatch(attachment_id):
        raise ApiError("attachment_id_invalid", "The attachment identifier is invalid", 422)
    library = paths.library.resolve()
    root = paths.library / "attachments"
    target = root / attachment_id
    # A junction or link must never turn this namespace into another folder.
    if root.resolve() != library / "attachments" or target.resolve() != library / "attachments" / attachment_id:
        raise ApiError("attachment_path_invalid", "The attachment folder is unavailable", 409)
    return target


def write_original(paths, attachment_id, media_type, data):
    target = folder(paths, attachment_id)
    target.parent.mkdir(exist_ok=True)
    target.mkdir()  # A generated ID owns a new folder; never overwrite.
    path = target / ("original" + CANONICAL_SUFFIX[media_type])
    try:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        remove_folder(paths, attachment_id)
        raise
    return path


def remove_folder(paths, attachment_id):
    target = folder(paths, attachment_id)
    if target.exists():
        shutil.rmtree(target)
