"""Typed inline image inputs; validation and Hermes conversion stay in memory."""
from __future__ import annotations

import base64
from io import BytesIO
from typing import Annotated, Literal
import warnings

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from renulus.contracts import ApiError

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 16 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MAX_IMAGES = 4
MAX_TEXT_CHARS = 1_000_000


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TextInput(_Input):
    type: Literal["text"]
    text: str


class ImageInput(_Input):
    type: Literal["image"]
    media_type: Literal["image/png", "image/jpeg", "image/webp"]
    data: str = Field(min_length=1, max_length=((MAX_IMAGE_BYTES + 2) // 3) * 4, repr=False)
    detail: Literal["auto", "low", "high"] = "auto"


ContentPart = Annotated[TextInput | ImageInput, Field(discriminator="type")]


class MessageInput(_Input):
    role: Literal["system", "user", "assistant"]
    content: str | Annotated[list[ContentPart], Field(min_length=1, max_length=32)]


def _image_size(part: ImageInput) -> int:
    try:
        raw = base64.b64decode(part.data, validate=True)
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            raise ValueError("image size")
        # Pillow is already an approved Hermes/Docling dependency. Never call save
        # or a file/URL loader. A parser failure cannot expose the payload.
        from PIL import Image
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                expected = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}
                if image.format != expected[part.media_type] or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("image format")
                if min(image.size) < 1 or image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValueError("image dimensions")
                image.verify()
        return len(raw)
    except (ImportError, ModuleNotFoundError):
        raise ApiError("image_runtime_missing", "The bundled image parser is not installed. Repair this installation.", 503) from None
    except Exception:
        raise ApiError("invalid_image", "Supply a valid, single-frame PNG, JPEG or WebP within the image limits.") from None


def validate_inputs(messages: list[dict]) -> list[dict]:
    if not isinstance(messages, list) or not 1 <= len(messages) <= 200:
        raise ApiError("invalid_messages", "Supply between 1 and 200 messages.")
    result = []
    text_size = image_size = images = 0
    for message in messages:
        if isinstance(message, dict) and message.get("role") not in ("system", "user", "assistant"):
            raise ApiError("tools_disabled", "Automation and tool messages are disabled.")
        try:
            parsed = MessageInput.model_validate(message)
        except (ValidationError, TypeError):
            raise ApiError("invalid_messages", "Messages contain a role and text or typed inline content parts.") from None
        if isinstance(parsed.content, str):
            text_size += len(parsed.content)
        else:
            for part in parsed.content:
                if isinstance(part, TextInput):
                    text_size += len(part.text)
                else:
                    if parsed.role != "user":
                        raise ApiError("invalid_image_role", "Inline images belong only to user messages.")
                    images += 1
                    if images > MAX_IMAGES:
                        raise ApiError("image_limit", "Supply at most four images per request.")
                    image_size += _image_size(part)
                    if image_size > MAX_TOTAL_IMAGE_BYTES:
                        raise ApiError("image_limit", "The combined image input exceeds 16 MiB.")
        if text_size > MAX_TEXT_CHARS:
            raise ApiError("context_limit", "Shorten the conversation before trying again.")
        result.append(parsed.model_dump())
    return result


def has_images(messages: list[dict]) -> bool:
    return any(isinstance(message["content"], list) and
               any(part["type"] == "image" for part in message["content"]) for message in messages)


def to_hermes_messages(messages: list[dict]) -> list[dict]:
    result = []
    for message in messages:
        content = message["content"]
        if isinstance(content, list):
            content = [{"type": "text", "text": part["text"]} if part["type"] == "text" else
                {"type": "image_url", "image_url": {"url": "data:" + part["media_type"] + ";base64," + part["data"],
                                                  "detail": part["detail"]}} for part in content]
        result.append({"role": message["role"], "content": content})
    return result


def from_hermes_messages(messages: list[dict]) -> list[dict]:
    result = []
    for message in messages:
        content = message.get("content", "")
        if isinstance(content, list):
            parts = []
            for part in content:
                if part.get("type") == "text":
                    parts.append({"type": "text", "text": part["text"]})
                elif part.get("type") == "image_url":
                    image = part["image_url"]
                    header, data = image["url"].split(";base64,", 1)
                    parts.append({"type": "image", "media_type": header.removeprefix("data:"),
                                  "data": data, "detail": image.get("detail", "auto")})
                else:
                    raise ApiError("context_protocol_error", "The context engine returned an unsupported content part.", 503)
            content = parts
        # Upstream bookkeeping, replay fields and persistence markers never leave
        # the controlled context adapter.
        result.append({"role": message["role"], "content": content})
    return result
