from typing import Literal

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from .service import UpdatesService
from .models import ReviewedEvidence, SourceChanges, SourceTarget


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
    evidence: list[ReviewedEvidence] = Field(default_factory=list, max_length=20)
    target: SourceTarget | None = None
    changes: SourceChanges | None = None


class TrackPublication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(max_length=3)
    url: str = Field(max_length=2000)
    permission_reference: str = Field(min_length=1, max_length=1000)
    max_bytes: int = Field(default=16_000_000, ge=1024, le=20_000_000)


class ScheduledRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["source", "publication", "literature"]
    id: str = Field(min_length=1, max_length=200)


class ScheduleSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    cadence_hours: int = Field(default=24, ge=24, le=720)
    selection: list[ScheduledRoute] = Field(default_factory=list, max_length=20)


def create_router(services):
    service = UpdatesService(services)
    services.registry["updates"] = service
    router = APIRouter(prefix="/updates", tags=["updates"])

    @router.get("/schedule")
    def schedule():
        return service.scheduling.status()

    @router.put("/schedule")
    async def configure_schedule(body: ScheduleSettings):
        return service.scheduling.configure(**body.model_dump())

    @router.post("/schedule/check")
    async def check_selection():
        service.scheduling.begin()
        return service.scheduling.status()

    @router.post("/schedule/cancel")
    async def cancel_schedule():
        return await service.scheduling.cancel()

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

    @router.get("/sources/{source_id}/status")
    def source_status(source_id: str):
        return {"statuses": service.reviews.statuses(source_id)}

    @router.get("/entries/{entry_id}/affected")
    def affected(entry_id: str, limit: int = Query(100, ge=1, le=250), offset: int = Query(0, ge=0)):
        service.get_entry(entry_id)
        return service.affected.for_entry(entry_id, limit, offset)

    @router.get("/affected/{kind}/{entity_id}/versions/{version}")
    def annotations(kind: Literal["question", "case"], entity_id: str, version: int = Path(ge=1)):
        return service.affected.needs_re_review(kind, entity_id, version)

    @router.post("/entries/{entry_id}/sync")
    def sync(entry_id: str):
        return service.reviews.sync_entry(entry_id)

    @router.get("/literature/checks")
    def literature_checks():
        return {"checks": service.literature.checks()}

    @router.post("/entries/{entry_id}/refresh")
    async def refresh(entry_id: str):
        return await service.scheduling.manual(service.refresh_entry, entry_id)

    @router.post("/publications")
    def track(body: TrackPublication):
        return service.publications.track(**body.model_dump())

    @router.post("/publications/{publication_id}/check")
    async def check_publication(publication_id: str, force: bool = False):
        return await service.scheduling.manual(service.publications.check, publication_id, force)

    @router.delete("/publications/{publication_id}")
    def stop_publication(publication_id: str):
        return service.publications.stop(publication_id)

    @router.post("/sources/{source_id}/check")
    async def check(source_id: str, force: bool = False):
        return await service.scheduling.manual(service.check_source, source_id, force)

    @router.post("/literature/check")
    async def literature(body: LiteratureCheck):
        return await service.scheduling.manual(service.check_literature, body.topic_ids, body.days)

    @router.post("/entries/{entry_id}/review")
    def review(entry_id: str, body: Review):
        return service.review(entry_id, body.summary, body.topic_ids, body.reviewer, body.state,
                              evidence=[item.model_dump(mode="json") for item in body.evidence],
                              target=body.target.model_dump(exclude_none=True) if body.target else None,
                              changes=body.changes.model_dump(mode="json", exclude_unset=True) if body.changes else None)

    @router.post("/entries/{entry_id}/read")
    def read(entry_id: str):
        return service.mark_read(entry_id)

    return router
