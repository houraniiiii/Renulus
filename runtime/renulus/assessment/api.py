"""Direct JSON module API. The server owns the /api/v1 prefix."""
from fastapi import APIRouter, Query

from .contracts import AnswerRequest, Command, HelpRequest, Selector, StartRequest
from .repository import AssessmentRepository


def create_router(services) -> APIRouter:
    repository = AssessmentRepository(services)
    services.registry["assessment"] = repository
    router = APIRouter(prefix="/assessment", tags=["assessment"])

    @router.get("/catalog")
    def catalog(track: str | None = None):
        return repository.catalog(Selector(track=track))

    @router.get("/aggregates")
    def aggregates():
        return repository.aggregates()

    @router.get("/progress")
    def progress():
        return repository.progress_summary()

    @router.get("/mistakes")
    def mistakes(limit: int = Query(default=100, ge=1, le=100)):
        return {"mistakes": repository.mistakes(limit)}

    @router.post("/start")
    def start(request: StartRequest):
        return repository.start(request)

    @router.get("/sessions")
    def sessions():
        return repository.sessions()

    @router.get("/sessions/{session_id}")
    def session(session_id: str):
        return repository.session(session_id)

    @router.post("/sessions/{session_id}/answer")
    def answer(session_id: str, request: AnswerRequest):
        return repository.answer(session_id, request)

    @router.post("/sessions/{session_id}/help")
    def help_item(session_id: str, request: HelpRequest):
        return repository.help(session_id, request)

    @router.get("/sessions/{session_id}/review")
    def review(session_id: str, item_id: str | None = Query(default=None, max_length=128),
               mistakes_only: bool = False):
        return repository.review(session_id, item_id, mistakes_only)

    @router.post("/sessions/{session_id}/pause")
    def pause(session_id: str, request: Command):
        return repository.transition(session_id, "pause", request)

    @router.post("/sessions/{session_id}/resume")
    def resume(session_id: str, request: Command):
        return repository.transition(session_id, "resume", request)

    @router.post("/sessions/{session_id}/end")
    def end(session_id: str, request: Command):
        return repository.transition(session_id, "end", request)

    return router
