# SPDX-License-Identifier: MIT
"""Account-free lifecycle proof for the private domain launch adapter."""
import io
import hashlib
import hmac
import http.client
import json
import os
from contextlib import closing
from pathlib import Path
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time
from uuid import uuid4

import pytest

from renulus.runtime.domain_process import FRAME_BYTES, PROTOCOL, read_frame

SOURCE = Path(__file__).resolve().parents[2]
TOKEN = "synthetic-domain-control-only"

APP = '''
import asyncio,os,sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,Request
from renulus.services import Services
def create_app(profile,token,source_root):
    assert token not in ' '.join(sys.argv) and 'RENULUS_SESSION_TOKEN' not in os.environ
    root=Path(profile)
    services=Services(None,None)
    async def finish():
        (root/'shutdown-attempted').write_text('attempted')
        if (root/'refuse').exists() and not (root/'allow-shutdown').exists():
            raise RuntimeError('synthetic refusal')
        (root/'services-settled').write_text('settled')
    services.on_shutdown.append(finish)
    @asynccontextmanager
    async def lifespan(app):
        (root/'startup-entered').write_text('entered')
        while (root/'delay-startup').exists() and not (root/'allow-startup').exists():
            await asyncio.sleep(.02)
        # Native and Python noise must stay outside the reserved stdout pipe.
        print('synthetic app stdout noise',flush=True)
        os.write(1,b'synthetic native stdout noise\\n')
        yield
        await services.finish_shutdown()
        while (root/'delay-exit').exists() and not (root/'allow-exit').exists():
            await asyncio.sleep(.02)
        (root/'lifespan-closed').write_text('closed')
    app=FastAPI(lifespan=lifespan)
    app.state.services=services
    @app.post('/api/v1/echo')
    async def echo(request:Request):
        return {'authorized':request.headers.get('x-renulus-token')==token,'body':(await request.body()).decode()}
    return app
'''


def until(predicate):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.02)
    raise AssertionError("domain process did not reach expected stage")


