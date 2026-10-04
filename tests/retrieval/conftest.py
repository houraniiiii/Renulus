"""Synthetic HTTP transports; real app repositories, no model/provider calls."""
import hashlib
import ipaddress
from pathlib import Path
import socket

import pytest

from renulus.content.repository import ContentRepository
from renulus.services import Services
from renulus.storage import AppPaths, Database

ROOT = Path(__file__).resolve().parents[2]


class SyntheticProtector:
    def protect(self, data, entropy):
        return hashlib.sha256(entropy + data).digest() + bytes(value ^ 0xA5 for value in data)

    def unprotect(self, data, entropy):
        plain = bytes(value ^ 0xA5 for value in data[32:])
        if hashlib.sha256(entropy + plain).digest() != data[:32]:
            raise ValueError("synthetic namespace mismatch")
        return plain


@pytest.fixture(autouse=True)
def no_live_network(monkeypatch):
    # Windows asyncio uses a loopback self-pipe; allow that local mechanism.
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)
        def guarded(self, address, _original=original):
            if isinstance(address, tuple):
                try:
                    if ipaddress.ip_address(address[0]).is_loopback:
                        return _original(self, address)
                except ValueError:
                    pass
            raise AssertionError("Live network is forbidden in synthetic retrieval tests")
        monkeypatch.setattr(socket.socket, name, guarded)


@pytest.fixture
def services(tmp_path):
    paths = AppPaths.create(tmp_path / "profile", ROOT)
    db = Database(paths.database)
    for name in ("content", "retrieval", "knowledge"):
        db.apply_migration(name + "-001", (ROOT / "runtime/renulus" / name / "schema.sql").read_text(encoding="utf-8"))
    services = Services(paths, db)
    content = ContentRepository(db, ROOT / "content/packs")
    content.install_pack(ROOT / "content/packs/renulus-foundations/1.0.0")
    services.registry["content"] = content
    return services
