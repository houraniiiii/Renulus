# SPDX-License-Identifier: MIT
"""Home router; integration owner mounts create_router under /api/v1."""
from typing import Annotated

from fastapi import APIRouter, Header, Response

from .home_models import NameUpdate
from .home_service import HomeService

Key = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def create_router(services):
    service = HomeService(services)
    services.registry["home"] = service
    router = APIRouter(prefix="/home", tags=["home"])

    @router.get("")
    async def home(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return service.read()

    @router.get("/preferences")
    async def preferences(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return service.preferences()

    @router.put("/preferences")
    async def save_name(body: NameUpdate, idempotency_key: Key, response: Response):
        response.headers["Cache-Control"] = "no-store"
        return service.save_name(body, idempotency_key)

    @router.post("/suggestions/refresh", status_code=202)
    async def refresh(idempotency_key: Key, response: Response):
        response.headers["Cache-Control"] = "no-store"
        return await service.refresh()

    return router
