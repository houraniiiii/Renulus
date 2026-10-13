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
    _shutdown_plan: tuple | None = field(default=None, init=False, repr=False)
    _shutdown_settled: set = field(default_factory=set, init=False, repr=False)

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
        if self._shutdown_plan is None:
            # Freeze identity AND order at the first close. Later list edits may
            # not replay released resources or substitute an unsettled owner.
            self._shutdown_plan = (tuple(self._requests.values()), tuple(self.on_stopping),
                                   tuple(reversed(self.on_shutdown)),
                                   tuple(reversed(self.on_shutdown_dependencies)))
        if self._shutdown_task is None or self.shutdown_status()['state'] == 'failed':
            self._shutdown_task = asyncio.create_task(self._shutdown(), name='renulus-profile-drain')
        # Observation timeout/cancellation does not cancel the profile owner.
        if not self._shutdown_task.done():
            done, _ = await asyncio.wait({self._shutdown_task}, timeout=timeout)
            if not done:
                raise ApiError('runtime_shutdown_pending',
                    'Renulus is still finishing local work. Keep this profile open and retry closing', 503, True)
        if self.shutdown_status()['state'] == 'failed':
            raise ApiError('runtime_shutdown_failed',
                'Local cleanup failed. This profile remains owned and cannot close yet', 503, True)
        return self.shutdown_status()

    async def _shutdown(self):
        interrupts, signals, producers, dependencies = self._shutdown_plan
        for stage, callbacks in (('interrupt', interrupts), ('signal', signals)):
            for ordinal, callback in enumerate(callbacks):
                key = (stage, ordinal)
                if key not in self._shutdown_settled:
                    callback()  # Signal-only hooks must not wait for settlement.
                    self._shutdown_settled.add(key)

        async def finish(stage, ordinal, callback):
            key = (stage, ordinal)
            if key in self._shutdown_settled:
                return
            result = callback()
            if inspect.isawaitable(result):
                await result
            self._shutdown_settled.add(key)

        # Start every producer's cancellation before awaiting a slow join.
        # Successful siblings are never repeated after another producer fails.
        owners = [asyncio.create_task(finish('producer', ordinal, callback))
                  for ordinal, callback in enumerate(producers)
                  if ('producer', ordinal) not in self._shutdown_settled]
        if owners:
            outcomes = await asyncio.gather(*owners, return_exceptions=True)
            for outcome in outcomes:
                if isinstance(outcome, BaseException):
                    raise outcome
        if ('requests', 0) not in self._shutdown_settled:
            await self.drain_requests()
            self._shutdown_settled.add(('requests', 0))
        for ordinal, callback in enumerate(dependencies):
            await finish('dependency', ordinal, callback)

    async def finish_shutdown(self):
        """Retain lifespan ownership and retry only unsettled frozen stages."""
        from .contracts import ApiError
        while True:
            try:
                await self.shutdown()
                return
            except asyncio.CancelledError:
                # Observers may leave; application ownership may not.
                continue
            except ApiError:
                # Persistent failure retains all later dependencies without a
                # tight spin; a transient native close can really resume.
                await asyncio.sleep(.1)

    def get(self, name: str):
        from .contracts import ApiError
        if name not in self.registry:
            raise ApiError("capability_unavailable", f"{name.capitalize()} is not ready", 503, True)
        return self.registry[name]
