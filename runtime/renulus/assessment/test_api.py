# SPDX-License-Identifier: MIT
"""Saved-test collection router. The integration owner mounts it under /api/v1."""
import base64
import json
import sqlite3
from typing import Literal

from fastapi import APIRouter, Query

from renulus.contracts import ApiError
from .test_models import (CreateReviewedTestRequest, EditTestVersionRequest, QuestionReportRequest,
                          RenameTestRequest, TestLifecycleRequest)
from .test_repository import SavedTestRepository, encode


def create_router(services) -> APIRouter:
    repository = SavedTestRepository(services)
    services.registry["saved_tests"] = repository
    services.on_startup.append(repository.backfill_legacy)
    router = APIRouter(prefix="/assessment/tests", tags=["saved-tests"])

    def call(method, *args, **kwargs):
        try:
            return method(*args, **kwargs)
        except sqlite3.Error as error:
            raise ApiError("assessment_storage_failed", "Saved tests could not be saved or loaded. Keep your edits and retry", 503, True) from error

    @router.get("")
    def collection(lifecycle: Literal["active", "archived"] = "active",
                   origin: Literal["reviewed_bank", "generated", "imported", "nightly"] | None = None,
                   q: str = Query(default="", max_length=200), limit: int = Query(default=50, ge=1, le=100),
                   cursor: str | None = Query(default=None, max_length=2048)):
        scope, before = [lifecycle, origin, q], None
        if cursor:
            try:
                value = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
                if value["scope"] != scope or not isinstance(value["last"], str) or len(value["last"]) > 256:
                    raise ValueError()
                before = value["last"]
            except (ValueError, KeyError, TypeError):
                raise ApiError("invalid_request", "Reopen the collection to restart this filtered page", 422) from None
        call(repository.backfill_legacy)
        result = call(repository.list_tests, lifecycle=lifecycle, origin=origin, query=q, limit=limit, before=before)
        if result["next_cursor"]:
            result["next_cursor"] = base64.urlsafe_b64encode(encode({"last": result["next_cursor"], "scope": scope}).encode()).decode().rstrip("=")
        return result

    @router.post("/reviewed")
    def create_reviewed(request: CreateReviewedTestRequest):
        return call(repository.create_reviewed, request)

    @router.get("/versions/{version_id}/setup")
    def setup_version(version_id: str):
        return call(repository.setup_version, version_id)

    @router.get("/{test_id}")
    def detail(test_id: str):
        return call(repository.get_test, test_id)

    @router.get("/{test_id}/setup")
    def setup(test_id: str, version_id: str | None = Query(default=None, max_length=256)):
        return call(repository.setup, test_id, version_id)

    @router.get("/{test_id}/history")
    def history(test_id: str):
        return call(repository.legacy_history, test_id)

    @router.get("/{test_id}/versions")
    def versions(test_id: str):
        return {"items": call(repository.get_test, test_id)["versions"]}

    @router.get("/{test_id}/versions/{version_id}/preview")
    def preview(test_id: str, version_id: str):
        return call(repository.preview_version, test_id, version_id)

    @router.post("/{test_id}/versions")
    def edit(test_id: str, request: EditTestVersionRequest):
        return call(repository.edit_version, test_id, request)

    @router.patch("/{test_id}")
    def rename(test_id: str, request: RenameTestRequest):
        return call(repository.rename, test_id, request)

    @router.post("/{test_id}/archive")
    def archive(test_id: str, request: TestLifecycleRequest):
        return call(repository.lifecycle, test_id, request, "archive")

    @router.post("/{test_id}/restore")
    def restore(test_id: str, request: TestLifecycleRequest):
        return call(repository.lifecycle, test_id, request, "restore")

    @router.delete("/{test_id}")
    def delete(test_id: str, request: TestLifecycleRequest):
        return call(repository.lifecycle, test_id, request, "delete")

    @router.post("/{test_id}/versions/{version_id}/reports")
    def report(test_id: str, version_id: str, request: QuestionReportRequest):
        return call(repository.report_question, test_id, version_id, request)

    return router
