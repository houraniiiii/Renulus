from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from .service import UpdatesService


class LiteratureCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_ids: list[str] = Field(min_length=1, max_length=5)
    days: int = Field(default=7, ge=1, le=90)


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(max_length=8000)
    topic_ids: list[str] = Field(default_factory=list, max_length=100)
    reviewer: Literal["learner", "assistant"] = "learner"
    state: Literal["reviewed", "dismissed"]


def create_router(services):
    service = UpdatesService(services)
    services.registry["updates"] = service
    router = APIRouter(prefix="/updates", tags=["updates"])

    @router.get("/sources")
    def sources():
        return {"sources": service.list_sources()}

    @router.get("/entries")
    def entries(reviewed_only: bool = False):
        return {"entries": service.list_entries(reviewed_only)}

    @router.post("/sources/{source_id}/check")
    async def check(source_id: str, force: bool = False):
        return await service.check_source(source_id, force)

    @router.post("/literature/check")
    async def literature(body: LiteratureCheck):
        return await service.check_literature(body.topic_ids, body.days)

    @router.post("/entries/{entry_id}/review")
    def review(entry_id: str, body: Review):
        return service.review(entry_id, body.summary, body.topic_ids, body.reviewer, body.state)

    @router.post("/entries/{entry_id}/read")
    def read(entry_id: str):
        return service.mark_read(entry_id)

    return router
