"""Subscription preparation for the parent-owned OpenCode integration seam."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from renulus.contracts import ApiError
from .inputs import validate_inputs
from .policy import BASE_URLS

PROTOCOLS = {"codex": "openai-responses", "opencode-go": "openai-chat"}
PATHS = {"codex": "/responses", "opencode-go": "/chat/completions"}


@dataclass(frozen=True)
class SubscriptionRoute:
    provider_id: str
    catalog_model_id: str
    wire_model_id: str
    endpoint: str
    protocol: str
    credential_ref: str
    credential_epoch: int
    catalogue_listed: bool | None

    def descriptor(self) -> dict:
        """Safe configuration data. This contains no credentials or input."""
        return asdict(self)


def subscription_route(provider: str, model: str, *, credential_ref: str,
                       credential_epoch: int, catalogue: set[str] | None) -> SubscriptionRoute:
    return SubscriptionRoute(provider, model, model, BASE_URLS[provider] + PATHS[provider],
                             PROTOCOLS[provider], credential_ref, credential_epoch,
                             None if catalogue is None else model in catalogue)


def validate_harness_images(images: list[dict]) -> None:
    """Validate final native inline images in memory, without echoing payloads.

    The Node adapter projects the serialized wire images into the existing input
    shape. The trusted parent supplies this decoder through its owned IPC seam.
    """
    if not isinstance(images, list) or any(not isinstance(part, dict) or part.get("type") != "image" for part in images):
        raise ApiError("invalid_image", "Supply typed inline images for decoder validation.")
    if images:
        validate_inputs([{"role": "user", "content": images}])
