# SPDX-License-Identifier: MIT
"""Synthetic loopback journey for the credential-free MCP broker (BF03). No real network/accounts."""
import asyncio
import base64
import hashlib
import json
import os
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from renulus.workers.mcp_broker import McpBroker, McpBrokerError
from renulus.workers.mcp_tokens import McpCredentials

OLD, REFRESH, NEW = "OLD_ACCESS_SENTINEL", "REFRESH_SENTINEL", "NEW_ACCESS_SENTINEL"
ECHO_SERVER = "import sys\nfor line in sys.stdin:\n    sys.stdout.write(line); sys.stdout.flush()\n"


class Server:
    def __init__(self):
        self.seen, self.deleted = [], 0

    async def handle(self, reader, writer):
        head = await reader.readuntil(b"\r\n\r\n")
        lines = head.decode().split("\r\n")
        method, path, _ = lines[0].split(" ")
        headers = {k.lower(): v for k, v in (l.split(": ", 1) for l in lines[1:] if ": " in l)}
        body = await reader.readexactly(int(headers.get("content-length", 0)))
        base = f"http://127.0.0.1:{self.port}"
        status, payload = 200, {}
        if path.endswith("oauth-protected-resource"):
            payload = {"authorization_servers": [base]}
        elif path.endswith("oauth-authorization-server"):
            payload = {"token_endpoint": base + "/token"}
        elif path == "/token":
            ok = f"refresh_token={REFRESH}" in body.decode()
            status, payload = (200, {"access_token": NEW, "expires_in": 3600, "token_type": "Bearer"}) if ok else (400, {})
        elif headers.get("authorization") != "Bearer " + NEW:
            status = 401
        elif method == "DELETE":
            self.deleted, status = self.deleted + 1, 204
        else:
            payload = {"echo": headers["authorization"]} if path == "/echo" else {"ok": True}
        self.seen.append((method, path, headers.get("authorization")))
        data = b"" if status == 204 else json.dumps(payload).encode()
        writer.write(f"HTTP/1.1 {status} X\r\nContent-Type: application/json\r\nContent-Length: {len(data)}\r\n"
            f"Location: http://evil.invalid/\r\nWWW-Authenticate: Bearer\r\nConnection: close\r\n\r\n".encode() + data)
        await writer.drain()
        writer.close()


@unittest.skipUnless(os.name == "nt", "Windows DPAPI and Job Object acceptance")
class McpBrokerJourney(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_echo_cleanup_stdio_and_revoke(self):
        server = Server()
        listener = await asyncio.start_server(server.handle, "127.0.0.1", 0)
        server.port = listener.sockets[0].getsockname()[1]
        base = f"http://127.0.0.1:{server.port}"
        with TemporaryDirectory(prefix="renulus-mcp-broker-") as folder:
            root = Path(folder).resolve()
            credentials = McpCredentials(root, root / "state")
            credentials.put("mcp_ref", revision=1, resource=base + "/mcp", client_id="client", access_token=OLD,
                refresh_token=REFRESH, expires_at=time.time() - 10)
            allowed = True

            async def ask(conn, lease, count):
                return allowed
            broker = McpBroker(credentials, ask, workspace=root)
            conn = {"conn": "c1"}
            await broker.handle({"op": "connection.open", **conn, "expires_at_ms": int(time.time() * 1000) + 60000,
                "max_bytes": 1024 * 1024, "endpoints": [{"host": "127.0.0.1", "port": server.port, "private_network": True}]})
            discovered = await broker.handle({"op": "credential.discover", **conn, "ref": "mcp_ref", "revision": 1})
            self.assertEqual(discovered["credential"]["token_endpoint"], base + "/token")

            def request(path, **extra):
                return {"op": "http", **conn, "url": base + path, "method": "POST", "headers": {"accept": "application/json"},
                    "body_base64": "", "body_sha256": hashlib.sha256(b"").hexdigest(),
                    "credential_ref": "mcp_ref", "credential_revision": 1, **extra}

            # Expired token: the broker refreshes before the request; Node never sees a token or auth headers.
            reply = await broker.handle(request("/mcp"))
            self.assertEqual(reply["status"], 200)
            self.assertEqual(set(reply["headers"]), {"content-type", "content-length"})
            chunk = await broker.handle({"op": "http.read", **conn, "stream": reply["stream"]})
            self.assertEqual(json.loads(base64.b64decode(chunk["data_base64"])), {"ok": True})
            await broker.handle({"op": "http.close", **conn, "stream": reply["stream"]})
            self.assertIn(("POST", "/mcp", "Bearer " + NEW), server.seen)
            # A server echoing the bearer token cannot return it to Node.
            echo = await broker.handle(request("/echo"))
            with self.assertRaises(McpBrokerError) as refused:
                await broker.handle({"op": "http.read", **conn, "stream": echo["stream"]})
            self.assertEqual(refused.exception.code, "mcp_credential_echo")
            # The token goes only to its own origin, and is never in the protected record's plaintext.
            with self.assertRaises(Exception):
                await broker.handle({**request("/mcp"), "url": "http://localhost:1/mcp"})
            stored = credentials.store.path.read_bytes()
            self.assertFalse(any(s.encode() in stored for s in (OLD, REFRESH, NEW)))

            # Developer-only stdio: bounded frames, Job-owned settlement.
            script = root / "server.py"
            script.write_text(ECHO_SERVER)
            opened = await broker.handle({"op": "stdio.open", **conn, "argv": [sys.executable, str(script)], "cwd": str(root)})
            frame = base64.b64encode(b'{"jsonrpc":"2.0","id":1}').decode()
            await broker.handle({"op": "stdio.write", **conn, "server": opened["server"], "frame_base64": frame})
            echoed = await broker.handle({"op": "stdio.read", **conn, "server": opened["server"]})
            self.assertEqual(echoed["frame_base64"], frame)
            closed = await broker.handle({"op": "stdio.close", **conn, "server": opened["server"]})
            self.assertTrue(closed["settlement"]["descendants_settled"])

            # Revoke: the host stops answering `current`; new work is refused and streams die.
            allowed = False
            with self.assertRaises(Exception):
                await broker.handle(request("/mcp"))
            await broker.handle({"op": "connection.close", **conn})
            with self.assertRaises(McpBrokerError):
                await broker.handle(request("/mcp"))
            # One-use cleanup path: its own lease, DELETE only, host-admitted separately.
            allowed = True
            done = await broker.handle({"op": "cleanup", **conn, "url": base + "/mcp", "session_id": "session-1",
                "endpoint": {"host": "127.0.0.1", "port": server.port, "private_network": True},
                "credential_ref": "mcp_ref", "credential_revision": 1})
            self.assertEqual(done["status"], 204)
            self.assertEqual(server.deleted, 1)
        listener.close()
        await listener.wait_closed()


if __name__ == "__main__":
    unittest.main()
