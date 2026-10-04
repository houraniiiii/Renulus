"""One generative seam consumed by all modules and implemented by the Hermes adapter."""
from collections.abc import AsyncIterator
from typing import Protocol

from .contracts import ContextScope


class Provider(Protocol):
    def status(self) -> dict: ...

    def stream(self, messages: list[dict], *, scope: ContextScope, run_id: str,
               model: str | None = None, system: str | None = None,
               purpose: str = "explain") -> AsyncIterator[str]: ...

    async def cancel(self, run_id: str) -> bool: ...
