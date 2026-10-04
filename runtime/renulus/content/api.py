# SPDX-License-Identifier: MIT
"""Module router; private assessment keys remain in the backend repository."""

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from renulus.contracts import ApiError

from .repository import ContentConflict, ContentRepository, ContentUnavailable
from .validation import PackValidationError


class InstallRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=200)


class WithdrawalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=1000)
    replacement_version: int | None = Field(default=None, ge=1)


def create_router(services) -> APIRouter:
    # App-owned pack root can be overridden by the integrator for packaging.
    root = Path(services.registry.get("content_pack_root", Path(__file__).resolve().parents[3] / "content" / "packs"))
    repository = ContentRepository(services.db, root)
    services.registry["content"] = repository
    default_pack = root / "renulus-foundations" / "1.0.0"
    already_installed = services.db.fetch_one(
        "SELECT 1 FROM content_packs WHERE pack_id=? AND version=?",
        ("renulus-foundations", "1.0.0"))
    if repository.active_manifest() is None and default_pack.is_dir() and not already_installed:
        repository.install_pack(default_pack)
    router = APIRouter(prefix="/content", tags=["content"])

    def call(method, *args, **kwargs):
        try:
            return method(*args, **kwargs)
        except ContentUnavailable as exc:
            raise ApiError("content_not_found", str(exc), 404) from exc
        except ContentConflict as exc:
            raise ApiError("content_conflict", str(exc), 409) from exc
        except PackValidationError as exc:
            raise ApiError("invalid_content_pack", str(exc), 422) from exc

    @router.get("/manifest")
    def manifest():
        return repository.active_manifest()

    @router.get("/topics")
    def topics():
        return repository.list_topics()

    @router.get("/sources")
    def sources():
        return repository.list_sources()

    @router.get("/sources/{source_id}")
    def source(source_id: str):
        return call(repository.get_source, source_id)

    @router.get("/sources/{source_id}/references")
    def source_references(source_id: str, include_historical: bool = False):
        return repository.references_for_source(source_id, include_historical=include_historical)

    @router.get("/cases")
    def cases():
        return [{k: c[k] for k in ("id", "version", "title", "summary", "topic_id",
                                  "secondary_topic_ids", "objective_ids", "review")}
                for c in repository.list_cases()]

    @router.get("/cases/{case_id}")
    def case(case_id: str):
        return call(repository.get_case, case_id)

    @router.get("/questions")
    def question_summaries(topic_id: str | None = None, domain: str | None = None, track: str | None = None):
        return repository.list_question_summaries(topic_id, domain, track)

    # Bank display belongs to M4, which commits family exposure before reveal.
    # There is deliberately no public question-detail endpoint here. The
    # trusted backend get_question_version remains available for pinned attempts.
    @router.post("/packs/install")
    def install(request: InstallRequest):
        candidate = (root / request.path).resolve()
        if not candidate.is_relative_to(root.resolve()):
            raise ApiError("invalid_pack_path", "Select a pack within the app content directory", 422)
        return call(repository.install_pack, candidate)

    @router.post("/questions/{question_id}/versions/{version}/withdraw")
    def withdraw(question_id: str, version: int, request: WithdrawalRequest):
        result = call(repository.withdraw_question, question_id, version, request.reason, request.replacement_version)
        return {"id": result["id"], "version": version, "withdrawn": result["withdrawn"],
                "withdrawal": result["withdrawal"]}

    return router
