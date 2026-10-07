"""Study consumers use real SQLite/content/assessment without helper workloads."""
import socket

import pytest


@pytest.fixture(autouse=True)
def bounded_study_services(monkeypatch):
    monkeypatch.setattr("renulus.server.MODULE_ORDER", ("content", "learn", "assessment", "study"))
    # No provider, acquisition, OCR, embedding or native workload belongs here.
    original_connect = socket.socket.connect
    original_create = socket.create_connection
    original_resolve = socket.getaddrinfo
    def check_host(host):
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise AssertionError("Study consumer verification must not use external sockets")
    def local_connect(sock, address):
        if isinstance(address, tuple):
            check_host(address[0])
        return original_connect(sock, address)
    def local_create(address, *args, **kwargs):
        check_host(address[0])
        return original_create(address, *args, **kwargs)
    def local_resolve(host, *args, **kwargs):
        check_host(host)
        return original_resolve(host, *args, **kwargs)
    # Windows asyncio constructs a loopback self-pipe through socketpair().
    monkeypatch.setattr(socket.socket, "connect", local_connect)
    monkeypatch.setattr(socket, "create_connection", local_create)
    monkeypatch.setattr(socket, "getaddrinfo", local_resolve)
