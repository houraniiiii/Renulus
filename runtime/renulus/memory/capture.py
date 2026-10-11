"""Trusted committed-answer extraction ports; no provider or record ownership."""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import inspect
import sqlite3
from typing import Literal, Protocol

from renulus.design_c_contracts import EligibleInput
from renulus.contracts import ApiError

FrozenMessages = tuple[tuple[Literal['system', 'user', 'assistant'], str], ...]


@dataclass(frozen=True)
class CommittedCapture:
    """Exact claimed job and committed-evidence pin; contains no answer body."""
    job_id: str
    attempt: int
    fingerprint: str
    scope_json: str
    project_id: str | None
    input: EligibleInput


class CaptureCurrent(Protocol):
    """Local None-or-raise check; a supplied connection must be reused."""
    def __call__(self, *, conn: sqlite3.Connection | None = None) -> None: ...


@dataclass(frozen=True)
class CaptureBinding:
    """One attempt's trusted native resource owner.

    cancel only signals. settle joins actual loop/transport finalizers, even if
    generation raised; release follows CPU settlement and a durable job outcome.
    current and require_publication_in perform local checks without IO/await.
    """
    generate: Callable[[FrozenMessages], Awaitable[str]]
    current: CaptureCurrent
    require_publication_in: Callable[[sqlite3.Connection], None]
    cancel: Callable[[], None]
    settle: Callable[[], Awaitable[None]]
    release: Callable[[], None]


class PrepareCapture(Protocol):
    """Synchronous local factory on the original loop, before CPU submission."""
    def __call__(self, request: CommittedCapture, *, current: CaptureCurrent) -> CaptureBinding: ...


def _local_result(result):
    if result is not None:
        if inspect.iscoroutine(result):
            result.close()
        raise ApiError('memory_generation_not_scoped', 'Capture guards must be synchronous local checks', 503)
