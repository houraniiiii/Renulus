# SPDX-License-Identifier: MIT
"""Ordered SSE through the shared approved Provider, with no durable run logs."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress

from renulus.contracts import ApiError, Event

from .repository import CaseRepository, Run


def sse(event: Event) -> str:
    return (f"id: {event.id}\nevent: {event.type}\n"
            f"data: {event.model_dump_json()}\n\n")


def _consume_task(task):
    # A provider that ignores cancellation must not log a later raw exception.
    with suppress(BaseException):
        task.result()


async def _next_delta(iterator, cancel: asyncio.Event):
    delta_task = asyncio.ensure_future(anext(iterator))
    cancel_task = asyncio.create_task(cancel.wait())
    try:
        ready, _ = await asyncio.wait((delta_task, cancel_task),
                                      return_when=asyncio.FIRST_COMPLETED)
        if cancel_task in ready or cancel.is_set():
            raise ApiError("case_run_cancelled", "This response was stopped", 409)
        return delta_task.result()
    finally:
        cancel_task.cancel()
        delta_task.cancel()
        delta_task.add_done_callback(_consume_task)
        with suppress(asyncio.CancelledError):
            await cancel_task


async def cancel_provider(repo: CaseRepository, run_id: str):
    provider = repo.services.registry.get("provider")
    if provider is not None:
        # Adapter cancellation may fail offline. The local guard already prevents
        # all late deltas/commits and cancellation must remain responsive.
        with suppress(Exception):
            await asyncio.wait_for(provider.cancel(run_id), timeout=2)


def safe_error(error: Exception, *, trusted_runtime: bool = False) -> dict:
    if trusted_runtime and isinstance(error, ApiError):
        # ProviderManager has already mapped raw SDK failures to its public
        # contract. Preserve policy denials and their non-retryable meaning.
        return {"code": error.code, "message": error.message, "retryable": error.retryable}
    # Provider exceptions may contain echoed raw prompts/tokens. Never stringify
    # them in events, logs, cache, memory or any canonical record.
    messages = {
        "capability_unavailable": "The approved model connection is not ready",
        "authentication_required": "Connect an approved subscription to discuss the case",
        "auth_required": "Connect an approved subscription to discuss the case",
        "model_unavailable": "The selected approved model is unavailable",
        "quota_exceeded": "The selected subscription has reached its usage limit",
        "provider_unavailable": "The approved model connection is unavailable; try again",
        "case_revision_conflict": "The case changed before this response completed",
        "case_run_superseded": "The case changed before this response completed",
        "case_response_invalid": "The provider did not return a usable response",
        "case_response_too_large": "The response exceeded the case limit",
        "case_context_full": "Start a new session for further discussion",
        "image_capabilities_unverified": "The selected account has no verified image-input model. Check Connections",
        "image_input_unsupported": "The selected account does not support image input for this model",
        "connection_changed": "The selected connection changed. Review the image and send it again",
    }
    if isinstance(error, ApiError) and error.code in messages:
        return {"code": error.code, "message": messages[error.code], "retryable": error.retryable}
    return {"code": "case_discussion_failed",
            "message": "The response could not finish. Your temporary case is still open",
            "retryable": True}


async def discuss(repo: CaseRepository, run: Run, messages: list[dict]) -> AsyncIterator[Event]:
    provider = None
    iterator = None
    with repo._lock:
        if run.terminal and run.events:
            # Replaying is volatile, never a second inference or saved operation.
            repo._load(run.case_id)
            replay = list(run.events)
        else:
            replay = None
            if run.status == "running":
                raise ApiError("case_busy", "This response is already running", 409, True)
            if not run.cancel.is_set():
                run.status = "running"
    if replay is not None:
        for event in replay:
            with repo._lock:
                repo._load(run.case_id)
            yield event
        return
    yield repo.event(run, "started", {"case_id": run.case_id, "revision": run.revision,
                                    "scope": run.scope.model_dump(mode="json")})
    try:
        with repo._lock:
            repo._current_run(run)
        provider = repo.services.get("provider")
        system = messages[0]["content"]
        # Exact shared generation.Provider seam. Scope is set before the call.
        if run.mode == 'image':
            from .images import require_image_model
            require_image_model(repo.services, run.model)
        iterator = provider.stream(messages[1:], scope=run.scope, run_id=run.id,
                                   model=run.model, system=system,
                                   purpose='case-image-discuss' if run.mode == 'image' else 'case-discuss')
        run.iterator = iterator
        while True:
            try:
                delta = await _next_delta(iterator, run.cancel)
            except StopAsyncIteration:
                break
            if not isinstance(delta, str):
                raise ApiError("case_response_invalid", "The provider did not return text", 502, True)
            if delta:
                yield repo.append_delta(run, delta)
        yield repo.complete(run)
    except asyncio.CancelledError:
        repo.cancel(run.id)
        repo.finish_error(run, cancelled=True)
        raise
    except Exception as error:
        from renulus.runtime.manager import ProviderManager
        cancelled = run.cancel.is_set() or (isinstance(error, ApiError) and
                    error.code in ("case_deleted", "case_run_cancelled", "case_not_found"))
        yield repo.finish_error(run, cancelled=cancelled,
                               error=None if cancelled else safe_error(error,
                                   trusted_runtime=isinstance(provider, ProviderManager)))
    finally:
        if run.status != "completed":
            await cancel_provider(repo, run.id)
        if iterator is not None and hasattr(iterator, "aclose"):
            with suppress(Exception):
                await asyncio.wait_for(iterator.aclose(), timeout=1)
        run.iterator = None
        # Release raw request context retained by the generator as soon as possible.
        messages.clear()


async def events(repo: CaseRepository, run: Run, messages: list[dict]) -> AsyncIterator[str]:
    async for event in discuss(repo, run, messages):
        yield sse(event)
