# SPDX-License-Identifier: MIT
"""Progress polling is read-only. Model work needs an explicit create or retry."""
import sqlite3
import inspect

from fastapi import APIRouter, Response

from renulus.contracts import ApiError
from .generation_models import AcceptShorterRequest, CreateGenerationRequest, GenerationAction
from .generation_service import SavedGenerationService


def create_router(services):
    service = SavedGenerationService(services)
    services.registry["saved_generation"] = service
    router = APIRouter(prefix="/assessment/generation", tags=["saved-generation"])

    async def call(method, *args):
        try:
            value = method(*args)
            return await value if inspect.isawaitable(value) else value
        except sqlite3.Error as error:
            raise ApiError("assessment_storage_failed", "Generation storage is unavailable. Your prior checkpoint is retained; retry explicitly", 503, True) from error

    @router.get("/jobs")
    async def jobs(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return await call(service.list_jobs)

    @router.get("/jobs/{identifier}")
    async def job(identifier: str, response: Response):
        response.headers["Cache-Control"] = "no-store"
        return await call(service.read, identifier)

    @router.post("/jobs", status_code=202)
    async def create(body: CreateGenerationRequest):
        return await call(service.create, body)

    @router.post("/quick-practice", status_code=202)
    async def quick(body: CreateGenerationRequest):
        return await call(service.quick_practice, body)

    @router.post("/jobs/{identifier}/retry")
    async def retry(identifier: str, body: GenerationAction):
        return await call(service.action, identifier, "retry", body)

    @router.post("/jobs/{identifier}/cancel")
    async def cancel(identifier: str, body: GenerationAction):
        return await call(service.action, identifier, "cancel", body)

    @router.post("/jobs/{identifier}/accept-shorter")
    async def accept(identifier: str, body: AcceptShorterRequest):
        return await call(service.action, identifier, "accept_shorter", body)

    return router
