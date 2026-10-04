# SPDX-License-Identifier: MIT
"""Cases API; the server mounts this router once under /api/v1."""

import sqlite3

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse

from renulus.contracts import ApiError

from .models import (AttachmentInput, DiscussCase, EditCase, HandoffCase, RevisionInput, StartCase)
from .repository import CaseRepository
from .streaming import cancel_provider, events


def create_router(services) -> APIRouter:
    repository = CaseRepository(services)
    services.registry["cases"] = repository
    async def no_store(response: Response):
        response.headers["Cache-Control"] = "no-store"

    router = APIRouter(prefix="/cases", tags=["cases"], dependencies=[Depends(no_store)])

    @router.get("/capabilities")
    async def capabilities():
        return {"inputs": {
            "text": {"supported": True, "max_characters": 50000},
            "image": {"supported": False, "code": "volatile_image_unavailable",
                      "reason": "A verified in-memory image route is not installed"},
            "pdf": {"supported": False, "code": "volatile_pdf_unavailable",
                    "reason": "A verified in-memory PDF route is not installed"}},
            "discussion": {"adapter_installed": "provider" in services.registry,
                           "scope": "temporary-case"},
            "teaching": {"content_installed": "content" in services.registry},
            "handoffs": {"explain": "guarded-reference",
                         "generated-practice": "guarded-reference"},
            "memory_capture": False}

    @router.get("/teaching")
    async def teaching():
        return {"cases": repository.list_teaching()}

    @router.get("/saved")
    async def saved():
        return {"cases": repository.list_saved()}

    @router.post("/sessions", status_code=201)
    async def start(body: StartCase):
        return repository.start(body)

    @router.get("/sessions/{case_id}")
    async def get(case_id: str):
        return repository.get(case_id)

    @router.patch("/sessions/{case_id}")
    async def edit(case_id: str, body: EditCase):
        return repository.edit(case_id, body)

    @router.delete("/sessions/{case_id}")
    async def delete(case_id: str, revision: int | None = Query(default=None, ge=1)):
        # Local invalidation precedes the adapter cancellation call.
        active = [run.id for run in repository._runs.values()
                  if run.case_id == case_id and not run.terminal]
        result = repository.delete(case_id, revision)
        for run_id in active:
            await cancel_provider(repository, run_id)
        return result

    @router.post("/sessions/{case_id}/close")
    async def close(case_id: str, body: RevisionInput):
        active = repository.get(case_id)["active_run_id"]
        result = repository.close(case_id, body.revision)
        if active:
            await cancel_provider(repository, active)
        return result

    @router.post("/sessions/{case_id}/save")
    async def save(case_id: str, body: RevisionInput):
        try:
            return repository.save(case_id, body.revision)
        except sqlite3.Error:
            raise ApiError("case_save_failed", "The case could not be saved. Your temporary work is still open",
                           503, True) from None

    @router.post("/sessions/{case_id}/reveal")
    async def reveal(case_id: str, body: RevisionInput):
        return repository.reveal(case_id, body.revision)

    @router.post("/sessions/{case_id}/handoff", status_code=201)
    async def handoff(case_id: str, body: HandoffCase):
        return repository.handoff(case_id, body)

    @router.delete("/handoffs/{ticket_id}")
    async def cancel_handoff(ticket_id: str):
        return repository.cancel_handoff(ticket_id)

    @router.post("/sessions/{case_id}/attachments")
    async def attachment(case_id: str, body: AttachmentInput):
        current = repository.get(case_id)
        if current["revision"] != body.revision:
            raise ApiError("case_revision_conflict", "Reload the current case and try again", 409, True)
        raise ApiError(f"volatile_{body.kind}_unavailable",
                       f"A verified in-memory {body.kind.upper()} route is not installed", 409)

    @router.post("/sessions/{case_id}/discuss")
    async def discuss(case_id: str, body: DiscussCase):
        run, messages = repository.begin_discussion(case_id, body)
        return StreamingResponse(events(repository, run, messages), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no",
                                          "X-Renulus-Run-ID": run.id})

    @router.get("/runs/{run_id}")
    async def run_status(run_id: str):
        return repository.run_status(run_id)

    @router.post("/runs/{run_id}/cancel")
    async def cancel(run_id: str):
        result = repository.cancel(run_id)
        if result["status"] == "cancelled":
            await cancel_provider(repository, run_id)
        return result

    return router
