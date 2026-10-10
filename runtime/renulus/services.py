import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
import inspect
from typing import Any

from .storage import AppPaths, Database


@dataclass
class Services:
    paths: AppPaths
    db: Database
    registry: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, dict] = field(default_factory=dict)
    on_startup: list = field(default_factory=list)
    on_stopping: list = field(default_factory=list)
    on_shutdown: list = field(default_factory=list)
    on_shutdown_dependencies: list = field(default_factory=list)
    _shutdown_task: asyncio.Task | None = field(default=None, init=False, repr=False)
    _requests: dict[asyncio.Task, Callable] = field(default_factory=dict, init=False, repr=False)

    @property
    def stopping(self):
        return self._shutdown_task is not None

    def shutdown_status(self):
        task = self._shutdown_task
        state = ('open' if task is None else 'draining' if not task.done() else
                 'failed' if task.cancelled() or task.exception() else 'settled')
        return {'state': state, 'api_version': 1}

    def admit_request(self, operation, interrupt):
        from .contracts import ApiError
        if self.stopping:
            raise ApiError('runtime_stopping',
                'Renulus is closing this profile. Wait for local work to finish', 503, True)
        task = asyncio.create_task(operation(), name='renulus-owned-request')
        self._requests[task] = interrupt
        task.add_done_callback(self._request_settled)
        return task

    def _request_settled(self, task):
        self._requests.pop(task, None)
        if not task.cancelled():
            task.exception()  # Observe errors even after the client has left.

    async def drain_requests(self):
        requests = tuple(self._requests)
        if requests:
            await asyncio.gather(*(asyncio.shield(task) for task in requests), return_exceptions=True)

    async def shutdown(self, *, timeout=None):
        from .contracts import ApiError
        if self._shutdown_task is None:
            self._shutdown_task = asyncio.create_task(self._shutdown(), name='renulus-profile-drain')
        # Observation timeout/cancellation does not cancel the profile owner.
        done, _ = await asyncio.wait({self._shutdown_task}, timeout=timeout)
        if not done:
            raise ApiError('runtime_shutdown_pending',
                'Renulus is still finishing local work. Keep this profile open and retry closing', 503, True)
        if self.shutdown_status()['state'] == 'failed':
            raise ApiError('runtime_shutdown_failed',
                'Local cleanup failed. This profile remains owned and cannot close yet', 503, True)
        return self.shutdown_status()

    async def _shutdown(self):
        for interrupt in tuple(self._requests.values()):
            interrupt()
        for callback in self.on_stopping:
            callback()  # Signal-only hooks must not wait for settlement.

        async def finish(callback):
            result = callback()
            if inspect.isawaitable(result):
                await result

        # Start every producer's cancellation before awaiting a slow join.
        # Dependencies remain live until all producers and requests settle.
        owners = [asyncio.create_task(finish(callback)) for callback in reversed(self.on_shutdown)]
        if owners:
            outcomes = await asyncio.gather(*owners, return_exceptions=True)
            for outcome in outcomes:
                if isinstance(outcome, BaseException):
                    raise outcome
        await self.drain_requests()
        for callback in reversed(self.on_shutdown_dependencies):
            await finish(callback)

    async def finish_shutdown(self):
        """Lifespan owns the loop until the shared drain has really finished."""
        from .contracts import ApiError
        blocked = asyncio.Event()
        while True:
            try:
                if self.shutdown_status()['state'] == 'failed':
                    # A failed callback is not permission to release its
                    # dependencies or acknowledge a clean process shutdown.
                    await blocked.wait()
                await self.shutdown()
                return
            except (asyncio.CancelledError, ApiError):
                # Request observers may leave; application ownership may not.
                continue

    def get(self, name: str):
        from .contracts import ApiError
        if name not in self.registry:
            raise ApiError("capability_unavailable", f"{name.capitalize()} is not ready", 503, True)
        return self.registry[name]
