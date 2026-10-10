# SPDX-License-Identifier: MIT
"""New whole-attempt routes; the parent mounts this router after saved_tests."""
import sqlite3

from fastapi import APIRouter, Header, Response
from pydantic import ValidationError

from renulus.contracts import ApiError

from .attempt_models import (CommitAnswer, HelpRequest, ItemRequest, QuestionReport,
                             SaveDraft, StartAttempt, SubmitAttempt, Transition)
from .attempt_repository import WholeAttemptRepository


def create_router(services):
    repository = WholeAttemptRepository(services)
    services.registry["whole_attempts"] = repository
    router = APIRouter(prefix="/assessment", tags=["whole-attempts"])

    def call(method, *args):
        try:
            return method(*args)
        except sqlite3.Error as error:
            raise ApiError("assessment_storage_failed", "Attempt storage is unavailable. Keep your draft and try again.", 503, True) from error
        except ValidationError as error:
            raise ApiError("invalid_attempt_snapshot", "This pinned attempt could not be read safely.", 409) from error

    @router.get("/policy")
    def policy(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return call(repository.policy)

    @router.get("/test-attempts")
    def attempts():
        return call(repository.list)

    @router.post("/test-attempts", status_code=201)
    def start(body: StartAttempt, idempotency_key: str = Header(min_length=8, max_length=128)):
        return call(repository.start, body, idempotency_key)

    @router.get("/test-attempts/{attempt_id}")
    def read(attempt_id: str):
        return call(repository.get, attempt_id)

    @router.put("/test-attempts/{attempt_id}/draft")
    def save(attempt_id: str, body: SaveDraft, idempotency_key: str = Header(min_length=8, max_length=128)):
        return call(repository.save, attempt_id, body, idempotency_key)

    @router.post("/test-attempts/{attempt_id}/present")
    def present(attempt_id: str, body: ItemRequest, idempotency_key: str = Header(min_length=8, max_length=128)):
        return call(repository.present, attempt_id, body, idempotency_key)

    @router.post("/test-attempts/{attempt_id}/help")
    def help_item(attempt_id: str, body: HelpRequest, idempotency_key: str = Header(min_length=8, max_length=128)):
        return call(repository.help, attempt_id, body, idempotency_key)

    @router.post("/test-attempts/{attempt_id}/submit-answer")
    def commit(attempt_id: str, body: CommitAnswer, idempotency_key: str = Header(min_length=8, max_length=128)):
        return call(repository.commit_answer, attempt_id, body, idempotency_key)

    @router.post("/test-attempts/{attempt_id}/submit")
    def submit(attempt_id: str, body: SubmitAttempt, idempotency_key: str = Header(min_length=8, max_length=128)):
        return call(repository.submit, attempt_id, body, idempotency_key)

    @router.post("/test-attempts/{attempt_id}/pause")
    def pause(attempt_id: str, body: Transition, idempotency_key: str = Header(min_length=8, max_length=128)):
        return call(repository.transition, attempt_id, "pause", body, idempotency_key)

    @router.post("/test-attempts/{attempt_id}/resume")
    def resume(attempt_id: str, body: Transition, idempotency_key: str = Header(min_length=8, max_length=128)):
        return call(repository.transition, attempt_id, "resume", body, idempotency_key)

    @router.post("/test-attempts/{attempt_id}/continue-untimed")
    def continue_untimed(attempt_id: str, body: Transition, idempotency_key: str = Header(min_length=8, max_length=128)):
        return call(repository.transition, attempt_id, "continue-untimed", body, idempotency_key)

    @router.post("/test-attempts/{attempt_id}/reports", status_code=201)
    def report(attempt_id: str, body: QuestionReport, idempotency_key: str = Header(min_length=8, max_length=128)):
        return call(repository.report, attempt_id, body, idempotency_key)

    return router
