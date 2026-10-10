import asyncio
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
    on_shutdown: list = field(default_factory=list)
    _shutdown_task: asyncio.Task | None = field(default=None, init=False, repr=False)

    @property
    def stopping(self):
        return self._shutdown_task is not None

    def shutdown_status(self):
        task = self._shutdown_task
        state = ('open' if task is None else 'draining' if not task.done() else
                 'failed' if task.cancelled() or task.exception() else 'settled')
        return {'state': state, 'api_version': 1}

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
        for callback in reversed(self.on_shutdown):
            result = callback()
            if inspect.isawaitable(result):
                await result

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
