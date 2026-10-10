# SPDX-License-Identifier: MIT
"""Narrow opt-in/status/Stop API; parent mounts and owns neutral policy exemptions."""
from typing import Annotated
import sqlite3

from fastapi import APIRouter, Header, Response

from renulus.contracts import ApiError
from .nightly_models import PreferencesUpdate
from .nightly_service import NightlyService

Key = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def create_router(services):
    service = NightlyService(services)
    services.registry["nightly"] = service
    router = APIRouter(prefix="/nightly", tags=["nightly"])

    @router.get("")
    async def status(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return service.read()

    @router.get("/preferences")
    async def preferences(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return service.preferences()

    @router.put("/preferences")
    async def update(body: PreferencesUpdate, idempotency_key: Key, response: Response):
        response.headers["Cache-Control"] = "no-store"
        try:
            return await service.update_preferences(body, idempotency_key)
        except sqlite3.Error as error:
            raise ApiError("nightly_storage_failed", "Nightly preferences could not be saved. Keep your changes and retry.", 503, True) from error

    @router.post("/jobs/{identifier}/cancel")
    async def cancel(identifier: str, idempotency_key: Key, response: Response):
        response.headers["Cache-Control"] = "no-store"
        return await service.cancel(identifier, idempotency_key)

    return router
