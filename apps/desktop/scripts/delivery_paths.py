"""Exact owned generated roots; source and application profiles are never outputs."""
from pathlib import Path

DESKTOP = Path(__file__).resolve().parents[1]
EXTERNAL_DELIVERY_ROOT = Path("E:/Renulus-native-delivery/desktop-20261005")


def owned_path(value: Path, root: Path, *, fresh: bool = False) -> Path:
    resolved, root = value.resolve(), root.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError("Delivery output must stay in its assigned desktop generated directory")
    if fresh and resolved.exists():
        raise ValueError("Delivery output must be fresh; preserve the existing checkpoint")
    for ancestor in (value.absolute(), *value.absolute().parents):
        if ancestor.exists() and (ancestor.is_symlink() or ancestor.is_junction()):
            raise ValueError("Delivery may not traverse a reparse path")
    return resolved


def generated_path(value: Path, *, fresh: bool = False) -> Path:
    for root in (DESKTOP / "test-results", EXTERNAL_DELIVERY_ROOT):
        if value.absolute().is_relative_to(root.absolute()):
            return owned_path(value, root, fresh=fresh)
    raise ValueError("Generated staging must stay in desktop test-results or the exact authorised E root")
