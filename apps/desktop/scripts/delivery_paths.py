"""Exact owned generated roots; source and application profiles are never outputs."""
from pathlib import Path
import re

DESKTOP = Path(__file__).resolve().parents[1]
EXTERNAL_DELIVERY_ROOT = Path("C:/Renulus-native-delivery/desktop-20261005")
PUBLIC_INPUT_ROOT = Path("E:/Renulus-native-delivery/desktop-20261005")
PUBLIC_DIRECTORY = re.compile(r"preparation|payloads|environment|temporary|proofs|source-[0-9a-f]{8}|matching-[0-9a-f]{8}|installed-[0-9a-f]{8}")
DELIVERY_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
WINDOWS_DEVICE_NAME = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", re.IGNORECASE)


def delivery_name(value: str) -> bool:
    return bool(DELIVERY_NAME.fullmatch(value) and not value.endswith(".")
                and not WINDOWS_DEVICE_NAME.fullmatch(value))


def owned_path(value: Path, root: Path, *, fresh: bool = False) -> Path:
    resolved, root = value.resolve(), root.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError("Delivery output must stay in its assigned desktop generated directory")
    if fresh and resolved.exists():
        raise ValueError("Delivery output must be fresh; preserve the existing checkpoint")
    for ancestor in (value.absolute(), *value.absolute().parents):
        if ancestor.is_symlink() or ancestor.is_junction():
            raise ValueError("Delivery may not traverse a reparse path")
    return resolved


def checked_delivery_root(value: Path) -> Path:
    """Only the approved C root or one named deliveries child may own outputs."""
    if not value.is_absolute():
        raise ValueError("DeliveryRoot requires an absolute local C path")
    base = EXTERNAL_DELIVERY_ROOT.resolve()
    resolved = value.resolve()
    if resolved != base:
        if not resolved.is_relative_to(base):
            raise ValueError("DeliveryRoot must stay in the exact authorised C SSD root")
        relative = resolved.relative_to(base).parts
        if len(relative) != 2 or relative[0] != "deliveries" or not delivery_name(relative[1]):
            raise ValueError("DeliveryRoot may only use a named deliveries child; repository/data/profile roots are excluded")
    for ancestor in (value.absolute(), *value.absolute().parents):
        if ancestor.is_symlink() or ancestor.is_junction():
            raise ValueError("DeliveryRoot may not traverse a reparse path")
    if resolved.exists() and not resolved.is_dir():
        raise ValueError("DeliveryRoot must be a directory")
    return resolved


def public_relative(value: Path, root: Path) -> None:
    relative = value.resolve().relative_to(root.resolve()).parts
    if root == EXTERNAL_DELIVERY_ROOT and len(relative) >= 3 and relative[0] == "deliveries" and delivery_name(relative[1]):
        relative = relative[2:]
    if not relative or not PUBLIC_DIRECTORY.fullmatch(relative[0]):
        raise ValueError("Public staging excludes source repositories, credentials and application data/profiles")


def generated_path(value: Path, *, fresh: bool = False) -> Path:
    if not value.is_absolute():
        raise ValueError("Generated staging requires an absolute path")
    for root in (DESKTOP / "test-results", EXTERNAL_DELIVERY_ROOT):
        if value.absolute().is_relative_to(root.absolute()):
            if root == EXTERNAL_DELIVERY_ROOT:
                public_relative(value, root)
            return owned_path(value, root, fresh=fresh)
    raise ValueError("Generated staging must stay in desktop test-results or the exact authorised C root; E inputs are read-only")


def public_input_path(value: Path) -> Path:
    """Admit explicit public inputs on E and fresh staged public bytes on C."""
    if not value.is_absolute():
        raise ValueError("Public inputs require an absolute path")
    for root in (DESKTOP / "test-results", EXTERNAL_DELIVERY_ROOT, PUBLIC_INPUT_ROOT):
        if value.absolute().is_relative_to(root.absolute()):
            if root in (EXTERNAL_DELIVERY_ROOT, PUBLIC_INPUT_ROOT):
                public_relative(value, root)
            return owned_path(value, root)
    raise ValueError("Public inputs require an explicit admitted C/E public directory")
