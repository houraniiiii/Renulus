import json
from contextlib import aclosing
from typing import Literal

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from renulus.contracts import ContextScope, Event, durable_id
from .service import LearnService


class NewThread(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="New study", max_length=120)
    topic_id: str | None = None
    teaching_style: Literal["direct", "guided"] = "direct"


class Ask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=16000)
    scope: ContextScope
    thread_id: str | None = None
    topic_id: str | None = None
    teaching_style: Literal["direct", "guided"] = "direct"
    model: str | None = None
    freshness: bool | None = None
    case_handoff_id: str | None = Field(default=None, max_length=120)


def create_router(services):
    service = LearnService(services)
    services.registry["learn"] = service
    router = APIRouter(prefix="/learn", tags=["learn"])

    @router.get("/threads")
    def threads():
        return {"threads": service.list_threads()}

    @router.post("/threads")
    def create(body: NewThread):
        return service.create_thread(body.title, body.topic_id, body.teaching_style)

    @router.get("/threads/{thread_id}")
    def thread(thread_id: str):
        return service.get_thread(thread_id)

    @router.delete("/threads/{thread_id}")
    async def delete(thread_id: str):
        return await service.delete_thread(thread_id)

    @router.post("/ask")
    async def ask(body: Ask, idempotency_key: str | None = Header(default=None)):
        replay, run = service.prepare(body.question, body.scope, body.thread_id, body.topic_id,
                                     body.teaching_style, idempotency_key or durable_id("request"),
                                     case_handoff_id=body.case_handoff_id)
        async def events():
            if replay:
                assistant = service.db.fetch_one(
                    "SELECT content,citations_json FROM learn_messages WHERE run_id=? AND role='assistant'",
                    (replay["id"],))
                payload = {"thread_id": replay["thread_id"], "replayed": True,
                           "text": assistant["content"] if assistant else "",
                           "citations": json.loads(assistant["citations_json"]) if assistant else []}
                event = Event(run_id=replay["id"], sequence=1, type="completed", payload=payload)
                yield f"id: {event.id}\nevent: completed\ndata: {event.model_dump_json()}\n\n"
                return
            async with aclosing(service.answer(run, body.question, body.teaching_style,
                                              body.topic_id, body.model, freshness=body.freshness)) as stream:
                async for event in stream:
                    yield f"id: {event.id}\nevent: {event.type}\ndata: {event.model_dump_json()}\n\n"
        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @router.post("/runs/{run_id}/cancel")
    async def cancel(run_id: str):
        return await service.cancel(run_id)

    return router
