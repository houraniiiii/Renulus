# SPDX-License-Identifier: MIT
"""Parent mounts create_router once under /api/v1 after Library/Cases."""
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response

from .reader import ReaderRepository
from .reader_models import ReaderAssetRequest, ReaderRequest, ReaderSelectionRequest


def create_router(services):
    repository = ReaderRepository(services)
    services.registry["readers"] = repository

    async def no_store(response: Response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"

    router = APIRouter(prefix="/readers", tags=["readers"], dependencies=[Depends(no_store)])

    @router.post("/resolve")
    def resolve(body: ReaderRequest):
        return repository.resolve(body)

    @router.post("/asset")
    def asset(body: ReaderAssetRequest):
        return Response(repository.asset(body), media_type="image/png", headers={
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox"})

    @router.post("/original")
    def original(body: ReaderRequest):
        source = repository.original(body)
        return Response(source.data, media_type="application/octet-stream", headers={
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(source.filename, safe=""),
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox"})

    @router.post("/passage")
    def passage(body: ReaderSelectionRequest):
        return repository.passage(body)

    return router
