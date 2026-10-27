# SPDX-License-Identifier: MIT
"""Developer-only MCP stdio byte transport: one Job-owned server, bounded frames.

The server is launched through the trusted developer shell primitive (suspended
until assigned to a Windows Job Object, minimal explicit environment). MCP
protocol semantics stay in native OpenCode: this module only moves newline
delimited frames and settles every descendant on close. Not a sandbox.
"""
from __future__ import annotations

import asyncio
from queue import Empty, Full, Queue
from threading import Thread

from .capability_shell import OwnedShell, ShellOwnershipError, TrustedShell

MAX_FRAME_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024


class McpStdioError(Exception):
    pass


def _deny(code):
    raise McpStdioError(code) from None


class OwnedMcpServer:
    def __init__(self, shell: OwnedShell, current):
        self.shell, self.current = shell, current
        self.frames: Queue = Queue(maxsize=8)
        self.closed, self.total = False, 0
        self.reader = Thread(target=self._read, name="renulus-mcp-stdio", daemon=True)
        self.reader.start()

    @classmethod
    def start(cls, argv, *, cwd, workspace, environment, current):
        try:
            shell = TrustedShell.start(argv, cwd=cwd, workspace=workspace, environment=environment,
                current=current, mode="developer", pipes=True)
        except ShellOwnershipError as error:
            _deny(str(error))
        return cls(shell, current)

    def _put(self, item):
        while not self.closed:
            try:
                return self.frames.put(item, timeout=0.05)
            except Full:
                continue

    def _read(self):
        stdout = self.shell.process.stdout
        try:
            while not self.closed:
                line = stdout.readline(MAX_FRAME_BYTES + 1)
                if not line:
                    break
                if len(line) > MAX_FRAME_BYTES or not line.endswith(b"\n"):
                    self._put(McpStdioError("mcp_stdio_frame_limit"))
                    return
                self._put(line[:-1].removesuffix(b"\r"))  # Windows servers write CRLF
        except (OSError, ValueError):
            pass
        finally:
            self._put(None)

    def _next(self):
        while True:
            try:
                return self.frames.get(timeout=0.05)
            except Empty:
                if self.closed:
                    return None

    async def read(self) -> bytes | None:
        """One frame without its newline, or None once the server's stdout ended."""
        frame = await asyncio.get_running_loop().run_in_executor(None, self._next)
        if isinstance(frame, McpStdioError):
            await self.close()
            raise frame
        if frame is not None:
            self._account(len(frame) + 1)
        return frame

    def _account(self, count):
        self.total += count
        if self.closed or not self.current() or self.total > MAX_TOTAL_BYTES:
            _deny("mcp_stdio_stale_or_limit")

    async def write(self, frame: bytes):
        if (not isinstance(frame, bytes) or not frame or len(frame) > MAX_FRAME_BYTES
                or b"\n" in frame or b"\0" in frame):
            _deny("mcp_stdio_frame_invalid")
        self._account(len(frame) + 1)

        def send():
            self.shell.process.stdin.write(frame + b"\n")
            self.shell.process.stdin.flush()
        try:
            await asyncio.get_running_loop().run_in_executor(None, send)
        except (OSError, ValueError):
            _deny("mcp_stdio_closed")

    async def close(self) -> dict:
        """Settle the Job (every descendant); effects of the server stay uncertain."""
        self.closed = True
        try:
            settlement = await asyncio.get_running_loop().run_in_executor(None, self.shell.terminate)
        except ShellOwnershipError as error:
            _deny(str(error))
        # The Job is dead, so stdout reaches EOF and the reader returns.
        self.reader.join(timeout=1)
        for stream in (self.shell.process.stdin, self.shell.process.stdout):
            try:
                stream.close()
            except OSError:
                pass
        return settlement
