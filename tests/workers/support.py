from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
from threading import Thread
import time
import uuid

from renulus.worker_contracts import (COMMAND, Capacity, LaunchConfig, ProcessIdentity,
                                     Revisions, payload_digest)

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = ProcessIdentity(profile_id="profile_synthetic", domain_store_id="domain_synthetic",
    runtime_store_id="runtime_synthetic", authority_epoch=4, process_generation="pg_synthetic")
REVISIONS = Revisions(configuration=8, grant=12, context=31, deletion=6, cancellation=0)
TOKEN = "synthetic-launch-token-for-worker-tests-only"


def config(**changes):
    values = dict(identity=IDENTITY, revisions=REVISIONS, retention="saved",
                  launch_token_sha256=hashlib.sha256(TOKEN.encode()).hexdigest())
    values.update(changes)
    return LaunchConfig(**values)


def command(name, input, *, revisions=REVISIONS, identity=IDENTITY, retention="saved", **changes):
    values = dict(protocol="renulus-worker/1", kind="command", **identity.model_dump(),
        operation_id="operation_synthetic", attempt_id="attempt_synthetic",
        request_id="request_" + uuid.uuid4().hex, payload_sha256=payload_digest(input),
        configuration_revision=revisions.configuration, grant_revision=revisions.grant,
        context_epoch=revisions.context, deletion_epoch=revisions.deletion,
        cancellation_epoch=revisions.cancellation, retention=retention, expected_revision=None,
        command=name, input=input, limits={"result_page_bytes":262144, "cpu_seconds":120})
    values.update(changes)
    return values


def output(handle=None, max_bytes=1024 * 1024):
    return dict(artifact_handle=handle or "artifact_" + uuid.uuid4().hex, artifact_revision=1,
                max_bytes=max_bytes, expires_at_ms=int(time.time() * 1000) + 3600000,
                reservation_id="reservation_synthetic", intent_id="intent_synthetic")


def grant(body, handle=None, rights=None):
    return dict(artifact_handle=handle or "artifact_" + uuid.uuid4().hex, artifact_revision=1,
        artifact_sha256=hashlib.sha256(body).hexdigest(), bytes=len(body),
        expires_at_ms=int(time.time() * 1000) + 3600000, rights=rights or ["read", "extract", "chunk"],
        permitted_ranges=[{"offset":0,"length":len(body)}],
        reservation_id="reservation_synthetic", intent_id="intent_synthetic")


def target(reply):
    return dict(identity=reply["identity"], request_sha256=reply["request_sha256"],
                worker_lease=reply["settlement"]["worker_lease"])


class Process:
    def __init__(self, folder, *, launch=None, capacity=None):
        folder.mkdir(parents=True, exist_ok=True)
        self.launch = launch or config()
        path = folder / "launch.json"
        path.write_text(self.launch.model_dump_json(), encoding="utf-8")
        # Explicit synthetic cache/temp state; no account/provider environment.
        env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "COMSPEC", "PATH") if key in os.environ}
        env.update(PYTHONPATH=str(ROOT / "runtime"), PYTHONDONTWRITEBYTECODE="1",
                   TEMP=str(folder), TMP=str(folder), TMPDIR=str(folder),
                   HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
        self.process = subprocess.Popen([sys.executable, "-B", "-m", "renulus.workers.main", "--config", str(path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=ROOT, env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.lines = queue.Queue()
        self.saved = []
        self.reader = Thread(target=self._read, daemon=True)
        self.reader.start()
        self.hello = dict(protocol="renulus-worker/1", kind="hello", launch_token=TOKEN,
                          expected_launcher_pid=self.process.pid,
                          identity=self.launch.identity.model_dump(),
                          capacity=(capacity or self.launch.capacity).model_dump())

    def _read(self):
        for line in self.process.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def send(self, value):
        self.process.stdin.write(json.dumps(value, ensure_ascii=False, allow_nan=False,
                                            separators=(",", ":")).encode("utf-8") + b"\n")
        self.process.stdin.flush()

    def receive(self, timeout=20):
        line = self.lines.get(timeout=timeout)
        if line is None:
            raise AssertionError(f"Worker exited: {self.process.poll()}")
        return json.loads(line)

    def start(self):
        self.send(self.hello)
        ready = self.receive(timeout=120)  # Cold selected native-helper imports.
        assert ready["kind"] == "ready"
        # Windows venv Scripts/python.exe is a redirector with an owned child.
        assert ready["process"]["launcher_pid"] == self.process.pid, ready
        assert ready["process"]["actual_pid"] == ready["pid"], ready
        assert 0 <= ready["process"]["ancestry_depth"] <= 16
        return ready

    def request(self, value, *, terminal=True, timeout=30):
        self.send(value)
        while True:
            for index, reply in enumerate(self.saved):
                if reply["identity"]["request_id"] == value["request_id"]:
                    self.saved.pop(index)
                    break
            else:
                reply = self.receive(timeout=timeout)
            if reply["identity"]["request_id"] != value["request_id"]:
                self.saved.append(reply)
                continue
            if not terminal or reply["settlement"]["state"] == "settled":
                return reply

    def upload(self, body, *, retention=None, rights=None, handle=None):
        g = grant(body, handle=handle, rights=rights)
        for offset in range(0, max(1, len(body)), 262144):
            chunk = body[offset:offset + 262144]
            value = command("artifact.upload", dict(artifact=g, offset=offset,
                data_base64=base64.b64encode(chunk).decode(), final=offset + len(chunk) == len(body)),
                retention=retention or self.launch.retention)
            reply = self.request(value)
            assert reply["outcome"] == "committed_reference", reply
        return g

    def read_all(self, reference):
        body, offset = bytearray(), 0
        while True:
            reply = self.request(command("artifact.read", dict(artifact_handle=reference["artifact_handle"],
                artifact_revision=reference["artifact_revision"], offset=offset, length=262144),
                retention=self.launch.retention))
            assert reply["outcome"] == "committed_reference", reply
            body.extend(base64.b64decode(reply["result"]["data_base64"]))
            offset = reply["result"]["next_cursor"]
            if offset is None:
                break
        assert len(body) == reference["bytes"]
        assert hashlib.sha256(body).hexdigest() == reference["artifact_sha256"]
        return bytes(body)

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=10)
            raise
        self.reader.join(timeout=2)
        assert self.process.stderr.read() == b""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
