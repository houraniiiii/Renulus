"""Evidence command runs inside the real protected worker; synthetic loopback only."""
import asyncio
import base64
import json
import queue
import time
from uuid import uuid4

import pytest

from renulus.worker_contracts import COMMAND, BrokerPaths, Identity, payload_digest
from renulus.workers.runtime import Worker
from .support import command, config, output, REVISIONS


@pytest.mark.parametrize("case", ["status", "search", "redirect"])
def test_evidence_run(tmp_path, case):
    async def journey():
        seen = []

        async def serve(reader, writer):
            raw = await reader.readuntil(b"\r\n\r\n")
            seen.append(raw.split(b" ")[1])
            body = json.dumps({"resultList": {"result": [{"id": "10001", "source": "MED",
                "title": "Synthetic AKI research", "firstPublicationDate": "2026-09-01"}]}}).encode()
            status = b"302 Found" if case == "redirect" else b"200 OK"
            headers = b"Location: /not-followed\r\n" if case == "redirect" else b""
            writer.write(b"HTTP/1.1 " + status + b"\r\n" + headers + b"Content-Type: application/json\r\nContent-Length: " +
                str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body)
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(serve, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        identity = config().identity.model_copy(update={"process_generation": "evidence_" + uuid4().hex})
        launch = config(identity=identity, broker=BrokerPaths(profile_root=str(tmp_path), state_root=str(tmp_path / "state")))
        replies = queue.Queue()
        worker = Worker(launch, launch.capacity, replies.put)

        async def terminal(raw):
            worker.handle(COMMAND.validate_python(raw), raw["input"])
            while True:
                reply = await asyncio.to_thread(replies.get, True, 10)
                if reply.identity.request_id == raw["request_id"] and reply.settlement.state == "settled":
                    return reply

        plan = dict(permit_id=uuid4().hex, admission_receipt="synthetic_receipt", revisions=REVISIONS.model_dump(),
            retention="saved", expires_at_ms=int(time.time()*1000)+60000, output=output(),
            action="status" if case == "status" else "search", provider=None if case == "status" else "europe-pmc",
            query=None if case == "status" else "AKI", max_requests=1,
            endpoint=dict(host="127.0.0.1", port=port, private_network=True), base_url=f"http://127.0.0.1:{port}/rest")
        raw = command("evidence.run", plan, identity=identity)
        plan["identity"] = Identity(**{k: raw[k] for k in Identity.model_fields}).model_dump()
        raw["payload_sha256"] = payload_digest(plan)
        try:
            reply = await terminal(raw)
            result = reply.result
            assert result.tag == "http"
            if case == "redirect":
                assert result.code == "retrieval_redirect_blocked"
                assert result.requests_started == 1 and result.effect == "response_received"
                assert len(seen) == 1
            else:
                assert reply.outcome == "committed_reference", reply
                read = command("artifact.read", dict(artifact_handle=result.artifact.artifact_handle,
                    artifact_revision=1, offset=0, length=result.artifact.bytes), identity=identity)
                data = json.loads(base64.b64decode((await terminal(read)).result.data_base64))
                if case == "status":
                    assert len(data["connections"]) == 5 and not seen
                    assert all(not row["configured"] for row in data["connections"])
                else:
                    assert data["verification"] == "discovery-only" and data["passage_evidence"] is False
                    assert data["records"][0]["title"] == "Synthetic AKI research"
                    assert result.requests_started == 1
        finally:
            await asyncio.to_thread(worker.disconnect)
            server.close()
            await server.wait_closed()

    asyncio.run(journey())
