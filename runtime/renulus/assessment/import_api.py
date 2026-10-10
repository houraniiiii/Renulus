# SPDX-License-Identifier: MIT
"""Private imports use explicit create/normalize/review/save actions."""
import inspect
import sqlite3

from fastapi import APIRouter, Depends, Response

from renulus.contracts import ApiError
from .contracts import Command
from .import_models import (CandidateVisibilityRequest, CreateImportRequest,
    EditImportCandidateRequest, ImportRevisionCommand, ResolveImportCandidateRequest)
from .import_service import SavedImportService


def create_router(services):
    service = SavedImportService(services)
    services.registry["saved_imports"] = service

    async def no_store(response: Response):
        response.headers["Cache-Control"] = "no-store"

    router = APIRouter(prefix="/assessment/imports", tags=["saved-imports"], dependencies=[Depends(no_store)])

    async def call(method, *args, **kwargs):
        try:
            value = method(*args, **kwargs)
            return await value if inspect.isawaitable(value) else value
        except sqlite3.Error as error:
            raise ApiError("assessment_storage_failed", "Import storage is unavailable. Retain your edits and retry explicitly", 503, True) from error

    @router.get("")
    async def imports():
        return await call(service.list_imports)

    @router.post("", status_code=201)
    async def create(body: CreateImportRequest):
        return await call(service.create, body)

    @router.get("/{identifier}")
    async def read(identifier: str):
        return await call(service.read, identifier)

    @router.get("/{identifier}/original")
    async def original(identifier: str):
        return await call(service.original, identifier)

    @router.post("/{identifier}/normalize", status_code=202)
    async def normalize(identifier: str, body: ImportRevisionCommand):
        return await call(service.normalize, identifier, body)

    @router.post("/{identifier}/retry", status_code=202)
    async def retry(identifier: str, body: ImportRevisionCommand):
        return await call(service.normalize, identifier, body, retry=True)

    @router.post("/{identifier}/cancel")
    async def cancel(identifier: str, body: Command):
        return await call(service.cancel, identifier, body)

    @router.post("/{identifier}/candidates/{candidate_id}/edit")
    async def edit(identifier: str, candidate_id: str, body: EditImportCandidateRequest):
        return await call(service.mutate_candidate, identifier, candidate_id, "edit", body)

    @router.post("/{identifier}/candidates/{candidate_id}/resolve")
    async def resolve(identifier: str, candidate_id: str, body: ResolveImportCandidateRequest):
        return await call(service.mutate_candidate, identifier, candidate_id, "resolve", body)

    @router.post("/{identifier}/candidates/{candidate_id}/visibility")
    async def visibility(identifier: str, candidate_id: str, body: CandidateVisibilityRequest):
        return await call(service.mutate_candidate, identifier, candidate_id, "visibility", body)

    @router.post("/{identifier}/save")
    async def save(identifier: str, body: ImportRevisionCommand):
        return await call(service.save, identifier, body)

    @router.post("/{identifier}/delete")
    async def delete(identifier: str, body: ImportRevisionCommand):
        return await call(service.delete, identifier, body)

    return router
