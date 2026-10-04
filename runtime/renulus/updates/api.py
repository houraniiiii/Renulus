from typing import Literal

from fastapi import APIRouter, Query
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


class TrackPublication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(max_length=3)
    url: str = Field(max_length=2000)
    permission_reference: str = Field(min_length=1, max_length=1000)
    max_bytes: int = Field(default=16_000_000, ge=1024, le=20_000_000)


def create_router(services):
    service = UpdatesService(services)
    services.registry["updates"] = service
    router = APIRouter(prefix="/updates", tags=["updates"])

    @router.get("/sources")
    def sources():
        return {"sources": service.list_sources()}

    @router.get("/entries")
    def entries(reviewed_only: bool = False, limit: int = Query(50, ge=1, le=250),
                offset: int = Query(0, ge=0), state: Literal["pending", "reviewed", "dismissed"] | None = None):
        return service.entries_page(reviewed_only=reviewed_only, limit=limit, offset=offset, state=state)

    @router.get("/entries/{entry_id}")
    def entry(entry_id: str):
        return service.get_entry(entry_id)

    @router.get("/publications")
    def publications():
        return {"publications": service.publications.list()}

    @router.get("/sources/{source_id}/publications")
    def publication_candidates(source_id: str):
        return {"candidates": service.publications.candidates(source_id)}

    @router.post("/publications")
    def track(body: TrackPublication):
        return service.publications.track(**body.model_dump())

    @router.post("/publications/{publication_id}/check")
    async def check_publication(publication_id: str, force: bool = False):
        return await service.publications.check(publication_id, force)

    @router.delete("/publications/{publication_id}")
    def stop_publication(publication_id: str):
        return service.publications.stop(publication_id)

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
