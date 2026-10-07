# SPDX-License-Identifier: MIT
"""Module router; private assessment keys remain in the backend repository."""

import json
from pathlib import Path
import re
from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from renulus.contracts import ApiError

from .repository import ContentConflict, ContentRepository, ContentUnavailable
from .validation import MAX_FILE_BYTES, PackValidationError, validate_pack


PACK_VERSION_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+$"
VersionLabel = Annotated[str, Field(pattern=PACK_VERSION_PATTERN)]


class BootstrapSelection(BaseModel):
    """Integrator override; omitted version selects the newest bundled release."""

    model_config = ConfigDict(extra="forbid")
    id: str = Field(default="renulus-foundations", pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
    version: VersionLabel | None = None
    upgrade_from: list[VersionLabel] | None = None


def _version_number(label: str) -> tuple[int, int, int]:
    # Pack schema permits only final numeric major.minor.patch versions.
    return tuple(int(part) for part in label.split("."))


def _bundled_pack(root: Path, selection: BootstrapSelection):
    root = root.resolve()
    lineage = (root / selection.id).resolve()
    if not lineage.is_relative_to(root):
        raise PackValidationError("Bundled content must stay within the app pack directory")
    if selection.version is not None:
        candidates = [lineage / selection.version]
    else:
        candidates = sorted(
            (path for path in lineage.iterdir()
             if path.is_dir() and re.fullmatch(PACK_VERSION_PATTERN, path.name)),
            key=lambda path: (_version_number(path.name), path.name), reverse=True,
        ) if lineage.is_dir() else []
    for path in candidates:
        candidate = path.resolve()
        if not candidate.is_relative_to(lineage):
            raise PackValidationError("Bundled release must stay within its app pack lineage")
        if selection.version is None:
            manifest_path = candidate / "manifest.json"
            if not manifest_path.is_file():
                continue
            if manifest_path.stat().st_size > MAX_FILE_BYTES:
                raise PackValidationError("Bundled manifest exceeds the supported size")
            metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(metadata, dict) and metadata.get("state") == "draft":
                continue
        pack = validate_pack(candidate)
        if pack.manifest["id"] != selection.id or pack.manifest["version"] != path.name:
            raise PackValidationError("Bundled manifest identity must match its pack/version directory")
        return candidate, pack.manifest
    raise ContentUnavailable("No published bundled release is available for the selected pack")


def _bootstrap(services, repository: ContentRepository, root: Path) -> dict:
    active = repository.active_manifest()
    state = {"status": "preserved", "reason": "", "target": None,
             "active": {"id": active["id"], "version": active["version"]} if active else None}
    try:
        selection = BootstrapSelection.model_validate(services.registry.get("content_pack_selection", {}))
        if active is None and services.db.fetch_one("SELECT 1 FROM content_packs LIMIT 1"):
            state["reason"] = "historical_profile_inactive"
            return state
        if active is not None and active["id"] != selection.id:
            state["reason"] = "different_active_lineage"
            return state
        candidate, manifest = _bundled_pack(root, selection)
        state["target"] = {"id": manifest["id"], "version": manifest["version"]}
        if active is not None:
            if _version_number(manifest["version"]) <= _version_number(active["version"]):
                state["reason"] = "active_version_not_older"
                return state
            if selection.upgrade_from is not None and active["version"] not in selection.upgrade_from:
                state["reason"] = "upgrade_not_selected"
                return state
        if services.db.fetch_one(
            "SELECT 1 FROM content_packs WHERE pack_id=? AND version=?",
            (manifest["id"], manifest["version"]),
        ):
            # An installed but inactive target represents retained user/admin state.
            # Bootstrap must not silently undo a withdrawal or deliberate selection.
            state["reason"] = "target_previously_installed"
            return state
        repository.install_bundled_release(candidate)
    except (ContentUnavailable, ContentConflict, PackValidationError, ValidationError,
            OSError, UnicodeError, json.JSONDecodeError) as exc:
        code = ("content_not_found" if isinstance(exc, ContentUnavailable) else
                "content_conflict" if isinstance(exc, ContentConflict) else "invalid_content_pack")
        state.update(status="unavailable", reason="activation_failed",
                     error={"code": code, "message": str(exc), "retryable": False})
        return state
    state.update(status="activated", reason="fresh_profile" if active is None else "newer_bundled_release",
                 active=state["target"])
    return state


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
    services.registry["content_bootstrap"] = _bootstrap(services, repository, root)
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

    @router.get("/bootstrap")
    def bootstrap_status():
        # Startup outcome only; /manifest remains the canonical current selection.
        return services.registry["content_bootstrap"]

    @router.get("/topics")
    def topics():
        return repository.list_topics()

    @router.get("/tracks")
    def tracks():
        return repository.track_metadata()

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
