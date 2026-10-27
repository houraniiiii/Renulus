"""Protected socket context stays exact and cannot authorize an engine task."""
import asyncio
import socket

import pytest

from renulus.workers.main import _offline_audit
from renulus.workers.transport_guard import endpoint_network, permitted_connection


def test_exact_endpoint_scope_and_sibling_engine_remain_isolated(monkeypatch):
    async def scenario():
        loop = asyncio.get_running_loop()
        async def resolve(host, port, **kwargs):
            assert host == "synthetic.invalid" and port == 443
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.7", 443))]
        monkeypatch.setattr(loop, "getaddrinfo", resolve)
        engine_enter = asyncio.Event()
        async def engine():
            await engine_enter.wait()
            assert not permitted_connection(("192.0.2.7", 443))
            with pytest.raises(PermissionError):
                _offline_audit("socket.connect", (None, ("192.0.2.7", 443)))
        sibling = asyncio.create_task(engine())
        async with endpoint_network("https://synthetic.invalid/v1/responses"):
            assert permitted_connection(("192.0.2.7", 443))
            _offline_audit("socket.connect", (None, ("192.0.2.7", 443)))
            assert not permitted_connection(("192.0.2.7", 80))
            assert not permitted_connection(("192.0.2.8", 443))
            engine_enter.set()
            await sibling
        assert not permitted_connection(("192.0.2.7", 443))
    asyncio.run(scenario())


def test_cancelled_scope_revokes_socket_authority(monkeypatch):
    async def scenario():
        loop = asyncio.get_running_loop()
        async def resolve(*args, **kwargs):
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:db8::7", 443, 0, 0))]
        monkeypatch.setattr(loop, "getaddrinfo", resolve)
        with pytest.raises(asyncio.CancelledError):
            async with endpoint_network("https://synthetic.invalid/v1"):
                assert permitted_connection(("2001:db8::7", 443, 0, 0))
                raise asyncio.CancelledError()
        assert not permitted_connection(("2001:db8::7", 443, 0, 0))
    asyncio.run(scenario())