class Domain:
    def __init__(self, root):
        self.root = root
        self.profile = root / "profile"
        self.profile.mkdir(parents=True)
        package = root / "runtime" / "renulus"
        (package / "runtime").mkdir(parents=True)
        (package / "__init__.py").write_text(
            f'__version__="0.1.0"\n__path__.append({str(SOURCE / "runtime" / "renulus")!r})\n', encoding="utf-8")
        (package / "runtime" / "__init__.py").write_text("", encoding="utf-8")
        for name in ("domain_process.py", "domain_peer.py"):
            shutil.copyfile(SOURCE / "runtime" / "renulus" / "runtime" / name, package / "runtime" / name)
        (package / "server.py").write_text(APP, encoding="utf-8")
        self.nonce = str(uuid4())
        self.process = None
        self.frames = queue.Queue()

    def start(self, change=None):
        env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "TEMP", "TMP") if k in os.environ}
        env.update(PYTHONPATH=str(self.root / "runtime"), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        self.process = subprocess.Popen([sys.executable, "-B", "-m", "renulus.runtime.domain_process",
            "--profile", str(self.profile), "--source-root", str(self.root), "--launch-nonce", self.nonce],
            cwd=self.root, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

        def collect():
            for line in self.process.stdout:
                self.frames.put(line)
            self.frames.put(None)

        self.collector = threading.Thread(target=collect, daemon=True)
        self.collector.start()
        hello = dict(protocol=PROTOCOL, kind="hello", profile=str(self.profile), launch_nonce=self.nonce,
                     expected_launcher_pid=self.process.pid, token=TOKEN)
        hello.update(change or {})
        self.send(hello)
        return self

    def send(self, value):
        self.process.stdin.write(json.dumps(value).encode() + b"\n")
        self.process.stdin.flush()

    def receive(self):
        line = self.frames.get(timeout=10)
        if line is None:
            return None
        assert TOKEN.encode() not in line
        return json.loads(line)

    def command(self, ready, **changes):
        value = {k: ready[k] for k in ("protocol", "profile", "launch_nonce", "pid")}
        value.update(kind="shutdown", request_id=str(uuid4()), timeout_seconds=1)
        value.update(changes)
        self.send(value)
        return value

    def finish(self):
        if self.process is None:
            return
        # Cleanup uses the same EOF + real settlement path even on assertion
        # failure, so tests do not leave detached synthetic writers.
        for name in ("allow-startup", "allow-shutdown", "allow-exit"):
            (self.profile / name).touch()
        if not self.process.stdin.closed:
            self.process.stdin.close()
        self.process.wait(timeout=10)
        self.collector.join(timeout=2)
        stderr = self.process.stderr.read()
        assert TOKEN.encode() not in stderr
        self.process.stdout.close()
        self.process.stderr.close()


@pytest.fixture
def domain(tmp_path):
    instance = Domain(tmp_path)
    try:
        yield instance
    finally:
        instance.finish()


@pytest.mark.skipif(os.name != "nt", reason="Windows lineage is deliberately required")
def test_http_peer_proves_the_owned_connection_without_application_credentials(domain):
    domain.start()
    ready = domain.receive()
    nonce = "ab" * 32
    with closing(http.client.HTTPConnection("127.0.0.1", ready["port"], timeout=2)) as connection:
        connection.request("GET", "/__renulus_peer?nonce=" + nonce)
        response = connection.getresponse()
        assert response.status == 200
        assert response.read() == hmac.new(TOKEN.encode(), b"renulus-domain-http/1:" + nonce.encode(),
                                           hashlib.sha256).hexdigest().encode()
        proven_socket = connection.sock
        assert proven_socket is not None
        for method, query in [("GET", ""), ("GET", "?nonce=foreign"), ("POST", "?nonce=" + nonce)]:
            connection.request(method, "/__renulus_peer" + query)
            denied = connection.getresponse()
            assert denied.status == 403
            assert denied.read() == b""
        connection.request("POST", "/api/v1/echo", body="SYNTHETIC study payload",
                           headers={"x-renulus-token": TOKEN})
        reply = connection.getresponse()
        assert reply.status == 200
        assert json.loads(reply.read()) == {"authorized": True, "body": "SYNTHETIC study payload"}
        assert connection.sock is proven_socket


@pytest.mark.skipif(os.name != "nt", reason="Windows lineage is deliberately required")
def test_ready_after_lifespan_and_exclusive_bind_ack_before_actual_exit(domain):
    (domain.profile / "delay-startup").touch()
    (domain.profile / "delay-exit").touch()
    domain.start()
    until(lambda: (domain.profile / "startup-entered").exists())
    assert domain.frames.empty(), "startup-entered is not readiness"
    (domain.profile / "allow-startup").touch()
    ready = domain.receive()
    assert ready["kind"] == "ready"
    proof = ready["process"]
    assert proof["launcher_pid"] == domain.process.pid
    assert proof["actual_pid"] == ready["pid"]
    assert int(proof["actual_creation_filetime"]) >= int(proof["launcher_creation_filetime"]) > 0
    with socket.socket() as foreign:
        with pytest.raises(OSError):
            foreign.bind(("127.0.0.1", ready["port"]))
    request = domain.command(ready)
    reply = domain.receive()
    assert reply == {k: v for k, v in request.items() if k != "timeout_seconds"} | {"state": "settled"}
    assert (domain.profile / "services-settled").exists()
    domain.process.stdin.close()
    assert domain.process.poll() is None, "ACK is distinct from process/lifespan exit"
    (domain.profile / "allow-exit").touch()
    assert domain.process.wait(timeout=10) == 0
    assert domain.receive() is None
    assert (domain.profile / "lifespan-closed").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows lineage is deliberately required")
def test_parent_eof_retains_refused_services_then_retries_real_drain(domain):
    (domain.profile / "refuse").touch()
    domain.start()
    assert domain.receive()["kind"] == "ready"
    domain.process.stdin.close()
    until(lambda: (domain.profile / "shutdown-attempted").exists())
    assert domain.process.poll() is None
    assert not (domain.profile / "services-settled").exists()
    (domain.profile / "allow-shutdown").touch()
    assert domain.process.wait(timeout=10) == 0
    assert domain.receive() is None, "EOF/exit must not synthesize a shutdown ACK"
    assert (domain.profile / "lifespan-closed").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows lineage is deliberately required")
def test_parent_eof_during_startup_drains_the_same_lifespan(domain):
    (domain.profile / "delay-startup").touch()
    domain.start()
    until(lambda: (domain.profile / "startup-entered").exists())
    domain.process.stdin.close()
    assert domain.process.poll() is None
    (domain.profile / "allow-startup").touch()
    assert domain.receive()["kind"] == "ready"
    assert domain.process.wait(timeout=10) == 0
    assert domain.receive() is None
    assert (domain.profile / "lifespan-closed").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows lineage is deliberately required")
@pytest.mark.parametrize("change", [
    {"profile": "foreign"}, {"launch_nonce": str(uuid4())}, {"pid": 1}, {"request_id": "stale"},
])
def test_foreign_shutdown_binding_never_receives_a_settlement_ack(domain, change):
    domain.start()
    ready = domain.receive()
    domain.command(ready, **change)
    assert domain.process.wait(timeout=10) == 0
    assert domain.receive() is None
    assert (domain.profile / "lifespan-closed").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows lineage is deliberately required")
@pytest.mark.parametrize("change", [
    {"profile": "foreign"}, {"launch_nonce": str(uuid4())}, {"expected_launcher_pid": 4294967295},
])
def test_foreign_hello_refused_before_application_startup(domain, change):
    domain.start(change)
    assert domain.process.wait(timeout=10) == 1
    assert domain.receive() is None
    assert not (domain.profile / "startup-entered").exists()


@pytest.mark.parametrize("body", [
    b'{"protocol":"renulus-domain/1","protocol":"renulus-domain/1"}\n',
    b'{"protocol":"renulus-domain/1","value":NaN}\n',
    b'\xff\n', b'{}', b'x' * FRAME_BYTES + b'\n',
])
def test_control_frames_reject_ambiguous_unbounded_or_incomplete_input(body):
    with pytest.raises(ValueError):
        read_frame(io.BytesIO(body))
