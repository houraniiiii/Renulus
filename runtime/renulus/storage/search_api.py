# SPDX-License-Identifier: MIT
from fastapi import APIRouter, Query, Response
from .search import LocalSearch


def create_router(services):
    search = LocalSearch(services)
    router = APIRouter(prefix="/search", tags=["search"])

    @router.get("")
    def find(response: Response, q: str = Query(default="", max_length=200),
             project_id: str | None = Query(default=None, min_length=1, max_length=128),
             archived: bool = False, limit: int = Query(default=30, ge=1, le=50),
             cursor: str | None = Query(default=None, max_length=2000)):
        response.headers["Cache-Control"] = "no-store"
        return search.find(q, project_id=project_id, archived=archived, limit=limit, cursor=cursor)

    return router
