"""Connected HTTP worker checks against owned loopback servers only."""
import asyncio
import base64
import hashlib
import queue
import time
from uuid import uuid4

import pytest

from renulus.worker_contracts import COMMAND, BrokerPaths, Identity
from renulus.workers.runtime import Worker
from .support import command, config, output, REVISIONS


@pytest.mark.parametrize("case", ["ok", "oversize", "redirect", "revoke", "replay", "denied"])
def test_mediated_http_worker(tmp_path, case):
    async def journey():
        seen = []
        reading = asyncio.Event()
        finish = asyncio.Event()

        async def serve(reader, writer):
            try:
                request = await reader.readuntil(b"\r\n\r\n")
                seen.append(request.split(b" ")[1])
                status = b"302 Found" if case == "redirect" else b"200 OK"
                body = b"x" * 200 if case == "oversize" else b"synthetic renal evidence"
                headers = b"Location: /must-not-follow\r\n" if case == "redirect" else b""
                writer.write(b"HTTP/1.1 " + status + b"\r\nContent-Type: text/plain\r\n" + headers +
                    b"Content-Length: " + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n")
                await writer.drain()
                reading.set()
                if case == "revoke":
                    await finish.wait()
                else:
                    writer.write(body)
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(serve, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        identity = config().identity.model_copy(update={"process_generation": "http_" + uuid4().hex})
        launch = config(identity=identity, broker=BrokerPaths(profile_root=str(tmp_path), state_root=str(tmp_path / "state")))
        replies = queue.Queue()
        worker = Worker(launch, launch.capacity, replies.put)

        async def terminal(raw):
            worker.handle(COMMAND.validate_python(raw), raw["input"])
            while True:
                reply = await asyncio.to_thread(replies.get, True, 5)
                if reply.identity.request_id == raw["request_id"] and reply.settlement.state == "settled":
                    return reply

        def request(permit=None):
            plan = dict(permit_id=permit or uuid4().hex, admission_receipt="receipt_" + uuid4().hex,
                revisions=REVISIONS.model_dump(), retention="saved", expires_at_ms=int(time.time()*1000)+60000,
                output=output(max_bytes=1024), endpoints=[dict(host="127.0.0.1", port=port if case != "denied" else port % 65535 + 1,
                    private_network=True)], method="GET", url=f"http://127.0.0.1:{port}/evidence", headers=[],
                body_base64="", body_sha256=hashlib.sha256(b"").hexdigest(), credential=None, max_response_bytes=100)
            raw = command("transport.http", plan, identity=identity)
            plan["identity"] = Identity(**{k: raw[k] for k in Identity.model_fields}).model_dump()
            from renulus.worker_contracts import payload_digest
            raw["payload_sha256"] = payload_digest(plan)
            return raw

        try:
            raw = request()
            pending = asyncio.create_task(terminal(raw))
            if case == "revoke":
                await asyncio.wait_for(reading.wait(), 5)
                revoke = command("worker.settle", dict(action="revoke", revisions=REVISIONS.model_copy(update={
                    "cancellation": REVISIONS.cancellation + 1}).model_dump(), target=None, artifact_handle=None), identity=identity)
                worker.handle(COMMAND.validate_python(revoke), revoke["input"])
            reply = await asyncio.wait_for(pending, 10)
            result = reply.result
            assert result.tag == "http"
            if case in ("ok", "redirect", "replay"):
                assert reply.outcome == "committed_reference", reply
                assert result.http_status == (302 if case == "redirect" else 200)
                read = command("artifact.read", dict(artifact_handle=result.artifact.artifact_handle,
                    artifact_revision=1, offset=0, length=1024), identity=identity)
                artifact_reply = await terminal(read)
                assert base64.b64decode(artifact_reply.result.data_base64) == b"synthetic renal evidence"
                if case == "redirect":
                    assert dict((h.name, h.value) for h in result.headers)["location"] == "/must-not-follow"
                if case == "replay":
                    replay = await terminal(request(raw["input"]["permit_id"]))
                    assert replay.result.code == "transport_permit_replayed"
                    assert replay.outcome == "rejected_before_admission"
                assert len(seen) == 1
            else:
                assert reply.outcome == "uncertain_after_disconnect", reply
                assert result.effect == "uncertain" and result.requests_started == 1
                assert result.artifact is None
                assert result.code == {"oversize": "capability_response_limit", "revoke": "transport_cancelled",
                    "denied": "capability_endpoint_denied"}[case]
                if case == "denied":
                    assert seen == []
        finally:
            finish.set()
            await asyncio.to_thread(worker.disconnect)
            server.close()
            await server.wait_closed()

    asyncio.run(journey())
