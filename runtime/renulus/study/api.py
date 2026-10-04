from datetime import date
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from .service import StudyService


class Goals(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hours_per_week: int = Field(default=3, ge=1, le=40)
    exam_date: date | None = None
    topic_ids: list[str] = Field(default_factory=list, max_length=100)
    track: Literal["general", "eseneph"] = "general"


class ChangeActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    due_date: date | None = None
    state: Literal["planned", "completed", "skipped"] | None = None


def create_router(services):
    service = StudyService(services)
    services.registry["study"] = service
    router = APIRouter(prefix="/study", tags=["study"])

    @router.get("/home")
    def home():
        return service.home()

    @router.get("/goals")
    def goals():
        return service.goals()

    @router.put("/goals")
    def update_goals(body: Goals):
        return service.save_goals(body.model_dump(mode="json"))

    @router.get("/plan")
    def plan():
        return {"activities": service.list_activities()}

    @router.post("/plan/propose")
    def propose():
        return service.propose()

    @router.patch("/plan/{activity_id}")
    def change(activity_id: str, body: ChangeActivity):
        return service.change_activity(activity_id, body.model_dump(mode="json", exclude_none=True))

    @router.get("/progress")
    def progress():
        return service.progress()

    return router
