"""Closing the public practice response waits for volatile/provider cleanup."""
import asyncio
import json

import pytest

from renulus.assessment.api import create_router
from renulus.assessment.generated_contracts import GenerateRequest

SENTINEL = "SYNTHETIC_PRACTICE_RESPONSE_CLOSE_NEVER_RETAIN"


class ScopedProvider:
    def __init__(self):
        self.active = set()
        self.closed = set()
        self.cancelled = []
        self.calls = []

    def status(self):
        return {"test_adapter": True, "live_provider_verified": False}

    async def stream(self, messages, *, scope, run_id, **kwargs):
        self.calls.append((run_id, scope.kind))
        self.active.add(run_id)
        try:
            yield '{"items": ['
            await asyncio.Event().wait()
        finally:
            self.active.discard(run_id)
            self.closed.add(run_id)

    async def cancel(self, run_id):
        # Cancellation alone cannot satisfy the iterator-close assertion.
        self.cancelled.append(run_id)
        return True


@pytest.mark.asyncio
@pytest.mark.parametrize("context", ["study", "temporary"])
@pytest.mark.parametrize("close_at", ["started", "progress"])
async def test_public_practice_response_waits_for_inner_cleanup(app, tmp_path, context, close_at):
    services = app.state.services
    provider = ScopedProvider()
    services.registry["provider"] = provider
    services.registry["knowledge"] = None
    router = create_router(services)
    repository = services.registry["generated_practice"]
    endpoint = next(route.endpoint for route in router.routes
                    if route.path == "/assessment/practice/generate")
    response = await endpoint(GenerateRequest(prompt=SENTINEL, context=context, count=1,
                              idempotency_key=f"close-{context}-{close_at}"))
    stream = response.body_iterator
    try:
        while True:
            chunk = await anext(stream)
            event = json.loads(next(line[6:] for line in chunk.splitlines()
                                    if line.startswith("data: ")))
            if event["type"] == close_at:
                break
        run = repository.runs[event["run_id"]]
        await stream.aclose()
        # Assert immediately, before GC or an event-loop turn can hide a leak.
        assert run.status == "cancelled"
        assert run.cancel.is_set()
        assert run.prompt == "" and run.messages == []
        assert provider.active == set()
        assert len(provider.calls) == (1 if close_at == "progress" else 0)
        if close_at == "progress":
            assert run.id in provider.cancelled and run.id in provider.closed
        assert sum(item.type in {"completed", "error", "cancelled"}
                   for item in run.events) == 1
        assert services.db.fetch_all("SELECT * FROM assessment_generated_sessions") == []
        assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
        for file in tmp_path.rglob("*"):
            if file.is_file():
                assert SENTINEL.encode() not in file.read_bytes()
    finally:
        await stream.aclose()
