# SPDX-License-Identifier: MIT
"""Connection challenge for the private domain facade; no token in the probe.

The Node facade sends credentials/body only on the very TCP connection which
returned this launch-private HMAC. A replacement listener cannot prove it and
the Node connection is forbidden to reconnect after challenge completion.
"""
import hashlib
import hmac
import re


class DomainPeer:
    def __init__(self, app, key):
        self.app = app
        self._key = key.encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/__renulus_peer":
            return await self.app(scope, receive, send)
        query = scope.get("query_string", b"")
        valid = re.fullmatch(b"nonce=([0-9a-f]{64})", query)
        body = (hmac.new(self._key, b"renulus-domain-http/1:" + valid[1], hashlib.sha256).hexdigest().encode()
                if valid and scope["method"] == "GET" else b"")
        await send({"type": "http.response.start", "status": 200 if body else 403,
                    "headers": [(b"content-type", b"text/plain"), (b"content-length", str(len(body)).encode()),
                                (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": body})
