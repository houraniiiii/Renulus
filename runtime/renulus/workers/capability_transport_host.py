# SPDX-License-Identifier: MIT
"""One helper process owns the browser tunnel sockets of one admitted lease.

The TypeScript host sends line-delimited JSON requests on stdin and receives replies on stdout.
Every credit decision is delegated back to the host (`{"credit": n}` -> `{"credit": n, "ok": bool}`),
so Node alone owns current authority while Python owns the bounded socket bytes. Closing the process
destroys every socket; no direct-connect fallback exists here.
"""
from __future__ import annotations
import asyncio
import base64
import json
import os
import sys
from threading import Thread

from .capability_transport import CapabilityTransport, CapabilityTransportError, Endpoint, NetworkLease


async def serve(stdin=None, stdout=None):
    stdin, stdout = stdin or sys.stdin.buffer, stdout or sys.stdout.buffer
    loop = asyncio.get_running_loop()
    lines: asyncio.Queue = asyncio.Queue()

    def pump():
        for line in stdin:
            loop.call_soon_threadsafe(lines.put_nowait, line)
        loop.call_soon_threadsafe(lines.put_nowait, None)

    Thread(target=pump, name="renulus-transport-host-stdin", daemon=True).start()
    credits: dict[int, asyncio.Future] = {}
    counter = 0

    def send(value):
        stdout.write((json.dumps(value) + "\n").encode())
        stdout.flush()

    async def current(_identity, count):
        nonlocal counter
        counter += 1
        key, credits[counter] = counter, loop.create_future()
        send({"credit": key, "count": count})
        return await credits[key]

    owner: CapabilityTransport | None = None
    tasks: set[asyncio.Task] = set()

    async def handle(message):
        nonlocal owner
        op, args = message["op"], message.get("args", {})
        try:
            if op == "init":
                lease = args["lease"]
                owner = CapabilityTransport(NetworkLease(lease["id"],
                    tuple(Endpoint(e["host"], e["port"], e["private_network"]) for e in lease["endpoints"]),
                    lease["expires_at_ms"], lease["max_bytes"], lease["max_sockets"]), current=current)
                result = None
            elif owner is None:
                raise CapabilityTransportError("capability_lease_invalid")
            elif op == "open":
                result = await owner.open(args["target"])
            elif op == "read":
                result = base64.b64encode(await owner.read(args["socket"])).decode()
            elif op == "write":
                await owner.write(args["socket"], base64.b64decode(args["data"]), bool(args["end"]))
                result = None
            elif op == "close_socket":
                await owner.close_socket(args["socket"])
                result = None
            elif op == "close":
                await owner.close()
                result = None
            else:
                raise CapabilityTransportError("capability_operation_unknown")
            send({"id": message["id"], "ok": True, "result": result})
        except (CapabilityTransportError, asyncio.CancelledError, OSError, KeyError, ValueError, TypeError) as error:
            send({"id": message["id"], "ok": False, "error": str(error) or type(error).__name__})
        if op == "close":
            await lines.put(None)

    while (line := await lines.get()) is not None:
        message = json.loads(line)
        if "credit" in message:
            credits.pop(message["credit"]).set_result(bool(message["ok"]))
            continue
        task = asyncio.create_task(handle(message))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
    if owner is not None:
        await owner.close()
    for future in credits.values():
        future.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(serve())
    sys.stdout.flush()
    os._exit(0)  # The stdin pump is a daemon thread blocked in readline; do not wait for it.
