# SPDX-License-Identifier: MIT
"""Actual synthetic sockets/HTTP; no owner profile or provider."""
import asyncio
import hashlib
import time
import unittest
from renulus.workers.capability_transport import CapabilityTransport, CapabilityTransportError, Endpoint, NetworkLease


class CapabilityTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.connected = {"a": 0, "b": 0}
        self.writers = []
        self.current = True
        self.credits = []

        async def handler(reader, writer, name):
            self.connected[name] += 1
            self.writers.append(writer)
            try:
                data = await reader.read(65536)
                if data.startswith(b"GET"):
                    writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 9\r\nContent-Type: text/plain\r\n\r\nSYNTHETIC")
                else:
                    writer.write(data)
                await writer.drain()
                await reader.read()
            finally:
                writer.close()
                await writer.wait_closed()

        self.a = await asyncio.start_server(lambda r,w:handler(r,w,"a"), "127.0.0.1", 0)
        self.b = await asyncio.start_server(lambda r,w:handler(r,w,"b"), "127.0.0.1", 0)
        self.port_a = self.a.sockets[0].getsockname()[1]
        self.port_b = self.b.sockets[0].getsockname()[1]
        self.owners = []

    async def asyncTearDown(self):
        for owner in self.owners:
            await owner.close()
        for writer in self.writers:
            writer.close()
        self.a.close()
        self.b.close()
        await self.a.wait_closed()
        await self.b.wait_closed()

    def owner(self, *, ttl=30000, limit=65536, private=True):
        async def credit(identity, count):
            self.credits.append((identity,count,self.current))
            return self.current
        owner = CapabilityTransport(NetworkLease("synthetic_lease", (Endpoint("127.0.0.1",self.port_a,private),),
            int(time.time()*1000)+ttl,max_bytes=limit),current=credit)
        self.owners.append(owner)
        return owner

    async def test_actual_streams_cannot_open_distinct_endpoint_or_admit_late_bytes(self):
        owner = self.owner()
        identity = await owner.open({"host":"127.0.0.1","port":self.port_a})
        await owner.write(identity,b"SYNTHETIC")
        self.assertEqual(await owner.read(identity),b"SYNTHETIC")
        with self.assertRaises(CapabilityTransportError):
            await owner.open({"host":"127.0.0.1","port":self.port_b})
        self.assertEqual(self.connected["b"],0)
        waiting = asyncio.create_task(owner.read(identity))
        await asyncio.sleep(0.01)
        before = owner.bytes
        self.current = False
        # Bytes buffered by an already admitted peer cannot become a new read credit.
        self.writers[0].write(b"LATE_WEBSOCKET_FRAME")
        await self.writers[0].drain()
        with self.assertRaises(CapabilityTransportError):
            await waiting
        self.assertEqual(owner.bytes,before)
        with self.assertRaises(CapabilityTransportError):
            await owner.write(identity,b"LATE_WRITE")
        await owner.close()
        self.assertFalse(owner.sockets)
        self.assertFalse(owner.tasks)

    async def test_http_is_dns_pinned_and_private_network_requires_explicit_grant(self):
        owner = self.owner()
        stream = await owner.http(url=f"http://127.0.0.1:{self.port_a}/synthetic",body_sha256=hashlib.sha256(b"").hexdigest())
        self.assertEqual(stream.status,200)
        self.assertEqual(await stream.read(),b"SYNTHETIC")
        self.assertIsNone(await stream.read())
        await stream.close()
        denied = self.owner(private=False)
        with self.assertRaises(CapabilityTransportError):
            await denied.open({"host":"127.0.0.1","port":self.port_a})
        self.assertEqual(self.connected["a"],1)

    async def test_expiry_and_shared_byte_limit_destroy_owned_sockets(self):
        owner = self.owner(ttl=500,limit=10)
        identity = await owner.open({"host":"127.0.0.1","port":self.port_a})
        await owner.write(identity,b"123456")
        with self.assertRaises(CapabilityTransportError):
            await owner.write(identity,b"12345")
        await asyncio.sleep(0.6)
        self.assertTrue(owner.closed)
        self.assertFalse(owner.sockets)


if __name__ == "__main__":
    unittest.main()
